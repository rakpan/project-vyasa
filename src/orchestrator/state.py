"""
State management for LangGraph workflows.

Provides JobStatus enum, JobInfo TypedDict, and ResearchState Pydantic model
for stable, versionable workflow state management.
"""

import threading
from datetime import datetime
from enum import Enum
from operator import add
from typing import Annotated, Any, Dict, List, Optional, TypedDict, Union

from langgraph.graph.message import add_messages

# Import Pydantic ResearchState model
from .schemas.state import ResearchState as ResearchStateModel, PhaseEnum

# Re-export for backward compatibility
__all__ = ["JobStatus", "JobInfo", "ResearchState", "DEFAULT_REVISION_COUNT", "PhaseEnum"]


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


# Backward-compatible TypedDict for legacy code
class ResearchState(TypedDict, total=False):
    """Legacy TypedDict for ResearchState (deprecated, use ResearchStateModel).
    
    This TypedDict is maintained for backward compatibility with existing code.
    New code should use ResearchStateModel from .schemas.state.
    
    The Pydantic ResearchStateModel provides:
    - Required fields: job_id, project_id, ingestion_id, project_config, phase
    - Workspace fields: raw_chunks, claims, conflicts, manuscript_blocks
    - Control flags: needs_human_review, conflict_detected
    - LangGraph reducer support: messages, triples, artifacts
    """

    jobId: str
    threadId: str
    revision_count: int
    messages: Annotated[list, add_messages]
    triples: Annotated[list, add]
    artifacts: Annotated[list, add]
    tone_findings: list
    tone_flags: list
    # New fields for stable state contract
    job_id: Optional[str]
    project_id: Optional[str]
    ingestion_id: Optional[str]
    project_config: Optional[Dict[str, Any]]
    phase: Optional[str]
    raw_chunks: Optional[List[Dict[str, Any]]]
    claims: Optional[List[Dict[str, Any]]]
    conflicts: Optional[List[Dict[str, Any]]]
    manuscript_blocks: Optional[List[Dict[str, Any]]]
    needs_human_review: Optional[bool]
    conflict_detected: Optional[bool]
