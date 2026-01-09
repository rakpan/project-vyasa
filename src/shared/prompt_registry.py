"""
Prompt Registry for Project Vyasa.

Reads active prompt profiles from ArangoDB (active_prompt_set + prompt_profiles)
with caching and fallback to defaults.
"""

import time
import threading
from typing import Dict, Optional, Tuple, Any
from datetime import datetime, timezone

from .logger import get_logger
from .config import (
    get_memory_url,
    ARANGODB_DB,
    ARANGODB_USER,
    get_arango_password,
)

logger = get_logger("shared", __name__)

# Cache for prompts: {prompt_id: (profile_data, fetched_at)}
_prompt_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 30  # 30 second cache TTL


def _get_db():
    """Get ArangoDB database instance (lazy, with error handling)."""
    try:
        from arango import ArangoClient
        client = ArangoClient(hosts=get_memory_url())
        return client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
    except Exception as e:
        logger.debug(f"Failed to connect to ArangoDB for prompt registry: {e}")
        return None


def get_prompt(prompt_id: str, default_template: str) -> Dict[str, Any]:
    """Get active prompt profile for a prompt_id.
    
    Behavior:
    1. Check cache (30s TTL)
    2. Load from ArangoDB (active_prompt_set -> prompt_profiles)
    3. Fall back to default_template if not found
    
    Args:
        prompt_id: Prompt identifier (e.g., "critic_verify", "synthesizer_section_writer")
        default_template: Fallback template if profile not found
    
    Returns:
        Dict with keys:
        - template: str (prompt template text)
        - output_type: str ("json" or "markdown")
        - constraints: Dict (citation format, bounded retry, etc.)
        - version: int (prompt version number)
        - source: str ("db", "default")
    """
    # Check cache first
    with _cache_lock:
        if prompt_id in _prompt_cache:
            profile_data, fetched_at = _prompt_cache[prompt_id]
            age_seconds = time.time() - fetched_at
            if age_seconds < CACHE_TTL_SECONDS:
                logger.debug(
                    f"Using cached prompt profile '{prompt_id}' (age: {age_seconds:.1f}s)",
                    extra={"payload": {"prompt_id": prompt_id, "version": profile_data.get("version")}}
                )
                return profile_data
            # Cache expired, remove it
            del _prompt_cache[prompt_id]
    
    # Try to load from ArangoDB
    db = _get_db()
    if db:
        try:
            from ...orchestrator.services.prompt_profile_service import PromptProfileService
            service = PromptProfileService(db)
            
            # Get active version (or latest if no active)
            profile = service.get_profile(prompt_id)
            
            if profile:
                profile_data = {
                    "template": profile.template,
                    "output_type": profile.output_type,
                    "constraints": profile.constraints.model_dump(mode="json", exclude_none=True),
                    "required_fields": profile.required_fields,
                    "version": profile.version,
                    "source": "db",
                }
                
                # Cache the result
                with _cache_lock:
                    _prompt_cache[prompt_id] = (profile_data, time.time())
                
                logger.info(
                    f"Loaded prompt profile '{prompt_id}' v{profile.version} from DB",
                    extra={"payload": {"prompt_id": prompt_id, "version": profile.version}}
                )
                
                return profile_data
        except Exception as e:
            logger.warning(
                f"Failed to load prompt profile '{prompt_id}' from DB: {e}, using default",
                extra={"payload": {"prompt_id": prompt_id}},
                exc_info=True
            )
    
    # Fall back to default
    profile_data = {
        "template": default_template,
        "output_type": "markdown",  # Default assumption
        "constraints": {},
        "required_fields": [],
        "version": 0,
        "source": "default",
    }
    
    logger.debug(
        f"Using default prompt template for '{prompt_id}'",
        extra={"payload": {"prompt_id": prompt_id}}
    )
    
    return profile_data


def clear_prompt_cache(prompt_id: Optional[str] = None) -> None:
    """Clear prompt cache, optionally for a specific prompt_id.
    
    Args:
        prompt_id: Optional prompt ID to clear. If None, clears all cached prompts.
    """
    with _cache_lock:
        if prompt_id is None:
            _prompt_cache.clear()
            logger.debug("Cleared all prompt caches")
        elif prompt_id in _prompt_cache:
            del _prompt_cache[prompt_id]
            logger.debug(f"Cleared cache for prompt '{prompt_id}'")
