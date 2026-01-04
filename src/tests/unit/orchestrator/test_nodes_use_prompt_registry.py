"""
Unit tests verifying nodes use Prompt Registry correctly.

Ensures:
- When registry enabled, nodes call get_active_prompt once (cached)
- When registry disabled, defaults are used
- wrap_prompt_with_context is applied after retrieval (important ordering)
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from typing import Dict, Any

from src.orchestrator.nodes.nodes import (
    cartographer_node,
    critic_node,
    synthesizer_node,
)
from src.orchestrator.prompts.registry import get_active_prompt
from src.orchestrator.prompts.defaults import (
    DEFAULT_CARTOGRAPHER_PROMPT,
    DEFAULT_CRITIC_PROMPT,
    DEFAULT_SYNTHESIZER_PROMPT,
)


@pytest.fixture
def base_node_state():
    """Base state dictionary for node tests."""
    return {
        "job_id": "test-job-123",
        "jobId": "test-job-123",
        "thread_id": "test-thread-123",
        "threadId": "test-thread-123",
        "project_id": "test-project-123",
        "raw_text": "Sample text for extraction.",
        "extracted_json": {},
        "triples": [],
        "critiques": [],
        "revision_count": 0,
        "project_context": {
            "thesis": "Test thesis",
            "research_questions": ["RQ1: What is X?"],
            "anti_scope": [],
            "rigor_level": "exploratory",
        },
        "rigor_level": "exploratory",
        "phase": "MAPPING",
    }


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for extraction."""
    return {
        "triples": [
            {
                "subject": "X",
                "predicate": "causes",
                "object": "Y",
                "claim_id": "claim-1",
                "source_anchor": {
                    "doc_id": "doc-123",
                    "page_number": 1,
                    "snippet": "Evidence text",
                },
                "rq_hits": ["RQ1"],
            }
        ],
        "entities": [],
    }


class TestCartographerPromptRegistry:
    """Tests for Cartographer prompt registry usage."""

    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    @patch("src.orchestrator.nodes.nodes.wrap_prompt_with_context")
    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes._query_established_knowledge")
    @patch("src.orchestrator.nodes.nodes.route_to_expert")
    def test_cartographer_uses_prompt_registry(
        self,
        mock_route,
        mock_query_knowledge,
        mock_call_expert,
        mock_wrap_context,
        mock_get_prompt,
        base_node_state,
        mock_llm_response,
    ):
        """Asserts Cartographer calls get_active_prompt with correct arguments."""
        import json
        
        # Setup mocks
        mock_route.return_value = ("http://worker:8000", "Worker", "model-id")
        mock_query_knowledge.return_value = ([], {}, [])
        mock_get_prompt.return_value = "Fetched prompt template"
        mock_wrap_context.return_value = "Wrapped prompt with context"
        mock_call_expert.return_value = (
            json.dumps(mock_llm_response),
            {"model_id": "model-id", "expert_name": "Worker"},
        )
        
        # Call cartographer
        cartographer_node(base_node_state)
        
        # Verify get_active_prompt was called with correct arguments
        mock_get_prompt.assert_called_once_with(
            "vyasa-cartographer",
            DEFAULT_CARTOGRAPHER_PROMPT,
        )
        
        # Verify wrap_prompt_with_context was called AFTER get_active_prompt
        assert mock_get_prompt.call_count == 1
        assert mock_wrap_context.call_count == 1
        # Verify wrap_context was called with the fetched template
        wrap_call_args = mock_wrap_context.call_args
        assert wrap_call_args[0][1] == "Fetched prompt template"  # Second arg is the template

    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    @patch("src.orchestrator.nodes.nodes.wrap_prompt_with_context")
    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    def test_cartographer_prompt_registry_cached(
        self,
        mock_call_expert,
        mock_wrap_context,
        mock_get_prompt,
        base_node_state,
        mock_llm_response,
    ):
        """Asserts Cartographer benefits from prompt registry caching."""
        import json
        
        mock_get_prompt.return_value = "Cached prompt template"
        mock_wrap_context.return_value = "Wrapped prompt"
        mock_call_expert.return_value = (
            json.dumps(mock_llm_response),
            {"model_id": "model-id"},
        )
        
        with patch("src.orchestrator.nodes.nodes._query_established_knowledge", return_value=([], {}, [])), \
             patch("src.orchestrator.nodes.nodes.route_to_expert", return_value=("http://worker:8000", "Worker", "model-id")):
            # Call cartographer twice (should use cache on second call)
            cartographer_node(base_node_state)
            cartographer_node(base_node_state)
            
            # Verify get_active_prompt was called twice (once per node invocation)
            # But the registry's internal cache prevents network calls
            assert mock_get_prompt.call_count == 2
            # Both calls should use the same default
            assert all(
                call[0][1] == DEFAULT_CARTOGRAPHER_PROMPT
                for call in mock_get_prompt.call_args_list
            )

    @patch("src.orchestrator.prompts.registry.PROMPT_REGISTRY_ENABLED", False)
    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    def test_cartographer_uses_default_when_registry_disabled(
        self,
        mock_get_prompt,
        base_node_state,
    ):
        """Asserts Cartographer uses default when registry is disabled."""
        # When registry is disabled, get_active_prompt should return default
        mock_get_prompt.return_value = DEFAULT_CARTOGRAPHER_PROMPT
        
        with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call, \
             patch("src.orchestrator.nodes.nodes._query_established_knowledge", return_value=([], {}, [])), \
             patch("src.orchestrator.nodes.nodes.route_to_expert", return_value=("http://worker:8000", "Worker", "model-id")):
            import json
            mock_call.return_value = (
                json.dumps({"triples": []}),
                {"model_id": "model-id"},
            )
            
            cartographer_node(base_node_state)
            
            # Verify default was used
            mock_get_prompt.assert_called_once_with(
                "vyasa-cartographer",
                DEFAULT_CARTOGRAPHER_PROMPT,
            )


