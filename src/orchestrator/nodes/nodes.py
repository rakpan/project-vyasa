"""
Compatibility shim for workflow nodes.

This module provides:
1. Shared utilities used across node modules (validate_state_schema, hydrate_project_context, etc.)
2. Infrastructure functions (route_to_expert, call_expert_with_fallback)
3. Re-exports of all node functions from their respective modules

Node implementations are organized by domain:
- cartography.py: Knowledge extraction (cartographer_node)
- quality.py: Governance and validation (critic_node, reframing_node, tone_validator_node)
- synthesis.py: Manuscript generation (synthesizer_node, lead_counsel_node, logician_node)
- export.py: Persistence (saver_node, artifact_registry_node)
- utils.py: Cross-cutting utilities (vision_node)
- base.py: Shared prompt wrappers (wrap_prompt_with_context)
"""

from typing import Dict, Any, List, Optional
import time
import re
import requests

from arango import ArangoClient
from langgraph.types import interrupt

from ...shared.config import (
    get_worker_url,
    get_brain_url,
    get_vision_url,
    get_memory_url,
    get_arango_password,
    ARANGODB_DB,
    ARANGODB_USER,
)
from ...shared.model_registry import get_model_config
from ...shared.logger import get_logger
from ...shared.llm_client import chat
from ...shared.role_manager import RoleRegistry
from ...shared.utils import get_utc_now
from ..state import JobStatus, PhaseEnum, ResearchState
from ..telemetry import get_telemetry_emitter, trace_node
from ..config import ExpertType, NODE_EXPERT_MAP
from ..job_manager import update_job_status

logger = get_logger("orchestrator", __name__)
telemetry_emitter = get_telemetry_emitter()
role_registry = RoleRegistry()

# Lazy import to avoid circular dependencies
_project_service: Optional[Any] = None

# Backpressure thresholds
BACKPRESSURE_THRESHOLD_DELAY = 0.85
BACKPRESSURE_THRESHOLD_RETRY = 0.95


# ============================================================================
# Shared Utilities (used by multiple node modules)
# ============================================================================

def validate_state_schema(state: ResearchState) -> ResearchState:
    """Ensure required control keys exist before node execution.
    
    Preserves all state fields including raw_text, pdf_path, and any unknown fields.
    This defensive preservation ensures that fields are not dropped during state validation.
    """
    job_id = state.get("jobId") or state.get("job_id")
    thread_id = state.get("threadId") or state.get("thread_id")
    if not job_id:
        raise ValueError("ResearchState missing required field: jobId")
    if not thread_id:
        raise ValueError("ResearchState missing required field: threadId")
    # Normalize keys so downstream nodes can rely on camelCase
    # Preserve ALL fields from input state (defensive preservation)
    normalized = {**state}
    normalized["jobId"] = job_id
    normalized["threadId"] = thread_id
    
    # Debug logging for raw_text preservation
    raw_text_len = len(state.get("raw_text", "")) if state.get("raw_text") else 0
    logger.debug(
        "State schema validated",
        extra={
            "payload": {
                "job_id": job_id,
                "state_keys": list(state.keys()),
                "raw_text_length": raw_text_len,
                "has_raw_text": "raw_text" in state,
                "has_pdf_path": "pdf_path" in state,
            }
        }
    )
    
    return normalized  # type: ignore[return-value]


def _get_project_service() -> Optional[Any]:
    """Get ProjectService instance (lazy import to avoid circular dependencies).
    
    Returns:
        ProjectService instance if available, None if DB unavailable.
    """
    global _project_service
    if _project_service is None:
        try:
            # Lazy imports to avoid circular dependencies
            from ...project.service import ProjectService
            arango_url = get_memory_url()
            arango_db = ARANGODB_DB
            arango_user = ARANGODB_USER
            arango_password = get_arango_password()
            
            client = ArangoClient(hosts=arango_url)
            db = client.db(arango_db, username=arango_user, password=arango_password)
            # Do not create DBs/collections here; assume pre-provisioned (matches server.py behavior)
            _project_service = ProjectService(db)
            logger.debug("ProjectService initialized in nodes module (no DB creation)")
        except Exception as e:
            logger.warning(f"Failed to initialize ProjectService in nodes: {e}")
            _project_service = None
    return _project_service


def hydrate_project_context(state: ResearchState) -> ResearchState:
    """Hydrate project context from project_id if missing.
    
    Ensures project_context is available in state as a JSON-serializable dict.
    If project_id exists but project_context is missing, fetches from ProjectService
    and stores model_dump() into state.
    
    Args:
        state: ResearchState that may contain project_id.
    
    Returns:
        Updated ResearchState with project_context populated if project_id was present.
    
    Raises:
        ValueError: If project_id is provided but project not found.
        RuntimeError: If project_id is provided but DB is unavailable.
    """
    project_id = state.get("project_id")
    
    # If no project_id, return state unchanged
    if not project_id:
        return state
    
    # If project_context already exists, return state unchanged
    if state.get("project_context"):
        return state
    
    # Fetch project config
    project_service = _get_project_service()
    if project_service is None:
        raise RuntimeError("ProjectService unavailable: cannot fetch project context")
    
    try:
        from ...project.types import ProjectConfig
        project = project_service.get_project(project_id)
        
        hydrated = {**state, "project_context": project.model_dump()}
        logger.info(f"Hydrated project context for project_id={project_id}")
        
        return hydrated
    except ValueError as e:
        # Project not found
        raise ValueError(f"Project not found: {project_id}") from e
    except Exception as e:
        # Other errors (DB unavailable, etc.)
        logger.error(f"Failed to hydrate project context for {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Failed to fetch project context: {e}") from e


