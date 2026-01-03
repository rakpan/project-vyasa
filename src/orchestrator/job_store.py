"""
Persistent job store backed by ArangoDB with in-memory fallback.

This keeps job status/progress across orchestrator restarts and allows
polling APIs to survive longer-running workflows.
"""

import uuid
from typing import Any, Dict, List, Optional

from arango import ArangoClient

from ..shared.config import get_memory_url, get_arango_password, ARANGODB_DB, ARANGODB_USER
from ..shared.logger import get_logger
from ..shared.utils import get_utc_now
from .state import JobStatus

logger = get_logger("orchestrator", __name__)

JOBS_COLLECTION = "jobs"

# In-memory fallback (used if Arango is unavailable)
_mem_store: Dict[str, Dict[str, Any]] = {}
_conflict_store: Dict[str, Dict[str, Any]] = {}
_reframe_store: Dict[str, Dict[str, Any]] = {}


def _get_db():
    client = ArangoClient(hosts=get_memory_url())
    return client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())


def _ensure_collection(db):
    if not db.has_collection(JOBS_COLLECTION):
        db.create_collection(JOBS_COLLECTION)
    if not db.has_collection("conflict_reports"):
        db.create_collection("conflict_reports")
    if not db.has_collection("reframing_proposals"):
        db.create_collection("reframing_proposals")


def _now_iso() -> str:
    return get_utc_now().isoformat()


def create_job_record(
    initial_state: Dict[str, Any],
    idempotency_key: Optional[str] = None,
    parent_job_id: Optional[str] = None,
    job_version: int = 1,
    reprocess_reason: Optional[str] = None,
    applied_reference_ids: Optional[list] = None,
) -> str:
    job_id = str(uuid.uuid4())
    record = {
        "_key": job_id,
        "job_id": job_id,
        "status": JobStatus.QUEUED.value,
        "progress": 0.0,
        "message": "Queued",
        "error": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "initial_state": initial_state,
        "result": None,
        "idempotency_key": idempotency_key,
        "parent_job_id": parent_job_id,
        "job_version": job_version,
        "reprocess_reason": reprocess_reason,
        "applied_reference_ids": applied_reference_ids or [],
    }
    try:
        db = _get_db()
        _ensure_collection(db)
        collection = db.collection(JOBS_COLLECTION)
        # Idempotency: if provided and exists, return existing job_id
        if idempotency_key:
            cursor = db.aql.execute(
                f"FOR j IN {JOBS_COLLECTION} FILTER j.idempotency_key == @ik RETURN j",
                bind_vars={"ik": idempotency_key},
            )
            existing = list(cursor)
            if existing:
                return existing[0]["job_id"]
        collection.insert(record)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Job store falling back to memory", extra={"payload": {"error": str(exc)}})
        _mem_store[job_id] = record
    return job_id


def update_job_record(job_id: str, patch: Dict[str, Any]) -> None:
    patch["updated_at"] = _now_iso()
    try:
        db = _get_db()
        _ensure_collection(db)
        collection = db.collection(JOBS_COLLECTION)
        if not collection.get(job_id):
            return
        collection.update({"_key": job_id, **patch})
    except Exception:
        if job_id in _mem_store:
            _mem_store[job_id].update(patch)


def get_job_record(job_id: str) -> Optional[Dict[str, Any]]:
    try:
        db = _get_db()
        _ensure_collection(db)
        collection = db.collection(JOBS_COLLECTION)
        doc = collection.get(job_id)
        if doc:
            return doc
    except Exception:
        pass
    return _mem_store.get(job_id)


def set_job_result_record(job_id: str, result: Dict[str, Any]) -> None:
    patch = {
        "result": result,
        "status": JobStatus.SUCCEEDED.value,
        "progress": 1.0,
        "message": "Completed",
    }
    update_job_record(job_id, patch)


def store_conflict_report(report: Dict[str, Any]) -> str:
    """Persist a conflict report with in-memory fallback."""
    report_id = report.get("report_id")
    if not report_id:
        report_id = str(uuid.uuid4())
        report["report_id"] = report_id
    try:
        db = _get_db()
        _ensure_collection(db)
        coll = db.collection("conflict_reports")
        coll.insert({**report, "_key": report_id})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Conflict store falling back to memory", extra={"payload": {"error": str(exc)}})
        _conflict_store[report_id] = report
    # Update job pointer if available
    job_id = report.get("job_id")
    if job_id:
        update_job_record(job_id, {"conflict_report_id": report_id})
    return report_id


def get_conflict_report(report_id: str) -> Optional[Dict[str, Any]]:
    """Get conflict report by ID.
    
    Args:
        report_id: Conflict report ID
    
    Returns:
        Conflict report dictionary or None if not found
    """
    try:
        db = _get_db()
        _ensure_collection(db)
        coll = db.collection("conflict_reports")
        doc = coll.get(report_id)
        if doc:
            return doc
    except Exception:
        pass
    return _conflict_store.get(report_id)


def store_reframing_proposal(proposal: Dict[str, Any]) -> str:
    """Persist a reframing proposal with in-memory fallback."""
    proposal_id = proposal.get("proposal_id") or str(uuid.uuid4())
    proposal["proposal_id"] = proposal_id
    try:
        db = _get_db()
        _ensure_collection(db)
        coll = db.collection("reframing_proposals")
        coll.insert({**proposal, "_key": proposal_id})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Reframing store falling back to memory", extra={"payload": {"error": str(exc)}})
        _reframe_store[proposal_id] = proposal
    job_id = proposal.get("job_id")
    if job_id:
        update_job_record(job_id, {"reframing_proposal_id": proposal_id, "status": JobStatus.NEEDS_SIGNOFF.value})
    return proposal_id


def list_jobs_by_project(project_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """List jobs for a project, ordered by created_at descending (most recent first).
    
    Args:
        project_id: Project ID to filter by
        limit: Maximum number of jobs to return (default 10)
    
    Returns:
        List of job records with job_id, status, created_at, and initial_state.project_id
    """
    jobs = []
    try:
        db = _get_db()
        _ensure_collection(db)
        
        # Query jobs where initial_state.project_id matches
        query = f"""
        FOR j IN {JOBS_COLLECTION}
        FILTER j.initial_state.project_id == @project_id
        SORT j.created_at DESC
        LIMIT @limit
        RETURN {{
            job_id: j.job_id,
            status: j.status,
            created_at: j.created_at,
            updated_at: j.updated_at,
            progress: j.progress,
            pdf_path: j.initial_state.pdf_path,
            parent_job_id: j.parent_job_id,
            job_version: j.job_version
        }}
        """
        cursor = db.aql.execute(query, bind_vars={"project_id": project_id, "limit": limit})
        jobs = list(cursor)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Job list query failed, falling back to memory", extra={"payload": {"error": str(exc)}})
        # Fallback to memory store (filter by initial_state.project_id)
        for job_id, record in _mem_store.items():
            initial_state = record.get("initial_state") or {}
            if initial_state.get("project_id") == project_id:
                jobs.append({
                    "job_id": record.get("job_id") or job_id,
                    "status": record.get("status"),
                    "created_at": record.get("created_at"),
                    "updated_at": record.get("updated_at"),
                    "progress": record.get("progress"),
                    "pdf_path": initial_state.get("pdf_path"),
                    "parent_job_id": record.get("parent_job_id"),
                    "job_version": record.get("job_version", 1),
                })
        # Sort by created_at descending
        jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)
        jobs = jobs[:limit]
    
    return jobs
