"""
Unit tests for Runtime Budget Resolver.

Tests budget loading, caching, and helper methods for capping/truncating.
"""

import pytest
from unittest.mock import Mock, patch

from src.shared.runtime_budgets import (
    get_tier_a_limits,
    get_tier_b_limits,
    truncate_candidate_text,
    cap_snippet_tokens,
    cap_evidence_pack_snippets,
    cap_packet_a_tokens,
    cap_packet_b_tokens,
    get_output_max_tokens,
    get_critic_bounded_retry_max,
    estimate_tokens,
)


@pytest.fixture
def mock_settings_service():
    """Mock SettingsService."""
    service = Mock()
    settings = Mock()
    settings.runtime_budgets.tier_a.model_dump.return_value = {
        "retrieval_top_k": 128,
        "rerank_top_m": 32,
        "candidate_trunc_tokens": 800,
        "snippet_min_tokens": 100,
        "snippet_max_tokens": 1000,
        "max_snippets": 15,
    }
    settings.runtime_budgets.tier_b.model_dump.return_value = {
        "shared_prefix_max_tokens": 8192,
        "packet_a_max_tokens": 16384,
        "packet_b_max_tokens": 4096,
        "output_max_tokens_by_agent": {
            "synthesizer": 8192,
            "critic": 4096,
            "cartographer_pass2": 8192,
        },
        "critic_bounded_retry_max": 2,
    }
    service.get_settings.return_value = settings
    return service


@patch("src.shared.runtime_budgets._get_db")
@patch("src.shared.runtime_budgets.SettingsService")
def test_get_tier_a_limits_from_db(mock_service_class, mock_get_db, mock_settings_service):
    """Test loading Tier A limits from DB."""
    mock_get_db.return_value = Mock()
    mock_service_class.return_value = mock_settings_service
    
    limits = get_tier_a_limits()
    
    assert limits["retrieval_top_k"] == 128
    assert limits["rerank_top_m"] == 32
    assert limits["max_snippets"] == 15


@patch("src.shared.runtime_budgets._get_db")
def test_get_tier_a_limits_fallback(mock_get_db):
    """Test fallback to defaults when DB unavailable."""
    mock_get_db.return_value = None
    
    limits = get_tier_a_limits()
    
    # Should use defaults from config
    assert limits["retrieval_top_k"] >= 1
    assert limits["max_snippets"] >= 5


def test_truncate_candidate_text():
    """Test truncating candidate text for reranker."""
    long_text = "word " * 1000  # ~5000 chars, ~1250 tokens
    
    truncated = truncate_candidate_text(long_text, max_tokens=600)
    
    assert len(truncated) < len(long_text)
    assert estimate_tokens(truncated) <= 600


def test_cap_snippet_tokens():
    """Test capping snippet tokens."""
    long_snippet = "word " * 2000  # ~10000 chars, ~2500 tokens
    
    truncated, token_estimate = cap_snippet_tokens(long_snippet)
    
    assert token_estimate <= 800  # Default max
    assert len(truncated) < len(long_snippet)


def test_cap_evidence_pack_snippets():
    """Test capping EvidencePack snippet count."""
    snippets = [{"quote_text": f"snippet {i}", "token_estimate": 100} for i in range(30)]
    
    capped = cap_evidence_pack_snippets(snippets)
    
    assert len(capped) <= 20  # Default max_snippets


def test_cap_packet_a_tokens():
    """Test capping Packet A total tokens."""
    snippets = [
        {"quote_text": "word " * 500, "token_estimate": 500}  # ~2500 tokens each
        for i in range(10)
    ]  # Total: ~25000 tokens
    
    capped = cap_packet_a_tokens(snippets)
    
    total_tokens = sum(s.get("token_estimate", 0) for s in capped)
    assert total_tokens <= 8192  # Default packet_a_max_tokens


def test_cap_packet_b_tokens():
    """Test capping Packet B total tokens."""
    notes = [
        {"text": "word " * 200}  # ~500 tokens each
        for i in range(10)
    ]  # Total: ~5000 tokens
    
    capped = cap_packet_b_tokens(notes)
    
    total_tokens = sum(estimate_tokens(n.get("text", "")) for n in capped)
    assert total_tokens <= 2048  # Default packet_b_max_tokens


@patch("src.shared.runtime_budgets._get_db")
@patch("src.shared.runtime_budgets.SettingsService")
def test_get_output_max_tokens(mock_service_class, mock_get_db, mock_settings_service):
    """Test getting output max tokens for agent."""
    mock_get_db.return_value = Mock()
    mock_service_class.return_value = mock_settings_service
    
    max_tokens = get_output_max_tokens("synthesizer")
    
    assert max_tokens == 8192  # From mock settings


@patch("src.shared.runtime_budgets._get_db")
@patch("src.shared.runtime_budgets.SettingsService")
def test_get_critic_bounded_retry_max(mock_service_class, mock_get_db, mock_settings_service):
    """Test getting critic bounded retry max."""
    mock_get_db.return_value = Mock()
    mock_service_class.return_value = mock_settings_service
    
    retry_max = get_critic_bounded_retry_max()
    
    assert retry_max == 2  # From mock settings
