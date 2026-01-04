"""
Unit tests for Prompt Registry.

Ensures:
- Returns default when Opik disabled
- Returns default on Opik exception
- Cache prevents repeated fetch calls within TTL
- Cache expires after TTL (using time mocking)
"""

import pytest
import time
from unittest.mock import MagicMock, patch, Mock
from typing import Dict, Any

from src.orchestrator.prompts.registry import (
    get_active_prompt,
    clear_prompt_cache,
    CACHE_TTL_SECONDS,
)
from src.orchestrator.prompts.defaults import (
    DEFAULT_CARTOGRAPHER_PROMPT,
    DEFAULT_CRITIC_PROMPT,
    DEFAULT_SYNTHESIZER_PROMPT,
)


@pytest.fixture
def mock_opik_config():
    """Mock Opik configuration."""
    with patch("src.orchestrator.prompts.registry.OPIK_ENABLED", True), \
         patch("src.orchestrator.prompts.registry.OPIK_BASE_URL", "http://opik:8000"), \
         patch("src.orchestrator.prompts.registry.OPIK_API_KEY", "test-key"), \
         patch("src.orchestrator.prompts.registry.OPIK_TIMEOUT_SECONDS", 2), \
         patch("src.orchestrator.prompts.registry.PROMPT_REGISTRY_ENABLED", True), \
         patch("src.orchestrator.prompts.registry.PROMPT_TAG", "production"):
        yield


@pytest.fixture
def mock_opik_disabled():
    """Mock Opik disabled configuration."""
    with patch("src.orchestrator.prompts.registry.PROMPT_REGISTRY_ENABLED", False), \
         patch("src.orchestrator.prompts.registry.OPIK_ENABLED", False):
        yield


@pytest.fixture
def clear_cache_before_test():
    """Clear cache before each test."""
    clear_prompt_cache()
    yield
    clear_prompt_cache()


class TestPromptRegistryDefaults:
    """Tests for default prompt behavior."""

    def test_returns_default_when_opik_disabled(
        self,
        mock_opik_disabled,
        clear_cache_before_test,
    ):
        """Asserts registry returns default when Opik is disabled."""
        default = "Default prompt text"
        result = get_active_prompt("test-prompt", default)
        
        assert result == default

    def test_returns_default_on_opik_exception(
        self,
        mock_opik_config,
        clear_cache_before_test,
    ):
        """Asserts registry returns default on Opik exception."""
        default = "Default prompt text"
        
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            mock_requests.get.side_effect = Exception("Connection failed")
            
            result = get_active_prompt("test-prompt", default)
            
            assert result == default

    def test_returns_default_on_opik_timeout(
        self,
        mock_opik_config,
        clear_cache_before_test,
    ):
        """Asserts registry returns default on Opik timeout."""
        default = "Default prompt text"
        
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            import requests
            mock_requests.get.side_effect = requests.exceptions.Timeout("Request timeout")
            
            result = get_active_prompt("test-prompt", default)
            
            assert result == default

    def test_returns_default_on_opik_404(
        self,
        mock_opik_config,
        clear_cache_before_test,
    ):
        """Asserts registry returns default when prompt not found in Opik."""
        default = "Default prompt text"
        
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_requests.get.return_value = mock_response
            
            result = get_active_prompt("test-prompt", default)
            
            assert result == default

    def test_returns_default_on_opik_empty_response(
        self,
        mock_opik_config,
        clear_cache_before_test,
    ):
        """Asserts registry returns default when Opik returns empty template."""
        default = "Default prompt text"
        
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"template": ""}  # Empty template
            mock_requests.get.return_value = mock_response
            
            result = get_active_prompt("test-prompt", default)
            
            assert result == default


