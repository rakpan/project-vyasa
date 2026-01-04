"""
Telemetry package for OpikEmitter and related utilities.

This package exists alongside telemetry.py. To avoid conflicts,
we re-export functions from telemetry.py here.
"""

from .opik_emitter import get_opik_emitter, OpikEmitter

# Import from parent telemetry.py file using importlib to avoid circular imports
import importlib.util
import sys
from pathlib import Path

_telemetry_file = Path(__file__).parent.parent / "telemetry.py"
if _telemetry_file.exists():
    spec = importlib.util.spec_from_file_location("_telemetry_file_module", _telemetry_file)
    _telemetry_file_module = importlib.util.module_from_spec(spec)
    # Set parent package to avoid relative import issues
    _telemetry_file_module.__package__ = "src.orchestrator"
    spec.loader.exec_module(_telemetry_file_module)
    extract_usage_from_response = _telemetry_file_module.extract_usage_from_response
    TelemetryEmitter = _telemetry_file_module.TelemetryEmitter
    trace_node = _telemetry_file_module.trace_node
else:
    # Fallback - these won't work but at least the import won't fail
    extract_usage_from_response = None
    TelemetryEmitter = None
    trace_node = None

__all__ = ["get_opik_emitter", "OpikEmitter", "extract_usage_from_response", "TelemetryEmitter", "trace_node"]

