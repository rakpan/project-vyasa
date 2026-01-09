"""
Runtime Budget Resolver for Project Vyasa.

Loads runtime budgets from system_settings and provides helper methods
to cap/truncate inputs and outputs according to Tier A and Tier B limits.
"""

import threading
import time
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone

from .logger import get_logger
from .config import (
    get_memory_url,
    ARANGODB_DB,
    ARANGODB_USER,
    get_arango_password,
    RETRIEVAL_TOP_K,
    RERANK_TOP_M,
)

logger = get_logger("shared", __name__)

# Cache for budgets: (budgets_dict, fetched_at)
_budget_cache: Optional[tuple] = None
_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 60  # 60 second cache TTL


def _get_db():
    """Get ArangoDB database instance (lazy, with error handling)."""
    try:
        from arango import ArangoClient
        client = ArangoClient(hosts=get_memory_url())
        return client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
    except Exception as e:
        logger.debug(f"Failed to connect to ArangoDB for budget resolver: {e}")
        return None


def _load_budgets() -> Dict[str, Any]:
    """Load runtime budgets from system_settings (with caching)."""
    # Check cache first
    with _cache_lock:
        if _budget_cache is not None:
            budgets_dict, fetched_at = _budget_cache
            age_seconds = time.time() - fetched_at
            if age_seconds < CACHE_TTL_SECONDS:
                return budgets_dict
            # Cache expired
            _budget_cache = None
    
    # Try to load from ArangoDB
    db = _get_db()
    if db:
        try:
            from ...orchestrator.services.settings_service import SettingsService
            service = SettingsService(db)
            settings = service.get_settings()
            
            budgets_dict = {
                "tier_a": settings.runtime_budgets.tier_a.model_dump(mode="json", exclude_none=True),
                "tier_b": settings.runtime_budgets.tier_b.model_dump(mode="json", exclude_none=True),
            }
            
            # Cache the result
            with _cache_lock:
                _budget_cache = (budgets_dict, time.time())
            
            logger.debug("Loaded runtime budgets from DB")
            return budgets_dict
        except Exception as e:
            logger.warning(f"Failed to load runtime budgets from DB: {e}, using defaults", exc_info=True)
    
    # Fall back to defaults (equivalent to current behavior)
    budgets_dict = {
        "tier_a": {
            "retrieval_top_k": RETRIEVAL_TOP_K,
            "rerank_top_m": RERANK_TOP_M,
            "candidate_trunc_tokens": 600,
            "snippet_min_tokens": 50,
            "snippet_max_tokens": 800,
            "max_snippets": 20,
        },
        "tier_b": {
            "shared_prefix_max_tokens": 4096,
            "packet_a_max_tokens": 8192,
            "packet_b_max_tokens": 2048,
            "output_max_tokens_by_agent": {
                "synthesizer": 4096,
                "critic": 2048,
                "cartographer_pass2": 4096,
            },
            "critic_bounded_retry_max": 1,
        },
    }
    
    logger.debug("Using default runtime budgets")
    return budgets_dict


def get_tier_a_limits() -> Dict[str, Any]:
    """Get Tier A (CPU/Embedder-bound) runtime limits.
    
    Returns:
        Dict with keys:
        - retrieval_top_k: int
        - rerank_top_m: int
        - candidate_trunc_tokens: int
        - snippet_min_tokens: int
        - snippet_max_tokens: int
        - max_snippets: int
    """
    budgets = _load_budgets()
    return budgets["tier_a"]


def get_tier_b_limits() -> Dict[str, Any]:
    """Get Tier B (GPU/Nemotron-49B-bound) runtime limits.
    
    Returns:
        Dict with keys:
        - shared_prefix_max_tokens: int
        - packet_a_max_tokens: int
        - packet_b_max_tokens: int
        - output_max_tokens_by_agent: Dict[str, int]
        - critic_bounded_retry_max: int
    """
    budgets = _load_budgets()
    return budgets["tier_b"]


def truncate_candidate_text(text: str, max_tokens: Optional[int] = None) -> str:
    """Truncate candidate text for reranker (Tier A).
    
    Args:
        text: Candidate text to truncate.
        max_tokens: Optional max tokens. If None, uses candidate_trunc_tokens from budgets.
    
    Returns:
        Truncated text (approximately max_tokens).
    """
    if max_tokens is None:
        limits = get_tier_a_limits()
        max_tokens = limits.get("candidate_trunc_tokens", 600)
    
    # Rough estimate: 1 token ≈ 4 characters
    max_chars = max_tokens * 4
    
    if len(text) <= max_chars:
        return text
    
    # Truncate at word boundary
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.8:  # Only truncate at word boundary if not too short
        truncated = truncated[:last_space]
    
    return truncated + "..."


def estimate_tokens(text: str) -> int:
    """Estimate token count for text (rough: 1 token ≈ 4 characters).
    
    Args:
        text: Text to estimate.
    
    Returns:
        Estimated token count.
    """
    return len(text) // 4


def cap_snippet_tokens(snippet_text: str) -> Tuple[str, int]:
    """Cap snippet text to snippet_max_tokens (Tier A).
    
    Args:
        snippet_text: Snippet text to cap.
    
    Returns:
        Tuple of (truncated_text, token_estimate).
    """
    limits = get_tier_a_limits()
    max_tokens = limits.get("snippet_max_tokens", 800)
    min_tokens = limits.get("snippet_min_tokens", 50)
    
    token_estimate = estimate_tokens(snippet_text)
    
    if token_estimate <= max_tokens:
        return snippet_text, token_estimate
    
    # Truncate to max_tokens
    max_chars = max_tokens * 4
    truncated = snippet_text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.8:
        truncated = truncated[:last_space]
    
    truncated_text = truncated + "..."
    token_estimate = estimate_tokens(truncated_text)
    
    # Ensure minimum
    if token_estimate < min_tokens and len(snippet_text) > min_tokens * 4:
        truncated_text = snippet_text[:min_tokens * 4]
        token_estimate = min_tokens
    
    return truncated_text, token_estimate


