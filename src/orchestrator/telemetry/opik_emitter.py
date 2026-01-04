"""
OpikEmitter: First-class "Control Room" tracing for Vyasa.

Emits structured traces to Opik including:
- Node start/end events
- Prompt metadata (from prompt_manifest)
- Schema validation results
- Key counts (claims, conflicts, blocks)
- Deterministic validator outcomes

All emissions are safe: timeouts respected, exceptions do not break workflow.
"""

from typing import Dict, Any, Optional
import requests

from ...shared.logger import get_logger
from ...shared.config import (
    OPIK_ENABLED,
    OPIK_BASE_URL,
    OPIK_API_KEY,
    OPIK_PROJECT_NAME,
    OPIK_TIMEOUT_SECONDS,
)
from ...shared.utils import get_utc_now

logger = get_logger("orchestrator", __name__)


class OpikEmitter:
    """Opik tracing emitter for Vyasa workflow execution.
    
    Provides structured emission of node execution events, prompt metadata,
    validation results, and key metrics to Opik for observability.
    
    All methods are no-op if OPIK_ENABLED=false. All emissions are best-effort
    and never raise exceptions that could break workflow execution.
    """
    
    def __init__(self):
        """Initialize OpikEmitter (lazy client initialization)."""
        self._client: Optional[Dict[str, Any]] = None
        self._enabled = OPIK_ENABLED and bool(OPIK_BASE_URL)
    
    def _get_client(self) -> Optional[Dict[str, Any]]:
        """Get Opik client config (lazy initialization)."""
        if not self._enabled:
            return None
        
        if self._client is None:
            self._client = {
                "base_url": OPIK_BASE_URL.rstrip("/"),
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPIK_API_KEY}" if OPIK_API_KEY else "",
                },
                "timeout": OPIK_TIMEOUT_SECONDS,
                "project": OPIK_PROJECT_NAME,
            }
        
        return self._client
    
    def _safe_post(self, url: str, payload: Dict[str, Any]) -> None:
        """Safely POST to Opik API, swallowing all exceptions.
        
        Args:
            url: Opik API endpoint URL
            payload: Payload to send
        """
        client = self._get_client()
        if not client:
            return
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=client["headers"],
                timeout=client["timeout"],
            )
            response.raise_for_status()
        except requests.Timeout:
            logger.debug(f"Opik POST timeout (ignored): {url}", extra={"payload": {"timeout": client["timeout"]}})
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug(f"Opik POST failed (ignored): {exc}", exc_info=True, extra={"payload": {"url": url, "error": str(exc)}})
    
    def emit_node_start(
        self,
        job_id: str,
        project_id: Optional[str],
        node_name: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit node start event to Opik.
        
        Args:
            job_id: Job identifier
            project_id: Project identifier (optional)
            node_name: Name of the node (e.g., "cartographer", "critic")
            meta: Optional metadata (rigor_level, prompt_manifest, etc.)
        """
        if not self._enabled:
            return
        
        client = self._get_client()
        if not client:
            return
        
        try:
            payload = {
                "project": client["project"],
                "run_type": "node_start",
                "metadata": {
                    "job_id": job_id,
                    "project_id": project_id,
                    "node_name": node_name,
                    "timestamp": get_utc_now().isoformat(),
                    **(meta or {}),
                },
            }
            
            url = f"{client['base_url']}/api/traces"
            self._safe_post(url, payload)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Opik node_start emission failed (ignored): {exc}", exc_info=True)
    
    def emit_node_end(
        self,
        job_id: str,
        project_id: Optional[str],
        node_name: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit node end event to Opik.
        
        Args:
            job_id: Job identifier
            project_id: Project identifier (optional)
            node_name: Name of the node
            meta: Optional metadata (duration_ms, success, counts, prompt_manifest, etc.)
        """
        if not self._enabled:
            return
        
        client = self._get_client()
        if not client:
            return
        
        try:
            # Extract key counts from meta if present
            counts = {}
            if meta:
                extracted = meta.get("extracted_json") or {}
                if isinstance(extracted, dict):
                    triples = extracted.get("triples", [])
                    if isinstance(triples, list):
                        counts["claims_count"] = len(triples)
                
                conflicts = meta.get("conflicts", [])
                if isinstance(conflicts, list):
                    counts["conflicts_count"] = len(conflicts)
                
                blocks = meta.get("manuscript_blocks", [])
                if isinstance(blocks, list):
                    counts["blocks_count"] = len(blocks)
            
            # Extract prompt metadata from prompt_manifest
            prompt_meta = {}
            if meta and meta.get("prompt_manifest"):
                prompt_manifest = meta["prompt_manifest"]
                if isinstance(prompt_manifest, dict) and node_name in prompt_manifest:
                    prompt_meta = prompt_manifest[node_name]
            
            payload = {
                "project": client["project"],
                "run_type": "node_end",
                "metadata": {
                    "job_id": job_id,
                    "project_id": project_id,
                    "node_name": node_name,
                    "timestamp": get_utc_now().isoformat(),
                    "counts": counts,
                    "prompt_metadata": prompt_meta,
                    **(meta or {}),
                },
            }
            
            url = f"{client['base_url']}/api/traces"
            self._safe_post(url, payload)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Opik node_end emission failed (ignored): {exc}", exc_info=True)
    
    def emit_validation(
        self,
        job_id: str,
        project_id: Optional[str],
        kind: str,
        result_meta: Dict[str, Any],
    ) -> None:
        """Emit validation result to Opik.
        
        Args:
            job_id: Job identifier
            project_id: Project identifier (optional)
            kind: Validation kind (e.g., "schema", "citation_integrity", "tone_guard")
            result_meta: Validation result metadata (pass/fail, findings_count, etc.)
        """
        if not self._enabled:
            return
        
        client = self._get_client()
        if not client:
            return
        
        try:
            payload = {
                "project": client["project"],
                "run_type": "validation",
                "metadata": {
                    "job_id": job_id,
                    "project_id": project_id,
                    "validation_kind": kind,
                    "timestamp": get_utc_now().isoformat(),
                    **result_meta,
                },
            }
            
            url = f"{client['base_url']}/api/traces"
            self._safe_post(url, payload)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Opik validation emission failed (ignored): {exc}", exc_info=True)


# Global singleton instance
_opik_emitter: Optional[OpikEmitter] = None


def get_opik_emitter() -> OpikEmitter:
    """Get global OpikEmitter singleton instance.
    
    Returns:
        OpikEmitter instance (no-op if Opik disabled)
    """
    global _opik_emitter
    if _opik_emitter is None:
        _opik_emitter = OpikEmitter()
    return _opik_emitter

