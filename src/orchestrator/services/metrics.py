"""
Quality metrics calculation and storage service.

Calculates quality metrics from job results, stores them in job records,
and emits telemetry for reprocessed jobs. No Flask dependencies.
"""

from typing import Dict, Any

from ...shared.logger import get_logger
from ...shared.utils import get_utc_now
from ..job_manager import get_job
from ..job_store import get_job_record, update_job_record
from ..telemetry import TelemetryEmitter

logger = get_logger("orchestrator", __name__)

# Singleton telemetry emitter instance
_telemetry_emitter: TelemetryEmitter | None = None


def _get_telemetry_emitter() -> TelemetryEmitter:
    """Get or create telemetry emitter instance."""
    global _telemetry_emitter
    if _telemetry_emitter is None:
        _telemetry_emitter = TelemetryEmitter()
    return _telemetry_emitter


def calculate_quality_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate quality metrics from a job result.
    
    Args:
        result: Job result dictionary
    
    Returns:
        Dictionary with quality metrics:
        - unsupported_claim_rate: float (0.0-1.0)
        - conflict_count: int
        - missing_fields_count: int
        - total_triples: int
        - unsupported_count: int
    """
    from ..api.jobs import _count_conflicts, _count_unsupported_claims, _count_missing_fields
    
    extracted_json = result.get("extracted_json", {})
    triples = extracted_json.get("triples", []) if isinstance(extracted_json, dict) else []
    total_triples = len(triples) if isinstance(triples, list) else 0
    
    conflict_count = _count_conflicts(result)
    missing_fields_count = _count_missing_fields(result)
    unsupported_count = _count_unsupported_claims(result)
    
    unsupported_claim_rate = (unsupported_count / total_triples) if total_triples > 0 else 0.0
    
    return {
        "unsupported_claim_rate": round(unsupported_claim_rate, 4),
        "conflict_count": conflict_count,
        "missing_fields_count": missing_fields_count,
        "total_triples": total_triples,
        "unsupported_count": unsupported_count,
    }


def store_quality_metrics(job_id: str, result: Dict[str, Any]) -> None:
    """Store quality metrics in job metadata, including comparison with parent if reprocessed.
    
    Args:
        job_id: Job identifier
        result: Job result dictionary
    """
    quality_metrics_after = calculate_quality_metrics(result)
    
    # Get job record to check if this is a reprocessed job
    record = get_job_record(job_id) or {}
    parent_job_id = record.get("parent_job_id")
    
    quality_metrics_before = None
    if parent_job_id:
        # Get parent job result to calculate metrics_before
        parent_job = get_job(parent_job_id)
        if parent_job and parent_job.get("result"):
            quality_metrics_before = calculate_quality_metrics(parent_job["result"])
    
    # Store metrics in job record
    update_job_record(job_id, {
        "quality_metrics_after": quality_metrics_after,
        "quality_metrics_before": quality_metrics_before,
    })
    
    logger.debug(
        f"Stored quality metrics for job {job_id}",
        extra={
            "payload": {
                "job_id": job_id,
                "quality_metrics_after": quality_metrics_after,
                "has_parent_metrics": quality_metrics_before is not None,
            }
        }
    )


def emit_reprocess_completion_telemetry(job_id: str, result: Dict[str, Any]) -> None:
    """Emit telemetry event when a reprocessed job completes.
    
    Args:
        job_id: Job identifier
        result: Job result dictionary
    """
    record = get_job_record(job_id) or {}
    parent_job_id = record.get("parent_job_id")
    
    if not parent_job_id:
        # Not a reprocessed job, skip telemetry
        return
    
    # Calculate quality deltas if parent metrics available
    quality_metrics_after = record.get("quality_metrics_after") or {}
    quality_metrics_before = record.get("quality_metrics_before")
    
    quality_deltas = None
    if quality_metrics_before:
        quality_deltas = {
            "unsupported_claim_rate_delta": quality_metrics_after.get("unsupported_claim_rate", 0.0) - quality_metrics_before.get("unsupported_claim_rate", 0.0),
            "conflict_count_delta": quality_metrics_after.get("conflict_count", 0) - quality_metrics_before.get("conflict_count", 0),
            "missing_fields_count_delta": quality_metrics_after.get("missing_fields_count", 0) - quality_metrics_before.get("missing_fields_count", 0),
            "triples_count_delta": quality_metrics_after.get("total_triples", 0) - quality_metrics_before.get("total_triples", 0),
        }
    
    emitter = _get_telemetry_emitter()
    emitter.emit_event(
        "job_reprocess_completed",
        {
            "parent_job_id": parent_job_id,
            "new_job_id": job_id,
            "timestamp": get_utc_now().isoformat(),
            "quality_deltas": quality_deltas,
            "quality_metrics_after": quality_metrics_after,
        },
    )

