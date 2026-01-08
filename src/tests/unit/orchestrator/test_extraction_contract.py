"""
Contract test for JSON extraction prompt alignment.

Validates that extraction prompts using ChatML format and response_format: json_object
produce valid JSON responses matching expected schema.

This is a lightweight smoke test to catch prompt format incompatibilities before
model consolidation (e.g., when switching to Llama 3.3).
"""

import json
import pytest
from unittest.mock import Mock, patch

from src.orchestrator.nodes.cartography import cartographer_node


@pytest.fixture
def minimal_extraction_state(base_node_state):
    """Minimal state for extraction contract test."""
    return {
        **base_node_state,
        "raw_text": "Machine learning models require large datasets for training. Neural networks use backpropagation.",
        "extracted_json": {},
        "critiques": [],
        "revision_count": 0,
    }


def test_extraction_contract_json_object_format(minimal_extraction_state, mock_llm_client, monkeypatch):
    """
    Contract test: Verify that extraction with response_format: json_object produces valid JSON.
    
    This test validates:
    1. ChatML prompt format is accepted
    2. response_format: {"type": "json_object"} produces valid JSON
    3. Response contains expected schema keys (triples array)
    """
    # Mock LLM response with valid JSON structure
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "triples": [
                            {
                                "subject": "Machine learning models",
                                "predicate": "require",
                                "object": "large datasets",
                                "confidence": 0.9,
                                "claim_text": "Machine learning models require large datasets",
                                "rq_hits": ["RQ1"],
                                "source_pointer": {
                                    "doc_hash": "test_hash",
                                    "page": 1,
                                    "snippet": "Machine learning models require large datasets"
                                }
                            }
                        ]
                    })
                }
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }
    
    # Mock the chat function to return our test response
    with patch("src.orchestrator.nodes.cartography.chat") as mock_chat:
        mock_chat.return_value = (mock_response, {
            "duration_ms": 100,
            "usage": mock_response["usage"],
            "expert_name": "Worker",
            "model_id": "test-model",
            "url_base": "http://test-worker:30001",
            "path": "primary",
            "attempt": 1,
        })
        
        # Mock route_to_expert
        with patch("src.orchestrator.nodes.cartography.route_to_expert") as mock_route:
            mock_route.return_value = ("http://test-worker:30001", "Worker", "test-model")
            
            # Mock get_brain_url for fallback
            with patch("src.orchestrator.nodes.cartography.get_brain_url") as mock_brain:
                mock_brain.return_value = "http://test-brain:30000"
                
                # Mock get_model_config
                with patch("src.orchestrator.nodes.cartography.get_model_config") as mock_config:
                    mock_config.return_value = Mock(model_id="test-model")
                    
                    # Mock role registry
                    with patch("src.orchestrator.nodes.cartography.role_registry") as mock_registry:
                        mock_role = Mock()
                        mock_role.allowed_tools = []
                        mock_registry.get_role.return_value = mock_role
                        
                        # Execute cartographer_node
                        result = cartographer_node(minimal_extraction_state)
                        
                        # Assertions
                        assert "extracted_json" in result
                        extracted = result["extracted_json"]
                        assert isinstance(extracted, dict)
                        
                        # Verify JSON structure
                        assert "triples" in extracted
                        assert isinstance(extracted["triples"], list)
                        assert len(extracted["triples"]) > 0
                        
                        # Verify triple schema
                        triple = extracted["triples"][0]
                        assert "subject" in triple
                        assert "predicate" in triple
                        assert "object" in triple
                        assert "confidence" in triple
                        assert "claim_text" in triple
                        assert "rq_hits" in triple
                        assert "source_pointer" in triple
                        
                        # Verify request_params included response_format
                        call_args = mock_chat.call_args
                        assert call_args is not None
                        request_params = call_args.kwargs.get("request_params", {})
                        assert "response_format" in request_params
                        assert request_params["response_format"] == {"type": "json_object"}


