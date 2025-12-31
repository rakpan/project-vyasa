"""
Job management API endpoints for reprocessing and versioning.

Provides endpoints for:
- Reprocessing jobs with new knowledge references
- Comparing job versions (diff endpoint)
"""

import threading
from typing import Dict, Any, List, Optional, Set
from flask import Blueprint, request, jsonify

from ..job_manager import create_job, get_job
from ..job_store import get_job_record, update_job_record
from ..state import JobStatus
from ..telemetry import TelemetryEmitter
from ...shared.logger import get_logger
from datetime import datetime, timezone, timedelta

logger = get_logger("orchestrator", __name__)
telemetry_emitter = TelemetryEmitter()

# Import workflow runner (avoid circular dependency by importing at function level)

# Flask Blueprint for job routes
jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


def _get_job_version(job_id: str, visited: Optional[Set[str]] = None, depth: int = 0) -> int:
    """Get the version number for a job (1 for original, increments for reprocesses).
    
    Includes cycle detection and max depth protection to prevent infinite recursion.
    
    Args:
        job_id: Job ID to get version for
        visited: Set of visited job IDs (internal, for cycle detection)
        depth: Current recursion depth (internal, for max depth protection)
    
    Returns:
        Version number (1 for original, increments for reprocesses)
    """
    # Initialize visited set on first call
    if visited is None:
        visited = set()
    
    # Cycle detection: if we've seen this job_id before, return sentinel -1 (caller will translate to 1)
    if job_id in visited:
        logger.warning(
            f"Cycle detected in job version chain for job {job_id}",
            extra={"payload": {"job_id": job_id, "visited": list(visited), "depth": depth}},
        )
        return -1  # Sentinel value to indicate cycle (caller will convert to 1)
    
    # Max depth protection: if we exceed max depth, return safe fallback
    MAX_DEPTH = 10
    if depth > MAX_DEPTH:
        logger.warning(
            f"Max depth ({MAX_DEPTH}) exceeded in job version chain for job {job_id}",
            extra={"payload": {"job_id": job_id, "depth": depth}},
        )
        return -1  # Sentinel value to indicate max depth exceeded (caller will convert to 1)
    
    # Add current job_id to visited set
    visited.add(job_id)
    
    try:
        record = get_job_record(job_id) or {}
        
        # If version is explicitly stored, use it
        if "job_version" in record:
            version = record.get("job_version", 1)
        else:
            # If no version, check parent_job_id and trace back
            parent_id = record.get("parent_job_id")
            if parent_id:
                parent_version = _get_job_version(parent_id, visited, depth + 1)
                # If parent_version is -1 (cycle/depth detected), propagate sentinel up
                if parent_version < 0:
                    version = -1
                else:
                    version = parent_version + 1
            else:
                # Default to version 1 for original jobs
                version = 1
    finally:
        # Remove job_id from visited set after processing (allows re-visit in different path)
        visited.discard(job_id)
    # Convert sentinels only at root invocation
    if depth == 0 and version < 1:
        return 1
    return version


