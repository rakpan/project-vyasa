"""
Vyasa-native Prompt Registry.

Fetches prompt templates from Opik when enabled, with safe fallback to local defaults
for offline/DGX-only runs. Includes in-memory caching to avoid network latency.
"""

import time
import threading
from typing import Dict, Optional, Tuple

from ...shared.logger import get_logger
from ...shared.config import (
    OPIK_ENABLED,
    OPIK_BASE_URL,
    OPIK_API_KEY,
    OPIK_TIMEOUT_SECONDS,
    PROMPT_REGISTRY_ENABLED,
    PROMPT_CACHE_SECONDS,
    PROMPT_TAG,
)
from .models import PromptUse

logger = get_logger("orchestrator", __name__)

# In-memory cache: {(prompt_name, tag): (template, fetched_at)}
_prompt_cache: Dict[Tuple[str, str], Tuple[str, float]] = {}
_cache_lock = threading.Lock()

# Cache TTL from config (defaults to 300 seconds / 5 minutes)
CACHE_TTL_SECONDS = PROMPT_CACHE_SECONDS


def get_active_prompt(
    prompt_name: str,
    default: str,
    tag: Optional[str] = None,
) -> str:
    """Fetch the active prompt from Opik, with caching and fallback.
    
    Behavior:
    - If PROMPT_REGISTRY_ENABLED=false or OPIK_ENABLED=false -> return default
    - Else try Opik fetch by name + tag (or name alone if tag not supported)
    - On any exception -> return default
    - Cache responses in-memory for configured TTL (default 300 seconds)
    
    Args:
        prompt_name: Name of the prompt in Opik (e.g., "vyasa-cartographer-v1")
        default: Fallback prompt template (factory default)
        tag: Tag/version to fetch (defaults to PROMPT_TAG from config, or "production")
    
    Returns:
        Prompt template string (from Opik or default)
    """
    template, _ = get_active_prompt_with_meta(prompt_name, default, tag)
    return template