def _parse_kv_utilization(metrics_text: str) -> Optional[float]:
    """Extract kv cache utilization from Prometheus exposition text."""
    for line in metrics_text.splitlines():
        if "kv_cache_utilization" in line or "kv_cache_fill" in line or "kv_cache_usage" in line:
            match = re.search(r"([0-9]+\.?[0-9]*)", line)
            if match:
                try:
                    value = float(match.group(1))
                    # Some metrics are 0-100, others 0-1
                    return value / 100.0 if value > 1 else value
                except ValueError:
                    continue
    return None


def check_kv_backpressure(expert_url: str):
    """Query SGLang metrics and decide whether to proceed, delay, or retry later."""
    try:
        resp = requests.get(f"{expert_url}/metrics", timeout=2)
        resp.raise_for_status()
        utilization = _parse_kv_utilization(resp.text)
        if utilization is None:
            return {"action": "proceed", "utilization": 0.0, "reason": "kv_cache_utilization_not_found"}
    except Exception as exc:  # noqa: BLE001
        return {"action": "proceed", "utilization": 0.0, "reason": f"metrics_unavailable:{exc}"}

    if utilization >= BACKPRESSURE_THRESHOLD_RETRY:
        return {"action": "retry_later", "utilization": utilization, "reason": "kv_cache>95%"}
    if utilization >= BACKPRESSURE_THRESHOLD_DELAY:
        time.sleep(0.2)
        return {"action": "delay", "utilization": utilization, "reason": "kv_cache>85%"}
    return {"action": "proceed", "utilization": utilization, "reason": "ok"}


def route_to_expert(node_name: str, node_type: str = "auto") -> tuple[str, str, str]:
    """Route a node to the appropriate expert service.
    
    Args:
        node_name: Name of the node function (e.g., "cartographer_node", "critic_node")
        node_type: Explicit expert type, or "auto" to infer from node_name
        
    Returns:
        Tuple of (expert_url, expert_name, model_id) for the appropriate expert service.
        expert_name is a human-readable identifier for logging/telemetry.
    """
    # Infer node type from name if auto
    if node_type == "auto":
        node_type = NODE_EXPERT_MAP.get(node_name, ExpertType.EXTRACTION_SCHEMA)
    
    # Route to appropriate expert
    if node_type == ExpertType.LOGIC_REASONING:
        return get_brain_url(), "Brain", get_model_config("brain").model_id
    elif node_type == ExpertType.EXTRACTION_SCHEMA:
        return get_worker_url(), "Worker", get_model_config("worker").model_id
    elif node_type == ExpertType.PROSE_WRITING:
        # Route prose writing to TEXT model (Brain) with draft prompt profile
        # Note: Prompt profile selection happens in the calling code, not here
        return get_brain_url(), "Brain", get_model_config("brain").model_id
    elif node_type == ExpertType.VISION:
        return get_vision_url(), "Vision", get_model_config("vision").model_id
    else:
        # Fallback to Worker
        return get_worker_url(), "Worker", get_model_config("worker").model_id


def call_expert_with_fallback(
    expert_url: str,
    expert_name: str,
    model_id: str,
    prompt: List[Dict[str, Any]],
    request_params: Dict[str, Any],
    fallback_url: Optional[str] = None,
    fallback_model_id: Optional[str] = None,
    node_name: str = "unknown",
    state: Optional[Dict[str, Any]] = None,
    allowed_tools: Optional[list] = None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Call an expert service with automatic retry/fallback via llm_client.chat."""
    data, meta = chat(
        primary_url=expert_url,
        model=model_id,
        messages=prompt,
        request_params=request_params,
        state=state,
        node_name=node_name,
        expert_name=expert_name,
        fallback_url=fallback_url,
        fallback_model=fallback_model_id,
        fallback_expert_name="Brain",
        allowed_tools=allowed_tools,
    )
    logger.debug(
        "Expert call completed",
        extra={
            "payload": {
                "node_name": node_name,
                "expert": meta.get("expert_name"),
                "path": meta.get("path"),
                "url": meta.get("url_base"),
            }
        },
    )
    return data, meta


# ============================================================================
# Node Functions (re-exported from domain modules)
# ============================================================================

# Re-export all node functions from their respective modules
# These imports are deferred to avoid circular dependencies at module level
# The __init__.py handles the actual imports for public API

# Cartography
from .cartography import cartographer_node

# Quality/Governance
# (imported in __init__.py to avoid circular imports)

# Synthesis
# (imported in __init__.py to avoid circular imports)

# Export/Persistence
# (imported in __init__.py to avoid circular imports)

# Utils
from .utils import vision_node, select_images_for_vision


# ============================================================================
# Infrastructure Nodes
# ============================================================================

@trace_node
def failure_cleanup_node(state: ResearchState) -> ResearchState:
    """Terminal failure handler that marks the job failed and emits telemetry."""
    job_id = state.get("job_id")
    error_msg = state.get("error") or state.get("critic_status") or "Workflow failed"
    try:
        if job_id:
            update_job_status(job_id, JobStatus.FAILED, current_step="failure_cleanup", error=str(error_msg), message="Failure cleanup")
    except Exception as exc:  # noqa: BLE001
        logger.error("Unable to mark job failed during cleanup", extra={"payload": {"job_id": job_id, "error": str(exc)}})
    telemetry_emitter.emit_event(
        "system_failure",
        {
            "job_id": job_id,
            "node_name": "failure_cleanup",
            "timestamp": get_utc_now().isoformat(),
            "error": str(error_msg),
        },
    )
    return {"status": "fail"}