@jobs_bp.route("/<job_id>/reprocess", methods=["POST"])
def reprocess_job(job_id: str):
    """Reprocess a job with additional knowledge references.
    
    Request body (JSON):
        {
            "reference_ids": List[str],  # List of external reference IDs to include
            "reprocess_reason": Optional[str]  # Optional reason for reprocessing
        }
    
    This endpoint:
    1. Clones the original job's initial_state
    2. Sets parent_job_id, job_version=parent.version+1
    3. Sets force_refresh_context=true
    4. Stores applied_reference_ids from request
    5. Enqueues the new job and returns new_job_id
    
    Response:
        {
            "job_id": "new-job-uuid",
            "parent_job_id": "original-job-uuid",
            "job_version": 2,
            "status": "QUEUED"
        }
    
    Errors:
        404: Original job not found
        400: Invalid reference_ids or job not in a reprocessable state
    """
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    status = job.get("status")
    status_value = status.value if isinstance(status, JobStatus) else str(status)
    
    # Only allow reprocessing of jobs in certain states
    if status_value not in (JobStatus.SUCCEEDED.value, JobStatus.FINALIZED.value, "completed", "low_confidence", "conflicts_present"):
        return jsonify({"error": f"Job status {status_value} does not allow reprocessing"}), 400
    
    payload = request.json or {}
    reference_ids = payload.get("reference_ids", [])
    reprocess_reason = payload.get("reprocess_reason")
    
    if not reference_ids:
        return jsonify({"error": "reference_ids list is required"}), 400
    
    # Get original job's initial_state and record
    record = get_job_record(job_id) or {}
    initial_state = job.get("initial_state") or {}
    if not initial_state:
        # Try to get from record
        initial_state = record.get("initial_state") or {}
    
    project_id = initial_state.get("project_id")
    
    if not project_id:
        return jsonify({"error": "Original job missing project_id"}), 400
    
    try:
        # Get parent job version
        parent_version = _get_job_version(job_id)
        new_version = parent_version + 1
        
        # Clone job config with reprocessing flags
        new_initial_state = {
            **initial_state,
            "reference_ids": reference_ids,
            "force_refresh_context": True,  # Prioritize candidate facts
            "context_sources": {},  # Will be populated during context assembly
        }
        
        # Create new job with versioning metadata
        new_job_id = create_job(
            new_initial_state,
            parent_job_id=job_id,
            job_version=new_version,
            reprocess_reason=reprocess_reason,
            applied_reference_ids=reference_ids,
        )
        
        # Emit reprocess requested telemetry
        telemetry_emitter.emit_event(
            "job_reprocess_requested",
            {
                "parent_job_id": job_id,
                "new_job_id": new_job_id,
                "applied_reference_ids": reference_ids,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "job_version": new_version,
                "reprocess_reason": reprocess_reason,
            },
        )
        
        # Start the workflow (lazy import to avoid circular dependency)
        from ..server import _run_workflow_async
        thread = threading.Thread(
            target=_run_workflow_async,
            args=(new_job_id, new_initial_state),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            "job_id": new_job_id,
            "parent_job_id": job_id,
            "job_version": new_version,
            "status": JobStatus.QUEUED.value
        }), 202
        
    except Exception as exc:
        logger.error(f"Reprocess failed for job {job_id}: {exc}", exc_info=True)
        return jsonify({"error": str(exc)}), 500


def _calculate_triple_delta(triples1: List[Dict[str, Any]], triples2: List[Dict[str, Any]]) -> tuple[int, int, List[Dict], List[Dict]]:
    """Calculate triple deltas between two job results.
    
    Args:
        triples1: Triples from first job (typically parent/older)
        triples2: Triples from second job (typically child/newer)
    
    Returns:
        Tuple of (triples_added_count, triples_removed_count, added_triples, removed_triples)
    """
    # Create a hash-based comparison (subject + predicate + object as key)
    def triple_key(t: Dict[str, Any]) -> str:
        return f"{t.get('subject', '')}|{t.get('predicate', '')}|{t.get('object', '')}"
    
    set1 = {triple_key(t): t for t in triples1 if isinstance(t, dict)}
    set2 = {triple_key(t): t for t in triples2 if isinstance(t, dict)}
    
    added_keys = set2.keys() - set1.keys()
    removed_keys = set1.keys() - set2.keys()
    
    added_triples = [set2[k] for k in added_keys]
    removed_triples = [set1[k] for k in removed_keys]
    
    return len(added_keys), len(removed_keys), added_triples, removed_triples


def _count_conflicts(result: Dict[str, Any]) -> int:
    """Count conflicts in a job result."""
    conflict_flags = result.get("conflict_flags") or []
    if isinstance(conflict_flags, list):
        return len(conflict_flags)
    
    # Check extracted_json for conflict flags
    extracted_json = result.get("extracted_json", {})
    if isinstance(extracted_json, dict):
        # Check for conflict-related metadata
        metadata = extracted_json.get("metadata", {})
        if isinstance(metadata, dict):
            conflicts = metadata.get("conflicts") or []
            if isinstance(conflicts, list):
                return len(conflicts)
    
    return 0


def _calculate_unsupported_claim_rate(result: Dict[str, Any]) -> float:
    """Calculate unsupported claim rate (0.0-1.0).
    
    Args:
        result: Job result dictionary
    
    Returns:
        Rate as float between 0.0 and 1.0
    """
    unsupported_count = _count_unsupported_claims(result)
    extracted_json = result.get("extracted_json", {})
    triples = extracted_json.get("triples", []) if isinstance(extracted_json, dict) else []
    total = len(triples) if isinstance(triples, list) else 0
    
    if total == 0:
        return 0.0
    
    return unsupported_count / total


def _count_unsupported_claims(result: Dict[str, Any]) -> int:
    """Count unsupported claims in a job result."""
    extracted_json = result.get("extracted_json", {})
    if not isinstance(extracted_json, dict):
        return 0
    
    triples = extracted_json.get("triples", [])
    if not isinstance(triples, list):
        return 0
    
    # Count triples with low confidence or missing evidence
    unsupported = 0
    for triple in triples:
        if not isinstance(triple, dict):
            continue
        confidence = triple.get("confidence", 1.0)
        has_evidence = bool(triple.get("source_pointer") or triple.get("evidence"))
        
        if confidence < 0.5 or not has_evidence:
            unsupported += 1
    
    return unsupported


