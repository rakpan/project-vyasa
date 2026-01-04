"""
Telemetry service wrappers for common event patterns.

Thin service layer around TelemetryEmitter for common telemetry patterns.
No routing logic, pure business logic.
"""

from typing import Optional

from ...shared.logger import get_logger
from ..telemetry import get_telemetry_emitter as _get_telemetry_emitter

logger = get_logger("orchestrator", __name__)


def get_telemetry_emitter():
    """Get singleton TelemetryEmitter instance (delegates to centralized factory).
    
    This function is kept for backward compatibility but now delegates to
    the centralized factory in telemetry.py to ensure a single singleton.
    
    Returns:
        TelemetryEmitter singleton instance.
    """
    return _get_telemetry_emitter()


def emit_reframe_event(
    event_type: str,
    proposal_id: str,
    job_id: str,
    thread_id: Optional[str] = None,
) -> None:
    """Emit a reframe-related telemetry event.
    
    Args:
        event_type: Event type ("reframe_accepted" or "reframe_rejected")
        proposal_id: Reframing proposal identifier
        job_id: Job identifier
        thread_id: Optional thread identifier (for accepted events)
    """
    emitter = get_telemetry_emitter()
    
    payload: dict = {
        "proposal_id": proposal_id,
        "job_id": job_id,
    }
    
    if thread_id:
        payload["thread_id"] = thread_id
    
    emitter.emit_event(event_type, payload)

