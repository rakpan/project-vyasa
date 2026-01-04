"""
Lightweight telemetry emitter for workflow breadcrumbs.

Events are appended to a local JSONL sink so downstream processors
can tail and fan-out without impacting workflow execution.
"""

from __future__ import annotations

import json
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..shared.logger import get_logger
from ..shared.utils import get_utc_now
from ..shared.config import TELEMETRY_PATH as TELEMETRY_PATH_ENV
from ..shared import opik_client
from .telemetry.opik_emitter import get_opik_emitter

logger = get_logger("telemetry", __name__)

DEFAULT_SINK = Path(TELEMETRY_PATH_ENV)


def _safe_usage_dict(candidate: Any) -> Optional[Dict[str, Any]]:
    """Normalize a usage/metadata blob into a dict if present."""
    if not isinstance(candidate, dict):
        return None
    usage = candidate.get("usage") or candidate.get("usage_info")
    if isinstance(usage, dict):
        return usage
    meta = candidate.get("meta") if isinstance(candidate, dict) else None
    if isinstance(meta, dict):
        nested_usage = meta.get("usage") or meta.get("usage_info")
        if isinstance(nested_usage, dict):
            return nested_usage
    return candidate if any(k in candidate for k in ("prompt_tokens", "completion_tokens", "total_tokens")) else None


def extract_usage_from_response(payload: Any) -> Optional[Dict[str, Any]]:
    """Extract token usage from a model response payload if present."""
    if not isinstance(payload, dict):
        return None
    # Common SGLang/OpenAI-style usage shapes
    for key in ("usage", "usage_info", "_sglang_usage", "_sglang_metadata", "response_metadata"):
        if key in payload and isinstance(payload.get(key), dict):
            return payload[key]
    # Meta wrapper
    meta_usage = _safe_usage_dict(payload)
    if meta_usage:
        return meta_usage
    return None


