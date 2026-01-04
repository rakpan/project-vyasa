"""
Opik Prompt Registry Integration for Project Vyasa.

Fetches prompt templates from Opik at runtime, enabling prompt versioning
and experimentation without code redeployment.

Falls back to local defaults if Opik is unavailable (offline/DGX-only runs).
"""

import time
import threading
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

import requests

from ..shared.logger import get_logger
from ..shared.config import (
    OPIK_ENABLED,
    OPIK_BASE_URL,
    OPIK_API_KEY,
    OPIK_TIMEOUT_SECONDS,
)

logger = get_logger("orchestrator", __name__)

# Cache for prompts: {prompt_name: (template, fetched_at)}
_prompt_cache: Dict[str, Tuple[str, float]] = {}
_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 300  # 5 minutes


def get_active_prompt(prompt_name: str, default: str) -> str:
    """Fetch the active prompt from Opik, with caching and fallback.
    
    Fetches the "Production" tagged version from Opik. If Opik is unavailable
    or the prompt is not found, returns the default (factory default).
    
    Caches results for 5 minutes to avoid network latency on every token.
    
    Args:
        prompt_name: Name of the prompt in Opik (e.g., "vyasa-cartographer-v1")
        default: Fallback prompt template (factory default)
    
    Returns:
        Prompt template string (from Opik or default)
    """
    # Check cache first
    with _cache_lock:
        if prompt_name in _prompt_cache:
            template, fetched_at = _prompt_cache[prompt_name]
            age_seconds = time.time() - fetched_at
            if age_seconds < CACHE_TTL_SECONDS:
                logger.debug(
                    f"Using cached prompt '{prompt_name}' (age: {age_seconds:.1f}s)",
                    extra={"payload": {"prompt_name": prompt_name}}
                )
                return template
            # Cache expired, remove it
            del _prompt_cache[prompt_name]
    
    # Opik not enabled or not configured
    if not OPIK_ENABLED or not OPIK_BASE_URL:
        logger.debug(
            f"Opik not enabled, using default prompt for '{prompt_name}'",
            extra={"payload": {"prompt_name": prompt_name}}
        )
        return default
    
    # Try to fetch from Opik
    try:
        client_config = {
            "base_url": OPIK_BASE_URL.rstrip("/"),
            "headers": {
                "Content-Type": "application/json",
            },
            "timeout": OPIK_TIMEOUT_SECONDS,
        }
        
        if OPIK_API_KEY:
            client_config["headers"]["Authorization"] = f"Bearer {OPIK_API_KEY}"
        
        # Fetch prompt from Opik API
        # Expected endpoint: GET /api/prompts/{prompt_name}?tag=production
        prompt_url = f"{client_config['base_url']}/api/prompts/{prompt_name}"
        params = {"tag": "production"}  # Fetch production-tagged version
        
        response = requests.get(
            prompt_url,
            headers=client_config["headers"],
            params=params,
            timeout=client_config["timeout"],
        )
        
        if response.status_code == 200:
            data = response.json()
            template = data.get("template") or data.get("content") or data.get("text", "")
            
            if template:
                # Cache the result
                with _cache_lock:
                    _prompt_cache[prompt_name] = (template, time.time())
                
                logger.info(
                    f"Fetched prompt '{prompt_name}' from Opik",
                    extra={"payload": {"prompt_name": prompt_name, "template_length": len(template)}}
                )
                return template
            else:
                logger.warning(
                    f"Opik returned empty template for '{prompt_name}', using default",
                    extra={"payload": {"prompt_name": prompt_name}}
                )
                return default
        
        elif response.status_code == 404:
            logger.debug(
                f"Prompt '{prompt_name}' not found in Opik, using default",
                extra={"payload": {"prompt_name": prompt_name}}
            )
            return default
        
        else:
            logger.warning(
                f"Opik returned status {response.status_code} for '{prompt_name}', using default",
                extra={"payload": {"prompt_name": prompt_name, "status_code": response.status_code}}
            )
            return default
    
    except requests.exceptions.Timeout:
        logger.warning(
            f"Opik request timeout for '{prompt_name}', using default",
            extra={"payload": {"prompt_name": prompt_name}}
        )
        return default
    
    except requests.exceptions.ConnectionError:
        logger.debug(
            f"Opik connection failed for '{prompt_name}', using default (offline mode)",
            extra={"payload": {"prompt_name": prompt_name}}
        )
        return default
    
    except Exception as e:
        logger.warning(
            f"Failed to fetch prompt '{prompt_name}' from Opik: {e}, using default",
            extra={"payload": {"prompt_name": prompt_name, "error": str(e)}},
            exc_info=True,
        )
        return default


def clear_prompt_cache(prompt_name: Optional[str] = None) -> None:
    """Clear prompt cache, optionally for a specific prompt.
    
    Args:
        prompt_name: Optional prompt name to clear. If None, clears all cached prompts.
    """
    with _cache_lock:
        if prompt_name:
            if prompt_name in _prompt_cache:
                del _prompt_cache[prompt_name]
                logger.debug(f"Cleared cache for prompt '{prompt_name}'")
        else:
            _prompt_cache.clear()
            logger.debug("Cleared all prompt caches")

