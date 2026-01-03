"""Package for workflow nodes and re-exports.

This package provides node functions from nodes.py and re-exports tone_guard utilities.
"""

import importlib
import logging

# Import directly from the local nodes.py module
from .nodes import (
    cartographer_node,
    critic_node,
    reframing_node,
    artifact_registry_node,
    tone_validator_node,
    saver_node,
    synthesizer_node,
    vision_node,
    lead_counsel_node,
    logician_node,
    route_to_expert,
    call_expert_with_fallback,
    ExpertType,
    NODE_EXPERT_MAP,
    failure_cleanup_node,
    select_images_for_vision,
    # Internal symbols for test mocking compatibility (imported in nodes.py)
    requests,
    ArangoClient,
    interrupt,
    _build_conflict_report,
    telemetry_emitter,  # Module-level telemetry emitter instance
)

# Import functions that are imported in nodes.py from other modules
# These need to be imported directly for test compatibility
from ...shared.config import get_worker_url, get_vision_url
from ..normalize import normalize_extracted_json
from ..artifacts.manifest_builder import build_manifest, persist_manifest
from ...shared.rigor_config import load_rigor_policy_yaml
from ..guards.tone_guard import scan_text
from ..guards.tone_rewrite import rewrite_to_neutral
from ..job_store import store_reframing_proposal
from ..job_manager import update_job_status
from .nodes import hydrate_project_context
from .base import wrap_prompt_with_context

# Cache for tone_guard module (lazy loading)
_tone_guard_cache = None

def __getattr__(name):
    """Lazy import pattern for tone_guard and other dynamic exports."""
    global _tone_guard_cache
    # Explicitly use global importlib to avoid scoping ambiguity
    import importlib as _importlib
    
    if name == "tone_guard":
        if _tone_guard_cache is None:
            _tone_guard_cache = _importlib.import_module("src.orchestrator.tone_guard")
        return _tone_guard_cache
    
    raise AttributeError(f"module {__name__} has no attribute {name}")

# Explicitly define the package's public API
__all__ = [
    "cartographer_node",
    "critic_node",
    "reframing_node",
    "artifact_registry_node",
    "tone_validator_node",
    "saver_node",
    "synthesizer_node",
    "vision_node",
    "lead_counsel_node",
    "logician_node",
    "route_to_expert",
    "call_expert_with_fallback",
    "ExpertType",
    "NODE_EXPERT_MAP",
    "failure_cleanup_node",
    "select_images_for_vision",
    # Internal symbols for test mocking compatibility
    "requests",
    "ArangoClient",
    "interrupt",
    "load_rigor_policy_yaml",
    "get_worker_url",
    "_build_conflict_report",
    "normalize_extracted_json",
    "build_manifest",
    "persist_manifest",
    "scan_text",
    "rewrite_to_neutral",
    "get_vision_url",
    "store_reframing_proposal",
    "update_job_status",
    "telemetry_emitter",
    "hydrate_project_context",
    "wrap_prompt_with_context",
]
