"""Lightweight, best-effort Opik tracing wrapper (observe-only)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from typing import Any, Callable, Dict, Optional

import requests

from .config import (
    OPIK_ENABLED,
    OPIK_BASE_URL,
    OPIK_API_KEY,
    OPIK_PROJECT_NAME,
    OPIK_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)
_client_lock = threading.Lock()
_client: Optional[Dict[str, Any]] = None


def get_opik_client() -> Optional[Dict[str, Any]]:
    """Return a lazy-initialized Opik client config if enabled."""
    global _client
    if not OPIK_ENABLED or not OPIK_BASE_URL:
        return None
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        _client = {
            "base_url": OPIK_BASE_URL.rstrip("/"),
            "headers": {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPIK_API_KEY}" if OPIK_API_KEY else "",
            },
            "timeout": OPIK_TIMEOUT_SECONDS,
            "project": OPIK_PROJECT_NAME,
        }
    return _client


def _safe_post(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: int) -> None:
    try:
        requests.post(url, json=payload, headers=headers, timeout=timeout)
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("Opik post failed (ignored)", exc_info=True, extra={"payload": {"error": str(exc)}})


def track_llm_call(metadata: Dict[str, Any], fn: Callable[[], Any]) -> Any:
    """
    Execute fn() and best-effort send metadata to Opik.

    Never raises on Opik failure. Returns fn() result unchanged.
    """
    result = fn()
    client = get_opik_client()
    if not client:
        return result
    try:
        payload = {
            "project": client["project"],
            "run_type": "llm_call",
            "metadata": metadata,
        }
        ingest_url = f"{client['base_url']}/api/traces"
        _safe_post(ingest_url, payload, client["headers"], client["timeout"])
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Opik tracking failed (ignored)", exc_info=True, extra={"payload": {"error": str(exc)}})
    return result


def compute_prompt_hash(messages: list, tool_signature: Any) -> str:
    """Compute a stable hash without storing raw prompts."""
    system_parts = []
    user_parts = []
    for msg in messages or []:
        role = msg.get("role") if isinstance(msg, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else ""
        if role == "system":
            system_parts.append(str(content))
        elif role == "user":
            user_parts.append(str(content))
    tool_sig = json.dumps(tool_signature, sort_keys=True, separators=(",", ":"))
    combined = "||".join(
        [
            "|".join(system_parts),
            "|".join(user_parts),
            tool_sig,
        ]
    )
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
