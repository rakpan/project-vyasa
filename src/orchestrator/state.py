from enum import Enum
from typing import List, Dict, Any, Optional, TypedDict
from datetime import datetime
import threading

from pydantic import BaseModel, Field, ConfigDict, model_validator


class JobStatus(str, Enum):
    """Status of an asynchronous job."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    FINALIZED = "FINALIZED"
    NEEDS_SIGNOFF = "NEEDS_SIGNOFF"
    # Backward-compatible aliases
    PENDING = QUEUED
    PROCESSING = RUNNING
    COMPLETED = SUCCEEDED


class PaperState(BaseModel):
    """Shared state for the agentic PDF processing workflow."""

    model_config = ConfigDict(extra="allow")

    pdf_path: str = ""
    raw_text: str = ""
    image_paths: List[str] = Field(default_factory=list)
    vision_results: List[Dict[str, Any]] = Field(default_factory=list)
    extracted_json: Dict[str, Any] = Field(default_factory=dict)
    critiques: List[str] = Field(default_factory=list)
    revision_count: int = 0
    project_id: Optional[str] = None
    project_context: Optional[Dict[str, Any]] = None
    doc_hash: Optional[str] = None
    reference_ids: Optional[List[str]] = None
    force_refresh_context: bool = False
    context_sources: Optional[Dict[str, int]] = None
    selected_reference_ids: Optional[List[str]] = None
    critic_status: Optional[str] = None
    critic_score: Optional[float] = None
    synthesis: Optional[str] = None

    @model_validator(mode="after")
    def validate_cartographer_output(self) -> "PaperState":
        extracted = self.extracted_json or {}
        triples = extracted.get("triples") if isinstance(extracted, dict) else None
        entities = extracted.get("entities") if isinstance(extracted, dict) else None
        if self.raw_text and isinstance(extracted, dict) and ("triples" in extracted or "entities" in extracted):
            triples_count = len(triples) if isinstance(triples, list) else 0
            entities_count = len(entities) if isinstance(entities, list) else 0
            if (triples_count + entities_count) <= 0:
                raise ValueError("Cartographer validation failed: no triples/entities extracted from provided text")
        return self

    @model_validator(mode="after")
    def validate_critic_output(self) -> "PaperState":
        if self.critic_status is not None:
            status_norm = str(self.critic_status).lower()
            if status_norm not in {"pass", "fail", "manual"}:
                raise ValueError(f"Critic validation failed: invalid status {self.critic_status}")
            if self.critic_score is None:
                raise ValueError("Critic validation failed: missing critic_score")
        return self

    @model_validator(mode="after")
    def validate_synthesizer_output(self) -> "PaperState":
        if "synthesis" in self.model_dump(exclude_none=False):
            if not self.synthesis or not str(self.synthesis).strip():
                raise ValueError("Synthesizer validation failed: narrative prose is empty")
        return self


class JobInfo(TypedDict, total=False):
    """Information about an asynchronous job."""
    job_id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    current_step: Optional[str]  # e.g., "Cartographer", "Critic", "Saver"
    result: Optional[Dict[str, Any]]  # Final workflow result
    error: Optional[str]  # Error message if failed
    progress: float  # 0.0 to 1.0


# Global job registry (in-memory, thread-safe)
_job_registry: Dict[str, JobInfo] = {}
_registry_lock = threading.Lock()

# Concurrency control: max 2 concurrent jobs
_job_semaphore = threading.Semaphore(2)

# Default revision count for new jobs
DEFAULT_REVISION_COUNT = 0
