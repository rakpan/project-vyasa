"""
Unit tests for Prompt Registry.

Tests DB-backed prompt loading, caching, and fallback behavior.
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch

from src.shared.prompt_registry import get_prompt, clear_prompt_cache


@pytest.fixture
def mock_db_service():
    """Mock PromptProfileService."""
    service = Mock()
    profile = Mock()
    profile.template = "DB template v2"
    profile.output_type = "json"
    profile.constraints = Mock()
    profile.constraints.model_dump.return_value = {"citation_token_format": r"\cite{chunk:<id>}"}
    profile.required_fields = ["decision", "rationale"]
    profile.version = 2
    service.get_profile.return_value = profile
    return service


@patch("src.shared.prompt_registry._get_db")
@patch("src.shared.prompt_registry.PromptProfileService")
def test_get_prompt_from_db(mock_service_class, mock_get_db, mock_db_service):
    """Test loading prompt from DB."""
    mock_get_db.return_value = Mock()
    mock_service_class.return_value = mock_db_service
    
    profile = get_prompt("critic_verify", "default template")
    
    assert profile["template"] == "DB template v2"
    assert profile["version"] == 2
    assert profile["source"] == "db"
    assert profile["output_type"] == "json"


@patch("src.shared.prompt_registry._get_db")
def test_get_prompt_fallback_to_default(mock_get_db):
    """Test fallback to default when DB unavailable."""
    mock_get_db.return_value = None
    
    profile = get_prompt("critic_verify", "default template")
    
    assert profile["template"] == "default template"
    assert profile["source"] == "default"
    assert profile["version"] == 0


@patch("src.shared.prompt_registry._get_db")
@patch("src.shared.prompt_registry.PromptProfileService")
def test_get_prompt_caching(mock_service_class, mock_get_db, mock_db_service):
    """Test that prompts are cached with TTL."""
    mock_get_db.return_value = Mock()
    mock_service_class.return_value = mock_db_service
    
    # First call: should load from DB
    profile1 = get_prompt("critic_verify", "default")
    assert profile1["source"] == "db"
    
    # Second call: should use cache
    profile2 = get_prompt("critic_verify", "default")
    assert profile2["source"] == "db"
    
    # Service should only be called once (cached on second call)
    assert mock_db_service.get_profile.call_count == 1


def test_clear_prompt_cache():
    """Test clearing prompt cache."""
    # This is a simple function, just verify it doesn't crash
    clear_prompt_cache()
    clear_prompt_cache("critic_verify")