def get_active_prompt_with_meta(
    prompt_name: str,
    default: str,
    tag: Optional[str] = None,
) -> Tuple[str, PromptUse]:
    """Fetch the active prompt from Opik with metadata, with caching and fallback.
    
    Returns both the template and metadata about its source for tracking.
    
    Args:
        prompt_name: Name of the prompt in Opik
        default: Fallback prompt template (factory default)
        tag: Tag/version to fetch (defaults to PROMPT_TAG from config)
    
    Returns:
        Tuple of (template: str, metadata: PromptUse)
    """
    # Use configured tag if not provided
    if tag is None:
        tag = PROMPT_TAG
    
    # Check cache first
    cache_key = (prompt_name, tag)
    cache_hit = False
    with _cache_lock:
        if cache_key in _prompt_cache:
            template, fetched_at = _prompt_cache[cache_key]
            age_seconds = time.time() - fetched_at
            if age_seconds < CACHE_TTL_SECONDS:
                logger.debug(
                    f"Using cached prompt '{prompt_name}' (tag: {tag}, age: {age_seconds:.1f}s)",
                    extra={"payload": {"prompt_name": prompt_name, "tag": tag}}
                )
                cache_hit = True
                # Create metadata for cached prompt
                metadata = PromptUse.from_template(
                    prompt_name=prompt_name,
                    template=template,
                    resolved_source="opik",  # Cached prompts came from Opik
                    tag=tag,
                    cache_hit=True,
                )
                return template, metadata
            # Cache expired, remove it
            del _prompt_cache[cache_key]
    
    # Prompt registry not enabled or Opik not configured
    if not PROMPT_REGISTRY_ENABLED or not OPIK_ENABLED or not OPIK_BASE_URL:
        logger.debug(
            f"Opik not enabled, using default prompt for '{prompt_name}'",
            extra={"payload": {"prompt_name": prompt_name, "tag": tag}}
        )
        metadata = PromptUse.from_template(
            prompt_name=prompt_name,
            template=default,
            resolved_source="default",
            tag=tag,
            cache_hit=False,
        )
        return default, metadata
    
    # Try to fetch from Opik
    try:
        # Guard import to avoid hard dependency on requests in non-Opik runs
        import requests
        
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
        # Expected endpoint: GET /api/prompts/{prompt_name}?tag={tag}
        prompt_url = f"{client_config['base_url']}/api/prompts/{prompt_name}"
        params = {"tag": tag} if tag else {}
        
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
                    _prompt_cache[cache_key] = (template, time.time())
                
                logger.info(
                    f"Fetched prompt '{prompt_name}' from Opik (tag: {tag})",
                    extra={"payload": {"prompt_name": prompt_name, "tag": tag, "template_length": len(template)}}
                )
                metadata = PromptUse.from_template(
                    prompt_name=prompt_name,
                    template=template,
                    resolved_source="opik",
                    tag=tag,
                    cache_hit=False,
                )
                return template, metadata
            else:
                logger.warning(
                    f"Opik returned empty template for '{prompt_name}' (tag: {tag}), using default",
                    extra={"payload": {"prompt_name": prompt_name, "tag": tag}}
                )
                metadata = PromptUse.from_template(
                    prompt_name=prompt_name,
                    template=default,
                    resolved_source="default",
                    tag=tag,
                    cache_hit=False,
                )
                return default, metadata
        
        elif response.status_code == 404:
            logger.debug(
                f"Prompt '{prompt_name}' not found in Opik (tag: {tag}), using default",
                extra={"payload": {"prompt_name": prompt_name, "tag": tag}}
            )
            metadata = PromptUse.from_template(
                prompt_name=prompt_name,
                template=default,
                resolved_source="default",
                tag=tag,
                cache_hit=False,
            )
            return default, metadata
        
        else:
            logger.warning(
                f"Opik returned status {response.status_code} for '{prompt_name}' (tag: {tag}), using default",
                extra={"payload": {"prompt_name": prompt_name, "tag": tag, "status_code": response.status_code}}
            )
            metadata = PromptUse.from_template(
                prompt_name=prompt_name,
                template=default,
                resolved_source="default",
                tag=tag,
                cache_hit=False,
            )
            return default, metadata
    
    except ImportError:
        # requests not available (shouldn't happen, but guard anyway)
        logger.warning(
            f"requests library not available, using default for '{prompt_name}'",
            extra={"payload": {"prompt_name": prompt_name, "tag": tag}}
        )
        metadata = PromptUse.from_template(
            prompt_name=prompt_name,
            template=default,
            resolved_source="default",
            tag=tag,
            cache_hit=False,
        )
        return default, metadata
    
    except Exception as e:
        logger.warning(
            f"Failed to fetch prompt '{prompt_name}' from Opik (tag: {tag}): {e}, using default",
            extra={"payload": {"prompt_name": prompt_name, "tag": tag, "error": str(e)}},
            exc_info=True,
        )
        metadata = PromptUse.from_template(
            prompt_name=prompt_name,
            template=default,
            resolved_source="default",
            tag=tag,
            cache_hit=False,
        )
        return default, metadata


def clear_prompt_cache(prompt_name: Optional[str] = None, tag: Optional[str] = None) -> None:
    """Clear prompt cache, optionally for a specific prompt/tag.
    
    Args:
        prompt_name: Optional prompt name to clear. If None, clears all cached prompts.
        tag: Optional tag to clear. If None and prompt_name is set, clears all tags for that prompt.
    """
    with _cache_lock:
        if prompt_name is None:
            _prompt_cache.clear()
            logger.debug("Cleared all prompt caches")
        elif tag is None:
            # Clear all tags for this prompt
            keys_to_remove = [k for k in _prompt_cache.keys() if k[0] == prompt_name]
            for key in keys_to_remove:
                del _prompt_cache[key]
            logger.debug(f"Cleared cache for prompt '{prompt_name}' (all tags)")
        else:
            cache_key = (prompt_name, tag)
            if cache_key in _prompt_cache:
                del _prompt_cache[cache_key]
                logger.debug(f"Cleared cache for prompt '{prompt_name}' (tag: {tag})")