class TestPromptRegistryCaching:
    """Tests for prompt caching behavior."""

    @patch("src.orchestrator.prompts.registry.time.time")
    def test_cache_prevents_repeated_fetch_calls(
        self,
        mock_time,
        mock_opik_config,
        clear_cache_before_test,
    ):
        """Asserts cache prevents repeated fetch calls within TTL."""
        default = "Default prompt text"
        opik_template = "Opik prompt template"
        
        # Mock time to return fixed timestamps
        current_time = 1000.0
        mock_time.return_value = current_time
        
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"template": opik_template}
            mock_requests.get.return_value = mock_response
            
            # First call should fetch from Opik
            result1 = get_active_prompt("test-prompt", default)
            assert result1 == opik_template
            assert mock_requests.get.call_count == 1
            
            # Second call within TTL should use cache
            result2 = get_active_prompt("test-prompt", default)
            assert result2 == opik_template
            assert mock_requests.get.call_count == 1  # No additional fetch

    @patch("src.orchestrator.prompts.registry.time.time")
    def test_cache_expires_after_ttl(
        self,
        mock_time,
        mock_opik_config,
        clear_cache_before_test,
    ):
        """Asserts cache expires after TTL and triggers new fetch."""
        default = "Default prompt text"
        opik_template_v1 = "Opik prompt template v1"
        opik_template_v2 = "Opik prompt template v2"
        
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            # First fetch
            mock_time.return_value = 1000.0
            mock_response.json.return_value = {"template": opik_template_v1}
            mock_requests.get.return_value = mock_response
            
            result1 = get_active_prompt("test-prompt", default)
            assert result1 == opik_template_v1
            assert mock_requests.get.call_count == 1
            
            # Second fetch after TTL expiration
            mock_time.return_value = 1000.0 + CACHE_TTL_SECONDS + 1  # Just past TTL
            mock_response.json.return_value = {"template": opik_template_v2}
            
            result2 = get_active_prompt("test-prompt", default)
            assert result2 == opik_template_v2
            assert mock_requests.get.call_count == 2  # New fetch triggered

    def test_cache_respects_tag(
        self,
        mock_opik_config,
        clear_cache_before_test,
    ):
        """Asserts cache respects tag parameter."""
        default = "Default prompt text"
        production_template = "Production template"
        staging_template = "Staging template"
        
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            # Fetch production tag
            mock_response.json.return_value = {"template": production_template}
            mock_requests.get.return_value = mock_response
            
            result1 = get_active_prompt("test-prompt", default, tag="production")
            assert result1 == production_template
            
            # Fetch staging tag (should be separate cache entry)
            mock_response.json.return_value = {"template": staging_template}
            result2 = get_active_prompt("test-prompt", default, tag="staging")
            assert result2 == staging_template
            
            # Verify both tags are cached separately
            assert mock_requests.get.call_count == 2


class TestPromptRegistryDefaultsModule:
    """Tests for default prompt templates."""

    def test_default_cartographer_prompt_exists(self):
        """Asserts DEFAULT_CARTOGRAPHER_PROMPT is defined."""
        assert DEFAULT_CARTOGRAPHER_PROMPT
        assert isinstance(DEFAULT_CARTOGRAPHER_PROMPT, str)
        assert len(DEFAULT_CARTOGRAPHER_PROMPT) > 0
        # Should mention JSON schema
        assert "JSON" in DEFAULT_CARTOGRAPHER_PROMPT or "json" in DEFAULT_CARTOGRAPHER_PROMPT
        # Should mention triples
        assert "triple" in DEFAULT_CARTOGRAPHER_PROMPT.lower()

    def test_default_critic_prompt_exists(self):
        """Asserts DEFAULT_CRITIC_PROMPT is defined."""
        assert DEFAULT_CRITIC_PROMPT
        assert isinstance(DEFAULT_CRITIC_PROMPT, str)
        assert len(DEFAULT_CRITIC_PROMPT) > 0
        # Should mention conflict detection
        assert "conflict" in DEFAULT_CRITIC_PROMPT.lower()
        # Should mention JSON output
        assert "JSON" in DEFAULT_CRITIC_PROMPT or "json" in DEFAULT_CRITIC_PROMPT

    def test_default_synthesizer_prompt_exists(self):
        """Asserts DEFAULT_SYNTHESIZER_PROMPT is defined."""
        assert DEFAULT_SYNTHESIZER_PROMPT
        assert isinstance(DEFAULT_SYNTHESIZER_PROMPT, str)
        assert len(DEFAULT_SYNTHESIZER_PROMPT) > 0
        # Should mention citation integrity
        assert "claim" in DEFAULT_SYNTHESIZER_PROMPT.lower() or "citation" in DEFAULT_SYNTHESIZER_PROMPT.lower()
        # Should mention claim_ids
        assert "claim_id" in DEFAULT_SYNTHESIZER_PROMPT.lower()