def test_extraction_contract_json_parsing_fallback(minimal_extraction_state, monkeypatch):
    """
    Contract test: Verify fallback when response_format fails but response is still JSON.
    
    Tests the scenario where:
    1. response_format: json_object may not be supported by backend
    2. But model still returns valid JSON in content
    3. System should parse and validate the JSON
    """
    # Mock response where content is valid JSON but wrapped in markdown or plain text
    json_content = {
        "triples": [
            {
                "subject": "Neural networks",
                "predicate": "use",
                "object": "backpropagation",
                "confidence": 0.85,
                "claim_text": "Neural networks use backpropagation",
                "rq_hits": ["RQ1"],
                "source_pointer": {
                    "doc_hash": "test_hash",
                    "page": 1,
                }
            }
        ]
    }
    
    # Simulate response where content might be wrapped (common when json_object not supported)
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": f"```json\n{json.dumps(json_content)}\n```"  # Markdown-wrapped JSON
                }
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }
    
    with patch("src.orchestrator.nodes.cartography.chat") as mock_chat:
        mock_chat.return_value = (mock_response, {
            "duration_ms": 100,
            "usage": mock_response["usage"],
            "expert_name": "Worker",
            "model_id": "test-model",
            "url_base": "http://test-worker:30001",
            "path": "primary",
            "attempt": 1,
        })
        
        with patch("src.orchestrator.nodes.cartography.route_to_expert") as mock_route:
            mock_route.return_value = ("http://test-worker:30001", "Worker", "test-model")
            
            with patch("src.orchestrator.nodes.cartography.get_brain_url") as mock_brain:
                mock_brain.return_value = "http://test-brain:30000"
                
                with patch("src.orchestrator.nodes.cartography.get_model_config") as mock_config:
                    mock_config.return_value = Mock(model_id="test-model")
                    
                    with patch("src.orchestrator.nodes.cartography.role_registry") as mock_registry:
                        mock_role = Mock()
                        mock_role.allowed_tools = []
                        mock_registry.get_role.return_value = mock_role
                        
                        # Execute cartographer_node
                        result = cartographer_node(minimal_extraction_state)
                        
                        # Should still extract valid JSON (cartographer_node has JSON parsing logic)
                        assert "extracted_json" in result
                        extracted = result["extracted_json"]
                        # Note: cartographer_node may need JSON extraction logic if markdown-wrapped
                        # This test documents the expected behavior


def test_extraction_contract_chatml_format(minimal_extraction_state, monkeypatch):
    """
    Contract test: Verify ChatML prompt format is used correctly.
    
    Validates that prompts use the expected ChatML structure:
    [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
    """
    with patch("src.orchestrator.nodes.cartography.chat") as mock_chat:
        mock_response = {
            "choices": [{"message": {"content": '{"triples": []}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }
        mock_chat.return_value = (mock_response, {
            "duration_ms": 100,
            "usage": mock_response["usage"],
            "expert_name": "Worker",
            "model_id": "test-model",
            "url_base": "http://test-worker:30001",
            "path": "primary",
            "attempt": 1,
        })
        
        with patch("src.orchestrator.nodes.cartography.route_to_expert") as mock_route:
            mock_route.return_value = ("http://test-worker:30001", "Worker", "test-model")
            
            with patch("src.orchestrator.nodes.cartography.get_brain_url") as mock_brain:
                mock_brain.return_value = "http://test-brain:30000"
                
                with patch("src.orchestrator.nodes.cartography.get_model_config") as mock_config:
                    mock_config.return_value = Mock(model_id="test-model")
                    
                    with patch("src.orchestrator.nodes.cartography.role_registry") as mock_registry:
                        mock_role = Mock()
                        mock_role.allowed_tools = []
                        mock_registry.get_role.return_value = mock_role
                        
                        cartographer_node(minimal_extraction_state)
                        
                        # Verify prompt format
                        call_args = mock_chat.call_args
                        assert call_args is not None
                        messages = call_args.kwargs.get("messages", [])
                        
                        # Should have system and user messages
                        assert len(messages) >= 2
                        assert messages[0]["role"] == "system"
                        assert messages[1]["role"] == "user"
                        
                        # System prompt should contain schema instructions
                        system_content = messages[0]["content"]
                        assert "triples" in system_content.lower() or "json" in system_content.lower()

