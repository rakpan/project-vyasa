import threading
from datetime import datetime
from enum import Enum
from operator import add
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph.message import add_messages


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


class ResearchState(TypedDict, total=False):
    """Typed state for LangGraph workflows with reducer semantics."""

    jobId: str
    threadId: str
    revision_count: int
    messages: Annotated[list, add_messages]
    triples: Annotated[list, add]
    artifacts: Annotated[list, add]
    tone_findings: list
    tone_flags: list