class TestPromptRegistryClearCache:
    """Tests for cache clearing functionality."""

    def test_clear_all_cache(
        self,
        mock_opik_config,
        clear_cache_before_test,
    ):
        """Asserts clear_prompt_cache clears all entries."""
        default = "Default prompt text"
        opik_template = "Opik template"
        
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"template": opik_template}
            mock_requests.get.return_value = mock_response
            
            # Fetch and cache
            get_active_prompt("prompt-1", default)
            get_active_prompt("prompt-2", default, tag="staging")
            
            # Clear all cache
            clear_prompt_cache()
            
            # Next fetch should hit Opik again
            get_active_prompt("prompt-1", default)
            assert mock_requests.get.call_count == 3  # 2 initial + 1 after clear

    def test_clear_specific_prompt_cache(
        self,
        mock_opik_config,
        clear_cache_before_test,
    ):
        """Asserts clear_prompt_cache clears specific prompt."""
        default = "Default prompt text"
        opik_template = "Opik template"
        
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"template": opik_template}
            mock_requests.get.return_value = mock_response
            
            # Fetch and cache two prompts
            get_active_prompt("prompt-1", default)
            get_active_prompt("prompt-2", default)
            
            # Clear only prompt-1
            clear_prompt_cache(prompt_name="prompt-1")
            
            # Fetch prompt-1 again should hit Opik, prompt-2 should use cache
            get_active_prompt("prompt-1", default)
            get_active_prompt("prompt-2", default)
            
            # Should have 3 calls: 2 initial + 1 after clear for prompt-1
            assert mock_requests.get.call_count == 3

    def test_clear_specific_tag_cache(
        self,
        mock_opik_config,
        clear_cache_before_test,
    ):
        """Asserts clear_prompt_cache clears specific tag."""
        default = "Default prompt text"
        opik_template = "Opik template"
        
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"template": opik_template}
            mock_requests.get.return_value = mock_response
            
            # Fetch and cache with different tags
            get_active_prompt("test-prompt", default, tag="production")
            get_active_prompt("test-prompt", default, tag="staging")
            
            # Clear only production tag
            clear_prompt_cache(prompt_name="test-prompt", tag="production")
            
            # Fetch production should hit Opik, staging should use cache
            get_active_prompt("test-prompt", default, tag="production")
            get_active_prompt("test-prompt", default, tag="staging")
            
            # Should have 3 calls: 2 initial + 1 after clear for production
            assert mock_requests.get.call_count == 3


class TestPromptRegistryConfig:
    """Tests for configuration handling."""

    def test_uses_configured_tag_when_not_provided(
        self,
        mock_opik_config,
        clear_cache_before_test,
    ):
        """Asserts registry uses PROMPT_TAG from config when tag not provided."""
        default = "Default prompt text"
        opik_template = "Opik template"
        
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"template": opik_template}
            mock_requests.get.return_value = mock_response
            
            # Call without tag (should use PROMPT_TAG from config)
            result = get_active_prompt("test-prompt", default)
            
            assert result == opik_template
            # Verify request was made with configured tag
            call_args = mock_requests.get.call_args
            assert call_args[1]["params"]["tag"] == "production"  # From mock_opik_config fixture

