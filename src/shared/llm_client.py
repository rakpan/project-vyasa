"""
Centralized LLM client for Project Vyasa.

Provides a unified interface for calling LLM services (SGLang/OpenAI-compatible APIs)
with optional debug logging when DEBUG_PROMPTS=true.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union
import requests

from .logger import get_logger

logger = get_logger("llm_client", __name__)

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


def call_model(
    url: str,
    payload: Dict[str, Any],
    timeout: int = 60,
    files: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
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
        
        # Append response to debug log
        _write_debug_log(url, request_data, response_data)
        
        return response_data
        
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

