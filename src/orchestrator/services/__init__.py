"""
Service modules for orchestrator business logic.

These modules contain pure business logic extracted from server.py,
with no Flask dependencies, making them testable and reusable.
"""

from .events import (
    notify_sse_clients,
    publish_event,
    get_event_queue,
    reset_events,
)
from .metrics import (
    calculate_quality_metrics,
    store_quality_metrics,
    emit_reprocess_completion_telemetry,
)
from .triples import (
    extract_nodes_from_triples,
    extract_edges_from_triples,
)
from .telemetry import (
    emit_reframe_event,
    get_telemetry_emitter,
)

__all__ = [
    # Events
    "notify_sse_clients",
    "publish_event",
    "get_event_queue",
    "remove_event_queue",
    "reset_events",
    # Metrics
    "calculate_quality_metrics",
    "store_quality_metrics",
    "emit_reprocess_completion_telemetry",
    # Triples
    "extract_nodes_from_triples",
    "extract_edges_from_triples",
    # Telemetry
    "emit_reframe_event",
    "get_telemetry_emitter",
]