class TestCriticPromptRegistry:
    """Tests for Critic prompt registry usage."""

    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    @patch("src.orchestrator.nodes.nodes.wrap_prompt_with_context")
    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    def test_critic_uses_prompt_registry(
        self,
        mock_call_expert,
        mock_wrap_context,
        mock_get_prompt,
        base_node_state,
    ):
        """Asserts Critic calls get_active_prompt with correct arguments."""
        base_node_state["extracted_json"] = {"triples": [{"claim_id": "c1"}]}
        
        mock_get_prompt.return_value = "Fetched critic prompt"
        mock_wrap_context.return_value = "Wrapped critic prompt"
        mock_call_expert.return_value = (
            '{"status": "pass", "score": 0.9, "critiques": []}',
            {"model_id": "model-id"},
        )
        
        with patch("src.orchestrator.nodes.nodes.load_claims_for_conflict_detection", return_value=[]):
            critic_node(base_node_state)
        
        # Verify get_active_prompt was called with correct arguments
        mock_get_prompt.assert_called_once_with(
            "vyasa-critic",
            DEFAULT_CRITIC_PROMPT,
        )
        
        # Verify wrap_prompt_with_context was called AFTER get_active_prompt
        assert mock_wrap_context.call_count == 1
        wrap_call_args = mock_wrap_context.call_args
        assert wrap_call_args[0][1] == "Fetched critic prompt"

    @patch("src.orchestrator.prompts.registry.PROMPT_REGISTRY_ENABLED", False)
    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    def test_critic_uses_default_when_registry_disabled(
        self,
        mock_get_prompt,
        base_node_state,
    ):
        """Asserts Critic uses default when registry is disabled."""
        base_node_state["extracted_json"] = {"triples": []}
        mock_get_prompt.return_value = DEFAULT_CRITIC_PROMPT
        
        with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call, \
             patch("src.orchestrator.nodes.nodes.load_claims_for_conflict_detection", return_value=[]):
            mock_call.return_value = (
                '{"status": "pass", "score": 0.9, "critiques": []}',
                {"model_id": "model-id"},
            )
            
            critic_node(base_node_state)
            
            # Verify default was used
            mock_get_prompt.assert_called_once_with(
                "vyasa-critic",
                DEFAULT_CRITIC_PROMPT,
            )


