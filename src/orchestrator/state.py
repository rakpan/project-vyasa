from enum import Enum
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
import threading


class JobStatus(str, Enum):
    """Status of an asynchronous job."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    FINALIZED = "FINALIZED"
    # Backward-compatible aliases
    PENDING = QUEUED
    PROCESSING = RUNNING
    COMPLETED = SUCCEEDED


class PaperState(TypedDict, total=False):
    """Shared state for the agentic PDF processing workflow."""

    pdf_path: str
    raw_text: str
    image_paths: List[str]
    vision_results: List[Dict[str, Any]]
    extracted_json: Dict[str, Any]
    critiques: List[str]
    revision_count: int
    project_id: Optional[str]  # UUID of the project this workflow belongs to
    project_context: Optional[Dict[str, Any]]  # Project metadata as plain dict (JSON-serializable)
    doc_hash: Optional[str]  # SHA256 hash of the source PDF (for text cache lookup)


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
