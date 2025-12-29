"""
Job management for asynchronous workflow execution.

Handles job tracking, status updates, and concurrency control.
"""

import uuid
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

from .state import JobStatus, JobInfo, _job_registry, _registry_lock, _job_semaphore
from ..shared.logger import get_logger
from .job_store import create_job_record, update_job_record, get_job_record, set_job_result_record
from .normalize import normalize_extracted_json

logger = get_logger("orchestrator", __name__)


def create_job(initial_state: Dict, idempotency_key: Optional[str] = None) -> str:
    """Create a new job and return its ID (persisted)."""
    job_id = create_job_record(initial_state, idempotency_key=idempotency_key)

    with _registry_lock:
        _job_registry[job_id] = JobInfo(
            job_id=job_id,
            status=JobStatus.QUEUED,
            created_at=datetime.now(timezone.utc),
            started_at=None,
            completed_at=None,
            current_step=None,
            result=None,
            error=None,
            progress=0.0,
        )

    logger.info(f"Created job {job_id}", extra={"payload": {"job_id": job_id}})
    return job_id


def get_job(job_id: str) -> Optional[JobInfo]:
    """Get job information by ID."""
    record = get_job_record(job_id) or {}
    with _registry_lock:
        mem_job = _job_registry.get(job_id)
    if record:
        # Normalize record to JobInfo shape
        return JobInfo(
            job_id=record.get("job_id", job_id),
            status=JobStatus(record.get("status", JobStatus.QUEUED.value)),
            created_at=record.get("created_at"),
            started_at=record.get("started_at"),
            completed_at=record.get("completed_at"),
            current_step=record.get("current_step"),
            result=record.get("result"),
            error=record.get("error"),
            progress=record.get("progress", 0.0),
        )
    return mem_job


def update_job_status(
    job_id: str,
    status: JobStatus,
    current_step: Optional[str] = None,
    progress: Optional[float] = None,
    error: Optional[str] = None,
    message: Optional[str] = None,
) -> None:
    """Update job status and metadata."""
    with _registry_lock:
        if job_id not in _job_registry:
            _job_registry[job_id] = JobInfo(job_id=job_id, status=status, created_at=datetime.now(timezone.utc))
        job = _job_registry[job_id]
        job["status"] = status
        if current_step is not None:
            job["current_step"] = current_step
        if progress is not None:
            job["progress"] = max(0.0, min(1.0, progress))
        if error is not None:
            job["error"] = error
        if status == JobStatus.RUNNING and job.get("started_at") is None:
            job["started_at"] = datetime.now(timezone.utc)
        if status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
            job["completed_at"] = datetime.now(timezone.utc)
            if status == JobStatus.SUCCEEDED:
                job["progress"] = 1.0

    update_job_record(
        job_id,
        {
            "status": status.value,
            "current_step": current_step,
            "progress": job.get("progress", 0.0),
            "error": error,
            "message": message,
        },
    )

    logger.info(
        f"Job {job_id} status updated",
        extra={"payload": {"job_id": job_id, "status": status.value, "current_step": current_step, "progress": progress}},
    )


def set_job_result(job_id: str, result: Dict) -> None:
    """Set the final result for a completed job."""
    # Normalize extracted_json to guarantee triples array
    extracted = result.get("extracted_json", {})
    result["extracted_json"] = normalize_extracted_json(extracted)

    with _registry_lock:
        if job_id not in _job_registry:
            _job_registry[job_id] = JobInfo(job_id=job_id, status=JobStatus.SUCCEEDED)
        _job_registry[job_id]["result"] = result
        _job_registry[job_id]["status"] = JobStatus.SUCCEEDED
        _job_registry[job_id]["completed_at"] = datetime.now(timezone.utc)
        _job_registry[job_id]["progress"] = 1.0

    set_job_result_record(job_id, result)
    logger.info(
        f"Job {job_id} completed",
        extra={"payload": {"job_id": job_id, "triples_count": len(result.get('extracted_json', {}).get('triples', []))}},
    )


def acquire_job_slot() -> bool:
    """Acquire a slot for job execution (concurrency control)."""
    acquired = _job_semaphore.acquire(blocking=False)
    if not acquired:
        logger.warning("Job queue full (max 2 concurrent jobs)")
    return acquired


def release_job_slot() -> None:
    """Release a job execution slot."""
    _job_semaphore.release()