def _extract_tokens(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pull token counts from known state slots."""
    usage = None
    for key in ("_sglang_usage", "_sglang_metadata", "sglang_metadata", "usage"):
        value = state.get(key)
        if isinstance(value, dict):
            usage = value
            break
    if usage is None:
        meta = state.get("meta") if isinstance(state.get("meta"), dict) else None
        if meta:
            maybe_usage = meta.get("usage") or meta.get("usage_info")
            if isinstance(maybe_usage, dict):
                usage = maybe_usage
    if not isinstance(usage, dict):
        return None
    tokens = {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens") if usage.get(k) is not None}
    return tokens or None


def _extract_doc_pointer(state: Dict[str, Any]) -> tuple[Optional[str], Optional[int]]:
    """Best-effort doc_hash/page extraction from state payloads."""
    doc_hash = state.get("doc_hash")
    page: Optional[int] = None

    extracted = state.get("extracted_json") if isinstance(state.get("extracted_json"), dict) else {}
    claims = extracted.get("claims") or []
    if isinstance(claims, list):
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            pointer = claim.get("source_pointer") or {}
            if isinstance(pointer, dict):
                if doc_hash is None:
                    doc_hash = claim.get("doc_hash") or pointer.get("doc_hash")
                if page is None and pointer.get("page") is not None:
                    page = pointer.get("page")
            if doc_hash and page is not None:
                break
    return doc_hash, page


class TelemetryEmitter:
    """Append-only telemetry emitter with JSONL sink."""

    def __init__(self, filepath: Path | str = DEFAULT_SINK):
        self.filepath = Path(filepath)

    def emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Append an event to the JSONL sink, swallowing errors."""
        event = dict(data)
        event["event_type"] = event_type
        event.setdefault("timestamp", get_utc_now().isoformat())
        event.setdefault("metadata", {})
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with self.filepath.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover - telemetry should not break workflow
            logger.warning("Failed to emit telemetry event", extra={"payload": {"error": str(exc), "event_type": event_type}})


def trace_node(func: Callable) -> Callable:
    """Decorator to emit node_execution breadcrumbs around LangGraph nodes."""
    emitter = TelemetryEmitter()
    opik_emitter = get_opik_emitter()

    @wraps(func)
    def wrapper(state: Dict[str, Any], *args: Any, **kwargs: Any):
        start = time.perf_counter()
        start_ts = get_utc_now().isoformat()
        result: Optional[Dict[str, Any]] = None
        error: Optional[str] = None
        
        # Extract job_id and project_id for Opik tracing
        job_id = state.get("job_id") or state.get("jobId")
        project_id = state.get("project_id")
        node_name = func.__name__
        
        # Emit node start to Opik
        try:
            rigor_level = state.get("rigor_level") or (state.get("project_context") or {}).get("rigor_level", "exploratory")
            prompt_manifest = state.get("prompt_manifest", {})
            opik_emitter.emit_node_start(
                job_id=job_id or "",
                project_id=project_id,
                node_name=node_name,
                meta={
                    "rigor_level": rigor_level,
                    "prompt_manifest": prompt_manifest,
                },
            )
        except Exception:  # pragma: no cover - Opik must be non-blocking
            pass
        
        try:
            result = func(state, *args, **kwargs)
            return result
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            payload = result if isinstance(result, dict) else state if isinstance(state, dict) else {}
            metadata: Dict[str, Any] = {}

            tokens = _extract_tokens(payload)
            if tokens:
                metadata["tokens"] = tokens

            if any(key in node_name.lower() for key in ("cartographer", "worker", "critic")):
                doc_hash, page = _extract_doc_pointer(payload)
                if doc_hash:
                    metadata["doc_hash"] = doc_hash
                if page is not None:
                    metadata["page"] = page

            # Extract expert information from state metadata (set by routing functions)
            expert = payload.get("_expert_name")
            expert_url = payload.get("_expert_url")
            if expert:
                metadata["expert"] = expert
            if expert_url:
                metadata["expert_url"] = expert_url

            if error:
                metadata["error"] = error

            emitter.emit_event(
                "node_execution",
                {
                    "job_id": job_id,
                    "project_id": project_id,
                    "node_name": node_name,
                    "timestamp": start_ts,
                    "duration_ms": duration_ms,
                    "metadata": metadata,
                },
            )

            # Emit node end to Opik with comprehensive metadata
            try:
                # Extract counts
                extracted = payload.get("extracted_json") or {}
                triples_count = len(extracted.get("triples", [])) if isinstance(extracted, dict) else 0
                critiques_count = len(payload.get("critiques", [])) if isinstance(payload.get("critiques"), list) else 0
                blocks_count = len(payload.get("manuscript_blocks", [])) if isinstance(payload.get("manuscript_blocks"), list) else 0
                conflicts_count = len(payload.get("conflicts", [])) if isinstance(payload.get("conflicts"), list) else 0
                
                # Extract validation results
                validation_results = {}
                tone_findings = payload.get("tone_findings", [])
                if isinstance(tone_findings, list):
                    validation_results["tone_findings_count"] = len(tone_findings)
                
                # Citation integrity validation (from synthesizer)
                synthesis_error = payload.get("synthesis_error")
                if synthesis_error and "citation integrity" in synthesis_error.lower():
                    validation_results["citation_integrity"] = "fail"
                elif node_name == "synthesizer" and not synthesis_error:
                    validation_results["citation_integrity"] = "pass"
                
                rigor_level = payload.get("rigor_level") or (payload.get("project_context") or {}).get("rigor_level", "exploratory")
                prompt_manifest = payload.get("prompt_manifest", {})
                
                opik_emitter.emit_node_end(
                    job_id=job_id or "",
                    project_id=project_id,
                    node_name=node_name,
                    meta={
                        "duration_ms": duration_ms,
                        "success": error is None,
                        "rigor_level": rigor_level,
                        "prompt_manifest": prompt_manifest,
                        "extracted_json": extracted,
                        "conflicts": payload.get("conflicts", []),
                        "manuscript_blocks": payload.get("manuscript_blocks", []),
                        "revision_count": payload.get("revision_count", 0),
                        "critic_status": payload.get("critic_status"),
                        "counts": {
                            "claims_count": triples_count,
                            "conflicts_count": conflicts_count,
                            "blocks_count": blocks_count,
                            "critiques_count": critiques_count,
                        },
                        "validation_results": validation_results,
                    },
                )
            except Exception:  # pragma: no cover - opik is best-effort
                logger.debug("Opik node_end emission failed (ignored)", exc_info=True)

    return wrapper