def cap_evidence_pack_snippets(snippets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cap EvidencePack snippets to max_snippets (Tier A).
    
    Args:
        snippets: List of snippet dicts with 'quote_text' and 'token_estimate'.
    
    Returns:
        Capped list of snippets.
    """
    limits = get_tier_a_limits()
    max_snippets = limits.get("max_snippets", 20)
    
    if len(snippets) <= max_snippets:
        return snippets
    
    logger.debug(
        f"Capping EvidencePack snippets: {len(snippets)} -> {max_snippets}",
        extra={"payload": {"original_count": len(snippets), "capped_count": max_snippets}}
    )
    
    return snippets[:max_snippets]


def cap_packet_a_tokens(snippets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cap Packet A (EvidencePack) total tokens to packet_a_max_tokens (Tier B).
    
    Args:
        snippets: List of snippet dicts with 'quote_text' and 'token_estimate'.
    
    Returns:
        Capped list of snippets (truncated to fit token budget).
    """
    limits = get_tier_b_limits()
    max_tokens = limits.get("packet_a_max_tokens", 8192)
    
    total_tokens = sum(s.get("token_estimate", estimate_tokens(s.get("quote_text", ""))) for s in snippets)
    
    if total_tokens <= max_tokens:
        return snippets
    
    # Truncate snippets to fit budget (keep best snippets first)
    capped_snippets = []
    current_tokens = 0
    
    for snippet in snippets:
        snippet_tokens = snippet.get("token_estimate", estimate_tokens(snippet.get("quote_text", "")))
        
        if current_tokens + snippet_tokens <= max_tokens:
            capped_snippets.append(snippet)
            current_tokens += snippet_tokens
        else:
            # Try to fit partial snippet
            remaining_tokens = max_tokens - current_tokens
            if remaining_tokens > 100:  # Only if meaningful space left
                quote_text = snippet.get("quote_text", "")
                truncated_text, truncated_tokens = cap_snippet_tokens(quote_text[:remaining_tokens * 4])
                snippet_copy = {**snippet, "quote_text": truncated_text, "token_estimate": truncated_tokens}
                capped_snippets.append(snippet_copy)
            break
    
    logger.debug(
        f"Capped Packet A tokens: {total_tokens} -> {sum(s.get('token_estimate', 0) for s in capped_snippets)}",
        extra={"payload": {"original_tokens": total_tokens, "capped_tokens": sum(s.get('token_estimate', 0) for s in capped_snippets), "snippet_count": len(capped_snippets)}}
    )
    
    return capped_snippets


def cap_packet_b_tokens(packet_b: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cap Packet B (Analytical Notes) total tokens to packet_b_max_tokens (Tier B).
    
    Args:
        packet_b: List of note dicts with 'text'.
    
    Returns:
        Capped list of notes (truncated to fit token budget).
    """
    limits = get_tier_b_limits()
    max_tokens = limits.get("packet_b_max_tokens", 2048)
    
    total_tokens = sum(estimate_tokens(note.get("text", "")) for note in packet_b)
    
    if total_tokens <= max_tokens:
        return packet_b
    
    # Truncate notes to fit budget
    capped_notes = []
    current_tokens = 0
    
    for note in packet_b:
        note_text = note.get("text", "")
        note_tokens = estimate_tokens(note_text)
        
        if current_tokens + note_tokens <= max_tokens:
            capped_notes.append(note)
            current_tokens += note_tokens
        else:
            # Try to fit partial note
            remaining_tokens = max_tokens - current_tokens
            if remaining_tokens > 50:  # Only if meaningful space left
                truncated_text = note_text[:remaining_tokens * 4]
                note_copy = {**note, "text": truncated_text + "..."}
                capped_notes.append(note_copy)
            break
    
    logger.debug(
        f"Capped Packet B tokens: {total_tokens} -> {sum(estimate_tokens(n.get('text', '')) for n in capped_notes)}",
        extra={"payload": {"original_tokens": total_tokens, "capped_tokens": sum(estimate_tokens(n.get('text', '')) for n in capped_notes)}}
    )
    
    return capped_notes


def get_output_max_tokens(agent_name: str) -> int:
    """Get max output tokens for an agent (Tier B).
    
    Args:
        agent_name: Agent name (e.g., "synthesizer", "critic", "cartographer_pass2").
    
    Returns:
        Max output tokens for this agent.
    """
    limits = get_tier_b_limits()
    output_limits = limits.get("output_max_tokens_by_agent", {})
    
    # Map common agent names
    agent_map = {
        "synthesizer": "synthesizer",
        "section_synthesizer": "synthesizer",
        "critic": "critic",
        "section_critic": "critic",
        "cartographer_pass2": "cartographer_pass2",
    }
    
    mapped_name = agent_map.get(agent_name, agent_name)
    return output_limits.get(mapped_name, 4096)  # Default 4096 if not found


def get_critic_bounded_retry_max() -> int:
    """Get max bounded retries for Critic verification (Tier B).
    
    Returns:
        Max bounded retry count.
    """
    limits = get_tier_b_limits()
    return limits.get("critic_bounded_retry_max", 1)


def clear_budget_cache() -> None:
    """Clear budget cache (force reload on next call)."""
    with _cache_lock:
        _budget_cache = None
    logger.debug("Cleared budget cache")
