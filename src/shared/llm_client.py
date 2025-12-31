"""
Centralized LLM client for Project Vyasa.

Provides a unified interface for calling LLM services (SGLang/OpenAI-compatible APIs)
with optional debug logging when DEBUG_PROMPTS=true.
"""

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import requests
from requests import Timeout as RequestsTimeout

from .logger import get_logger
from ..orchestrator.telemetry import extract_usage_from_response  # type: ignore
from .utils import get_utc_now
from .config import TIMEOUT_MATRIX
from .opik_client import track_llm_call, compute_prompt_hash, get_opik_client

logger = get_logger("llm_client", __name__)
_telemetry_emitter = None

# Sensitive keys to redact from debug logs
SENSITIVE_KEYS = {
    "api_key",
    "apiKey",
    "authorization",
    "Authorization",
    "password",
    "token",
    "secret",
    "credentials",
}


def _redact_sensitive(data: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive keys from a dictionary.
    
    Args:
        data: Dictionary that may contain sensitive keys.
        
    Returns:
        New dictionary with sensitive values redacted (replaced with "[REDACTED]").
    """
    redacted = {}
    for key, value in data.items():
        if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = _redact_sensitive(value)
        elif isinstance(value, list):
            redacted[key] = [
                _redact_sensitive(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted


def _write_debug_log(
    url: str,
    request_data: Dict[str, Any],
    response_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Write debug log file for LLM request/response.
    
    Args:
        url: Request URL.
        request_data: Request payload (already redacted).
        response_data: Optional response data to append.
    """
    debug_enabled = os.getenv("DEBUG_PROMPTS", "false").lower() == "true"
    if not debug_enabled:
        return
    
    # Ensure logs/debug directory exists
    debug_dir = Path("logs/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = debug_dir / f"req_{timestamp}_{unique_id}.json"
    
    # Prepare log entry
    log_entry: Dict[str, Any] = {
        "url": url,
        "request": _redact_sensitive(request_data),
        "timestamp": datetime.now().isoformat(),
    }
    
    if response_data:
        log_entry["response"] = response_data
    
    # Write to file
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False)
        logger.debug(f"Debug log written: {filename}")
    except Exception as e:
        logger.warning(f"Failed to write debug log: {e}")


def _get_telemetry_emitter():
    """Lazy-load telemetry emitter to avoid import cycles."""
    global _telemetry_emitter
    if _telemetry_emitter is None:
        try:
            from ..orchestrator.telemetry import TelemetryEmitter  # type: ignore

            _telemetry_emitter = TelemetryEmitter()
        except Exception:
            _telemetry_emitter = None
    return _telemetry_emitter


def call_model(
    url: str,
    payload: Dict[str, Any],
    timeout: int = 60,
    files: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    opik_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call an LLM model via HTTP POST request.
    
    Supports both JSON and multipart/form-data requests (for vision endpoints with file uploads).
    When DEBUG_PROMPTS=true, writes request/response to logs/debug/req_{timestamp}_{uuid}.json.
    
    Args:
        url: Full URL to the LLM endpoint (e.g., "http://cortex-worker:30001/v1/chat/completions").
        payload: Request payload dictionary (will be JSON-encoded or form-encoded).
        timeout: Request timeout in seconds (default: 60).
        files: Optional files dictionary for multipart/form-data requests.
        headers: Optional custom headers.
        
    Returns:
        Response JSON as dictionary.
        
    Raises:
        requests.RequestException: If the HTTP request fails.
        ValueError: If response is not valid JSON.
    """
    # Prepare request data for logging (before making the call)
    request_data: Dict[str, Any] = {
        "url": url,
        "payload": payload,
    }
    if files:
        request_data["files"] = {k: f"<file: {k}>" for k in files.keys()}
    if headers:
        request_data["headers"] = _redact_sensitive(headers)
    
    # Write request to debug log (before call)
    _write_debug_log(url, request_data)
    
    # Make the HTTP request
    try:
        start = datetime.now()
        if files:
            # Multipart/form-data request (for vision endpoints)
            response = requests.post(
                url,
                data=payload,
                files=files,
                headers=headers,
                timeout=timeout,
            )
        else:
            # JSON request
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout,
            )
        
        response.raise_for_status()
        response_data = response.json()
        duration_ms = (datetime.now() - start).total_seconds() * 1000

        # Append response to debug log
        _write_debug_log(url, request_data, response_data)
        emitter = _get_telemetry_emitter()
        if emitter:
            emitter.emit_event(
                "llm_call_completed",
                {
                    "job_id": payload.get("job_id"),
                    "project_id": payload.get("project_id"),
                    "node_name": payload.get("node") or payload.get("task") or "llm_client",
                    "timestamp": get_utc_now().isoformat(),
                    "duration_ms": duration_ms,
                    "metadata": {
                        "usage": extract_usage_from_response(response_data) or {},
                        "url": url,
                        "model": payload.get("model"),
                        "path": "call_model",
                        "success": True,
                        "tokens": extract_usage_from_response(response_data) or {},
                    },
                },
            )

        opik_meta = {
            "project_id": payload.get("project_id"),
            "job_id": payload.get("job_id"),
            "node_name": payload.get("node") or payload.get("task") or "llm_client",
            "expert_type": payload.get("expert_type"),
            "model": payload.get("model"),
            "duration_ms": duration_ms,
            "prompt_hash": (opik_metadata or {}).get("prompt_hash"),
            "tokens": extract_usage_from_response(response_data) or {},
            "success": True,
            "path": "call_model",
        }
        return track_llm_call(opik_meta, lambda: response_data)
        
    except requests.exceptions.RequestException as e:
        # Log error response if available
        error_data = None
        if hasattr(e.response, "text"):
            try:
                error_data = {"error": e.response.text, "status_code": e.response.status_code}
            except Exception:
                pass
        
        if error_data:
            _write_debug_log(url, request_data, error_data)
        
        logger.error(
            f"LLM request failed: {url}",
            extra={"payload": {"error": str(e), "url": url}},
            exc_info=True,
        )
        raise


def _normalize_tools(allowed_tools: Optional[list]) -> list:
    """Normalize tools into OpenAI-compatible objects."""
    if not allowed_tools:
        return []
    tools: list = []
    for tool in allowed_tools:
        if isinstance(tool, dict):
            tools.append(tool)
        elif isinstance(tool, str):
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool,
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            )
    return tools


def chat(
    *,
    primary_url: str,
    model: str,
    messages: list,
    request_params: Optional[Dict[str, Any]] = None,
    state: Optional[Dict[str, Any]] = None,
    node_name: str = "llm_node",
    expert_name: str = "Worker",
    fallback_url: Optional[str] = None,
    fallback_model: Optional[str] = None,
    fallback_expert_name: str = "Brain",
    timeout: int = 60,
    max_retries: int = 1,
    allowed_tools: Optional[list] = None,
    opik_annotation: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Standard chat interface with retry + fallback and telemetry.

    Returns:
        (response_json, meta) where meta includes duration_ms, usage, expert_name, model_id, url_base, path.
    """
    emitter = _get_telemetry_emitter()
    tools = _normalize_tools(allowed_tools)
    payload_base = {"messages": messages, "model": model}
    if tools:
        payload_base["tools"] = tools
    if request_params:
        payload_base.update(request_params)

    tool_signature = [{"name": t.get("function", {}).get("name")} for t in tools] if tools else []
    prompt_hash = compute_prompt_hash(messages, tool_signature)

    attempts = [("primary", primary_url, model, expert_name)]
    if fallback_url:
        attempts.append(("fallback", fallback_url, fallback_model or model, fallback_expert_name))

    last_error: Optional[Exception] = None

    for path, url_base, model_id, exp_name in attempts:
        for attempt in range(1, max_retries + 2):  # initial try + retries
            start = time.monotonic()
            try:
                def _do_request():
                    resp_inner = requests.post(
                        f"{url_base.rstrip('/')}/v1/chat/completions",
                        json=payload_base if path == "primary" else {**payload_base, "model": model_id},
                        timeout=TIMEOUT_MATRIX.get("SGLANG_CALL", timeout),
                    )
                    resp_inner.raise_for_status()
                    return resp_inner

                resp = _do_request()
                data = resp.json()
                duration_ms = (time.monotonic() - start) * 1000
                usage = extract_usage_from_response(data) or {}

                if emitter:
                    emitter.emit_event(
                        "llm_call_completed",
                        {
                            "job_id": state.get("job_id") if isinstance(state, dict) else None,
                            "project_id": state.get("project_id") if isinstance(state, dict) else None,
                            "node_name": node_name,
                            "timestamp": get_utc_now().isoformat(),
                            "duration_ms": duration_ms,
                            "metadata": {
                                "expert_name": exp_name,
                                "model_id": model_id,
                                "url": f"{url_base.rstrip('/')}/v1/chat/completions",
                                "path": path,
                                "attempt": attempt,
                                "success": True,
                                "tokens": usage,
                                "usage": usage,
                            },
                        },
                    )

                # Emit explicit fallback signal when path is fallback and primary existed
                if path == "fallback" and attempts[0][1] != url_base and emitter:
                    emitter.emit_event(
                        "expert_fallback",
                        {
                            "job_id": state.get("job_id") if isinstance(state, dict) else None,
                            "project_id": state.get("project_id") if isinstance(state, dict) else None,
                            "node_name": node_name,
                            "timestamp": get_utc_now().isoformat(),
                            "duration_ms": duration_ms,
                            "metadata": {
                                "primary": attempts[0][3],
                                "fallback": exp_name,
                                "reason": str(last_error) if last_error else "primary failure",
                            },
                        },
                    )

                opik_meta = {
                    "project_id": state.get("project_id") if isinstance(state, dict) else None,
                    "job_id": state.get("job_id") if isinstance(state, dict) else None,
                    "node_name": node_name,
                    "expert_type": exp_name,
                    "model": model_id,
                    "duration_ms": duration_ms,
                    "prompt_hash": prompt_hash,
                    "tokens": usage,
                    "success": True,
                    "path": path,
                }
                result_tuple = (
                    data,
                    {
                        "duration_ms": duration_ms,
                        "usage": usage,
                        "expert_name": exp_name,
                        "model_id": model_id,
                        "url_base": url_base.rstrip("/"),
                        "path": path,
                        "attempt": attempt,
                    },
                )
                return track_llm_call(opik_meta, lambda: result_tuple)
            except RequestsTimeout as exc:
                duration_ms = (time.monotonic() - start) * 1000
                if emitter:
                    emitter.emit_event(
                        "llm_call_completed",
                        {
                            "job_id": state.get("job_id") if isinstance(state, dict) else None,
                            "project_id": state.get("project_id") if isinstance(state, dict) else None,
                            "node_name": node_name,
                            "timestamp": get_utc_now().isoformat(),
                            "duration_ms": duration_ms,
                            "metadata": {
                                "expert_name": exp_name,
                                "expert_type": exp_name,
                                "model_id": model_id,
                                "url": f"{url_base.rstrip('/')}/v1/chat/completions",
                                "path": path,
                                "attempt": attempt,
                                "success": False,
                                "error": "TIMEOUT_EXCEEDED",
                                "error_code": "TIMEOUT_EXCEEDED",
                            },
                        },
                    )
                if attempt > max_retries:
                    last_error = exc
                    # best-effort Opik failure trace
                    opik_meta = {
                        "project_id": state.get("project_id") if isinstance(state, dict) else None,
                        "job_id": state.get("job_id") if isinstance(state, dict) else None,
                        "node_name": node_name,
                        "expert_type": exp_name,
                        "model": model_id,
                        "duration_ms": duration_ms,
                        "prompt_hash": prompt_hash,
                        "success": False,
                        "error": "TIMEOUT_EXCEEDED",
                        "path": path,
                        "annotation": opik_annotation or {},
                    }
                    track_llm_call(opik_meta, lambda: None)
                    break
                time.sleep(0.5)
                continue
            except requests.RequestException as exc:  # noqa: PERF203
                duration_ms = (time.monotonic() - start) * 1000
                last_error = exc
                if emitter:
                    emitter.emit_event(
                        "llm_call_completed",
                        {
                            "job_id": state.get("job_id") if isinstance(state, dict) else None,
                            "project_id": state.get("project_id") if isinstance(state, dict) else None,
                            "node_name": node_name,
                            "timestamp": get_utc_now().isoformat(),
                            "duration_ms": duration_ms,
                            "metadata": {
                                "expert_name": exp_name,
                                "model_id": model_id,
                                "url": f"{url_base.rstrip('/')}/v1/chat/completions",
                                "path": path,
                                "attempt": attempt,
                                "success": False,
                                "error": str(exc),
                            },
                        },
                    )
                if attempt > max_retries:
                    opik_meta = {
                        "project_id": state.get("project_id") if isinstance(state, dict) else None,
                        "job_id": state.get("job_id") if isinstance(state, dict) else None,
                        "node_name": node_name,
                        "expert_type": exp_name,
                        "model": model_id,
                        "duration_ms": duration_ms,
                        "prompt_hash": prompt_hash,
                        "success": False,
                        "error": str(exc),
                        "path": path,
                        "annotation": opik_annotation or {},
                    }
                    track_llm_call(opik_meta, lambda: None)
                    break  # move to fallback or raise
                time.sleep(0.5)

    # If all attempts exhausted, raise last error
    if last_error:
        raise last_error
    raise RuntimeError("LLM chat failed without an exception")