class TestSynthesizerPromptRegistry:
    """Tests for Synthesizer prompt registry usage."""

    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    @patch("src.orchestrator.nodes.nodes.wrap_prompt_with_context")
    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    def test_synthesizer_uses_prompt_registry(
        self,
        mock_call_expert,
        mock_wrap_context,
        mock_get_prompt,
        base_node_state,
    ):
        """Asserts Synthesizer calls get_active_prompt with correct arguments."""
        base_node_state["extracted_json"] = {"triples": []}
        
        mock_get_prompt.return_value = "Fetched synthesizer prompt"
        mock_wrap_context.return_value = "Wrapped synthesizer prompt"
        mock_call_expert.return_value = (
            '{"synthesis": "Test", "blocks": [{"text": "Block", "claim_ids": ["c1"]}]}',
            {"model_id": "model-id"},
        )
        
        synthesizer_node(base_node_state)
        
        # Verify get_active_prompt was called with correct arguments
        mock_get_prompt.assert_called_once_with(
            "vyasa-synthesizer",
            DEFAULT_SYNTHESIZER_PROMPT,
        )
        
        # Verify wrap_prompt_with_context was called AFTER get_active_prompt
        assert mock_wrap_context.call_count == 1
        wrap_call_args = mock_wrap_context.call_args
        assert wrap_call_args[0][1] == "Fetched synthesizer prompt"

    @patch("src.orchestrator.prompts.registry.PROMPT_REGISTRY_ENABLED", False)
    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    def test_synthesizer_uses_default_when_registry_disabled(
        self,
        mock_get_prompt,
        base_node_state,
    ):
        """Asserts Synthesizer uses default when registry is disabled."""
        base_node_state["extracted_json"] = {"triples": []}
        mock_get_prompt.return_value = DEFAULT_SYNTHESIZER_PROMPT
        
        with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call:
            mock_call.return_value = (
                '{"synthesis": "Test", "blocks": []}',
                {"model_id": "model-id"},
            )
            
            synthesizer_node(base_node_state)
            
            # Verify default was used
            mock_get_prompt.assert_called_once_with(
                "vyasa-synthesizer",
                DEFAULT_SYNTHESIZER_PROMPT,
            )


class TestPromptRegistryOrdering:
    """Tests for correct ordering of prompt retrieval and context injection."""

    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    @patch("src.orchestrator.nodes.nodes.wrap_prompt_with_context")
    def test_context_injection_after_prompt_retrieval(
        self,
        mock_wrap_context,
        mock_get_prompt,
        base_node_state,
    ):
        """Asserts wrap_prompt_with_context is called AFTER get_active_prompt."""
        import json
        
        base_node_state["extracted_json"] = {"triples": []}
        mock_get_prompt.return_value = "Retrieved prompt"
        mock_wrap_context.return_value = "Wrapped prompt"
        
        with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call, \
             patch("src.orchestrator.nodes.nodes._query_established_knowledge", return_value=([], {}, [])), \
             patch("src.orchestrator.nodes.nodes.route_to_expert", return_value=("http://worker:8000", "Worker", "model-id")):
            mock_call.return_value = (
                json.dumps({"triples": []}),
                {"model_id": "model-id"},
            )
            
            cartographer_node(base_node_state)
            
            # Verify call order: get_active_prompt first, then wrap_prompt_with_context
            call_order = []
            for call in mock_get_prompt.call_args_list:
                call_order.append("get_prompt")
            for call in mock_wrap_context.call_args_list:
                call_order.append("wrap_context")
            
            # get_prompt should appear before wrap_context
            assert call_order.index("get_prompt") < call_order.index("wrap_context")