def _count_missing_fields(result: Dict[str, Any]) -> int:
    """Count triples with missing required fields."""
    extracted_json = result.get("extracted_json", {})
    if not isinstance(extracted_json, dict):
        return 0
    
    triples = extracted_json.get("triples", [])
    if not isinstance(triples, list):
        return 0
    
    required_fields = {"subject", "predicate", "object"}
    missing_count = 0
    
    for triple in triples:
        if not isinstance(triple, dict):
            missing_count += 1
            continue
        
        for field in required_fields:
            if not triple.get(field):
                missing_count += 1
                break  # Count each triple only once
    
    return missing_count


@jobs_bp.route("/<job_id>/diff", methods=["GET"])
def get_job_diff(job_id: str):
    """Compare two job versions and return deltas.
    
    Query parameters:
        against: Other job ID to compare against (required)
    
    Response:
        {
            "job_id": "...",
            "against": "...",
            "deltas": {
                "conflicts_delta": -12,
                "missing_fields_delta": -4,
                "unsupported_claims_delta": -7,
                "triples_added": 55,
                "triples_removed": 10
            },
            "details": {
                "conflicts_resolved": [...],
                "new_facts_used": [...],
                "citations_added": [...]
            }
        }
    
    Errors:
        404: Job not found
        400: Missing 'against' parameter
    """
    against_id = request.args.get("against")
    if not against_id:
        return jsonify({"error": "Query parameter 'against' is required"}), 400
    
    job1 = get_job(job_id)
    job2 = get_job(against_id)
    
    if not job1:
        return jsonify({"error": f"Job {job_id} not found"}), 404
    if not job2:
        return jsonify({"error": f"Job {against_id} not found"}), 404
    
    result1 = job1.get("result") or {}
    result2 = job2.get("result") or {}
    
    # Calculate deltas (result2 - result1, so positive means improvement)
    conflicts1 = _count_conflicts(result1)
    conflicts2 = _count_conflicts(result2)
    conflicts_delta = conflicts2 - conflicts1
    
    missing_fields1 = _count_missing_fields(result1)
    missing_fields2 = _count_missing_fields(result2)
    missing_fields_delta = missing_fields2 - missing_fields1
    
    unsupported1 = _count_unsupported_claims(result1)
    unsupported2 = _count_unsupported_claims(result2)
    unsupported_claims_delta = unsupported2 - unsupported1
    
    # Triple deltas
    triples1 = (result1.get("extracted_json") or {}).get("triples", [])
    triples2 = (result2.get("extracted_json") or {}).get("triples", [])
    triples_added, triples_removed, added_triples, removed_triples = _calculate_triple_delta(
        triples1 if isinstance(triples1, list) else [],
        triples2 if isinstance(triples2, list) else []
    )
    
    # Build details (simplified for now - can be enhanced when more artifacts exist)
    details = {
        "conflicts_resolved": [],  # TODO: Track specific conflicts when conflict tracking is enhanced
        "new_facts_used": [],  # TODO: Track which candidate facts were used
        "citations_added": [],  # TODO: Track citation changes when citation tracking is enhanced
    }
    
    # If we have context_sources metadata, include which references were used
    context_sources2 = result2.get("context_sources", {})
    selected_refs2 = result2.get("selected_reference_ids") or result2.get("applied_reference_ids") or []
    if selected_refs2:
        details["new_facts_used"] = [{"reference_id": ref_id} for ref_id in selected_refs2[:10]]  # Limit to 10
    
    # If conflicts were resolved (delta is negative), try to identify them
    if conflicts_delta < 0:
        conflict_flags2 = result2.get("conflict_flags") or []
        if isinstance(conflict_flags2, list) and len(conflict_flags2) < conflicts1:
            # Some conflicts were resolved
            details["conflicts_resolved"] = [f"{len(conflict_flags2)} conflicts remaining (resolved {conflicts1 - len(conflict_flags2)})"]
    
    return jsonify({
        "job_id": job_id,
        "against": against_id,
        "deltas": {
            "conflicts_delta": conflicts_delta,
            "missing_fields_delta": missing_fields_delta,
            "unsupported_claims_delta": unsupported_claims_delta,
            "triples_added": triples_added,
            "triples_removed": triples_removed,
        },
        "details": details,
    }), 200
