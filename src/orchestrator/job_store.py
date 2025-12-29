"""
Persistent job store backed by ArangoDB with in-memory fallback.

This keeps job status/progress across orchestrator restarts and allows
polling APIs to survive longer-running workflows.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from arango import ArangoClient

from ..shared.config import MEMORY_URL, ARANGODB_DB, ARANGODB_USER, ARANGODB_PASSWORD
from ..shared.logger import get_logger
from .state import JobStatus

logger = get_logger("orchestrator", __name__)

JOBS_COLLECTION = "jobs"

# In-memory fallback (used if Arango is unavailable)
_mem_store: Dict[str, Dict[str, Any]] = {}


def _get_db():
    client = ArangoClient(hosts=MEMORY_URL)
    return client.db(ARANGODB_DB, username=ARANGODB_USER, password=ARANGODB_PASSWORD)


def _ensure_collection(db):
    if not db.has_collection(JOBS_COLLECTION):
        db.create_collection(JOBS_COLLECTION)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job_record(initial_state: Dict[str, Any], idempotency_key: Optional[str] = None) -> str:
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
