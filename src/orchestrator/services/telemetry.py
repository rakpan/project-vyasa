"""
Telemetry service wrappers for common event patterns.

Thin service layer around TelemetryEmitter for common telemetry patterns.
No routing logic, pure business logic.
"""

from typing import Optional

from ...shared.logger import get_logger
from ..telemetry import TelemetryEmitter

logger = get_logger("orchestrator", __name__)

# Singleton telemetry emitter instance
_telemetry_emitter: TelemetryEmitter | None = None


def get_telemetry_emitter() -> TelemetryEmitter:
    """Get or create singleton TelemetryEmitter instance.
    
    Returns:
        TelemetryEmitter instance.
    """
    global _telemetry_emitter
    if _telemetry_emitter is None:
        _telemetry_emitter = TelemetryEmitter()
    return _telemetry_emitter


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

