"""
Job management API endpoints for reprocessing and versioning.

Provides endpoints for:
- Reprocessing jobs with new knowledge references
- Comparing job versions (diff endpoint)
- Getting conflict reports
"""

import threading
from typing import Dict, Any, List, Optional, Set
from flask import Blueprint, request, jsonify

from ..job_manager import create_job, get_job
from ..job_store import get_job_record, update_job_record, get_conflict_report
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
            "reprocess_reason": str (optional)
        }
    
    Response:
        {
            "job_id": "new-job-uuid",
            "status": "QUEUED"
        }
    
    Errors:
        404: Job not found
        400: Invalid request
        503: Database unavailable
    """
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    data = request.json or {}
    reference_ids = data.get("reference_ids", [])
    reprocess_reason = data.get("reprocess_reason")
    
    if not isinstance(reference_ids, list):
        return jsonify({"error": "reference_ids must be a list"}), 400
    
    # Get initial state from job record
    record = get_job_record(job_id) or {}
    initial_state = record.get("initial_state") or {}
    
    if not initial_state:
        return jsonify({"error": "Job initial state not found"}), 404
    
    # Create new job with updated reference IDs
    from ..job_manager import create_job
    parent_job_id = job_id
    job_version = _get_job_version(job_id) + 1
    
    new_job_id = create_job(
        initial_state,
        parent_job_id=parent_job_id,
        job_version=job_version,
        reprocess_reason=reprocess_reason,
        applied_reference_ids=reference_ids,
    )
    
    # Start workflow (import here to avoid circular dependency)
    from ..server import _run_workflow_async
    import threading
    
    thread = threading.Thread(
        target=_run_workflow_async,
        args=(new_job_id, initial_state),
        daemon=True
    )
    thread.start()
    
    telemetry_emitter.emit_event("job_reprocessed", {
        "parent_job_id": parent_job_id,
        "new_job_id": new_job_id,
        "reference_ids": reference_ids,
    })
    
    return jsonify({
        "job_id": new_job_id,
        "status": JobStatus.QUEUED.value
    }), 202


@jobs_bp.route("/<job_id>/conflict-report", methods=["GET"])
def get_conflict_report(job_id: str):
    """Get conflict report for a job.
    
    Response:
        {
            "report_id": str,
            "conflict_items": [
                {
                    "conflict_id": str,
                    "summary": str,
                    "details": str,
                    "evidence_anchors": [SourcePointer, ...],
                    ...
                }
            ],
            ...
        }
    
    Errors:
        404: Job or conflict report not found
    """
    record = get_job_record(job_id)
    if not record:
        return jsonify({"error": "Job not found"}), 404
    
    conflict_report_id = record.get("conflict_report_id")
    if not conflict_report_id:
        return jsonify({"error": "No conflict report found for this job"}), 404
    
    conflict_report = get_conflict_report(conflict_report_id)
    if not conflict_report:
        return jsonify({"error": "Conflict report not found"}), 404
    
    # Remove ArangoDB internal fields
    conflict_report.pop("_id", None)
    conflict_report.pop("_key", None)
    conflict_report.pop("_rev", None)
    
    return jsonify(conflict_report), 200


def _calculate_triple_delta(triples1: List[Dict[str, Any]], triples2: List[Dict[str, Any]]) -> tuple[int, int, List[Dict], List[Dict]]:
    """Calculate delta between two triple lists.
    
    Returns:
        (added_count, removed_count, added_triples, removed_triples)
    """
    # Create normalized keys for comparison
    def make_key(t: Dict[str, Any]) -> str:
        return f"{t.get('subject', '')}|{t.get('predicate', '')}|{t.get('object', '')}"
    
    keys1 = {make_key(t) for t in triples1 if isinstance(t, dict)}
    keys2 = {make_key(t) for t in triples2 if isinstance(t, dict)}
    
    added_keys = keys2 - keys1
    removed_keys = keys1 - keys2
    
    added_triples = [t for t in triples2 if isinstance(t, dict) and make_key(t) in added_keys]
    removed_triples = [t for t in triples1 if isinstance(t, dict) and make_key(t) in removed_keys]
    
    return len(added_keys), len(removed_keys), added_triples, removed_triples


def _count_conflicts(result: Dict[str, Any]) -> int:
    """Count conflicts in a job result."""
    conflict_flags = result.get("conflict_flags", [])
    if isinstance(conflict_flags, list):
        return len(conflict_flags)
    return 0


def _count_unsupported_claims(result: Dict[str, Any]) -> int:
    """Count unsupported claims (triples without evidence)."""
    extracted_json = result.get("extracted_json", {})
    if not isinstance(extracted_json, dict):
        return 0
    
    triples = extracted_json.get("triples", [])
    if not isinstance(triples, list):
        return 0
    
    unsupported_count = 0
    for triple in triples:
        if not isinstance(triple, dict):
            continue
        source_pointer = triple.get("source_pointer") or {}
        evidence = triple.get("evidence", "")
        # Consider unsupported if no source_pointer and no evidence
        if not source_pointer.get("doc_hash") and not evidence:
            unsupported_count += 1
    
    return unsupported_count


def _count_missing_fields(result: Dict[str, Any]) -> int:
    """Count triples missing required fields (subject, predicate, object)."""
    extracted_json = result.get("extracted_json", {})
    if not isinstance(extracted_json, dict):
        return 0
    
    triples = extracted_json.get("triples", [])
    if not isinstance(triples, list):
        return 0
    
    missing_count = 0
    for triple in triples:
        if not isinstance(triple, dict):
            continue
        subject = triple.get("subject", "").strip()
        predicate = triple.get("predicate", "").strip()
        obj = triple.get("object", "").strip()
        
        if not subject or not predicate or not obj:
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


@jobs_bp.route("/<job_id>/events", methods=["GET"])
def get_job_events(job_id: str):
    """Get node execution events for a job.
    
    Response:
        {
            "events": [
                {
                    "node_name": str,
                    "duration_ms": float,
                    "status": "success" | "error" | "pending",
                    "timestamp": str (ISO),
                    "job_id": str,
                    "project_id": str (optional),
                    "metadata": dict (optional)
                }
            ]
        }
    
    Errors:
        404: Job not found
    """
    from ..telemetry import TelemetryEmitter, DEFAULT_SINK
    from pathlib import Path
    import json
    
    # Verify job exists
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    # Read telemetry events from JSONL file
    telemetry_path = Path(DEFAULT_SINK)
    events: List[Dict[str, Any]] = []
    
    if telemetry_path.exists():
        try:
            # Read last 1000 lines to find events for this job
            with telemetry_path.open("rb") as fh:
                fh.seek(0, 2)
                file_size = fh.tell()
                fh.seek(max(file_size - 200_000, 0))  # ~200KB tail
                data = fh.read().decode("utf-8", errors="ignore")
            
            lines = data.strip().splitlines()[-1000:]
            for line in lines:
                try:
                    evt = json.loads(line)
                    # Filter for node_execution events for this job
                    if (
                        evt.get("event_type") == "node_execution"
                        and evt.get("job_id") == job_id
                    ):
                        events.append({
                            "node_name": evt.get("node_name", "unknown"),
                            "duration_ms": evt.get("duration_ms", 0),
                            "status": "error" if evt.get("metadata", {}).get("error") else "success",
                            "timestamp": evt.get("timestamp", ""),
                            "job_id": evt.get("job_id"),
                            "project_id": evt.get("project_id"),
                            "metadata": evt.get("metadata", {}),
                        })
                except Exception:
                    continue
            
            # Sort by timestamp (newest first)
            events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        except Exception as exc:
            logger.warning(f"Failed to read telemetry events: {exc}", exc_info=True)
    
    return jsonify({"events": events}), 200
