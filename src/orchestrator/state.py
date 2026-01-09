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
__all__ = ["JobStatus", "JobInfo", "ResearchState", "DEFAULT_REVISION_COUNT", "PhaseEnum", "ExecutionTier"]


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


class ExecutionTier(str, Enum):
    """Execution tier for job stages (Tier A = CPU/Embedder-bound, Tier B = GPU/Nemotron-49B-bound)."""
    TIER_A = "A"
    TIER_B = "B"


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

# Tier B concurrency control: max 1 concurrent Nemotron-49B call (max-running-requests=1)
# This ensures serialization of heavy LLM calls to respect KV cache limits and 64k context policy
_tier_b_semaphore = threading.Semaphore(1)


def acquire_tier_b_slot(blocking: bool = True, timeout: Optional[float] = None) -> bool:
    """Acquire a Tier B slot for Nemotron-49B call (serialization).
    
    Args:
        blocking: If True, block until slot is available. If False, return immediately.
        timeout: Optional timeout in seconds (only used if blocking=True).
    
    Returns:
        True if slot acquired, False otherwise.
    """
    if blocking:
        if timeout is not None:
            return _tier_b_semaphore.acquire(blocking=True, timeout=timeout)
        else:
            _tier_b_semaphore.acquire(blocking=True)
            return True
    else:
        return _tier_b_semaphore.acquire(blocking=False)


def release_tier_b_slot() -> None:
    """Release a Tier B slot after Nemotron-49B call completes."""
    _tier_b_semaphore.release()

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
    # Raw text and PDF path (preserved across all nodes)
    raw_text: Optional[str]
    pdf_path: Optional[str]
