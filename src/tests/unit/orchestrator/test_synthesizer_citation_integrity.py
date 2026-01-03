"""
Unit tests for Synthesizer citation integrity guard.

Tests verify that Synthesizer enforces claim bindings and rejects
blocks without bindings in conservative mode.
"""

import pytest
from unittest.mock import Mock, patch
from src.orchestrator.nodes.nodes import synthesizer_node
from src.tests.conftest import base_node_state


class TestSynthesizerCitationIntegrity:
    """Test Synthesizer citation integrity enforcement."""
    
    def test_synthesizer_rejects_block_without_bindings_conservative(self):
        """Test Synthesizer rejects blocks without claim bindings in conservative mode."""
        state = {
            **base_node_state,
            "project_id": "test_project",
            "project_context": {
                "thesis": "Test thesis",
                "research_questions": [],
                "rigor_level": "conservative",
            },
            "synthesis": "This is a paragraph without any claim bindings.",
            "extracted_json": {
                "triples": [
                    {
                        "subject": "A",
                        "predicate": "causes",
                        "object": "B",
                    }
                ],
            },
        }
        
        result = synthesizer_node(state)
        
        # In conservative mode, should reject block without bindings
        assert result.get("synthesis") == ""
        assert "synthesis_error" in result
        assert "no claim bindings" in result.get("synthesis_error", "").lower()
    
    def test_synthesizer_allows_block_without_bindings_exploratory(self):
        """Test Synthesizer allows blocks without bindings in exploratory mode (with warning)."""
        state = {
            **base_node_state,
            "project_id": "test_project",
            "project_context": {
                "thesis": "Test thesis",
                "research_questions": [],
                "rigor_level": "exploratory",
            },
            "synthesis": "This is a paragraph without any claim bindings.",
            "extracted_json": {
                "triples": [],
            },
        }
        
        result = synthesizer_node(state)
        
        # In exploratory mode, should allow but warn
        assert result.get("synthesis") != ""
        assert "synthesis_error" not in result
    
    def test_synthesizer_accepts_block_with_inline_bindings(self):
        """Test Synthesizer accepts blocks with inline claim bindings."""
        state = {
            **base_node_state,
            "project_id": "test_project",
            "project_context": {
                "thesis": "Test thesis",
                "research_questions": [],
                "rigor_level": "conservative",
            },
            "synthesis": "This paragraph references [[claim_id_123]] and [[claim_id_456]].",
            "extracted_json": {
                "triples": [],
            },
        }
        
        result = synthesizer_node(state)
        
        # Should accept block with inline bindings
        assert result.get("synthesis") != ""
        assert "synthesis_error" not in result
        assert "claim_id_123" in result.get("synthesis", "")
    
    def test_synthesizer_uses_context_wrapper(self):
        """Test Synthesizer uses wrap_prompt_with_context."""
        state = {
            **base_node_state,
            "project_id": "test_project",
            "project_context": {
                "thesis": "Test thesis",
                "research_questions": ["RQ1"],
                "anti_scope": ["Mobile"],
                "rigor_level": "conservative",
            },
            "synthesis": "Test [[claim_1]]",
            "extracted_json": {"triples": []},
        }
        
        with patch("src.orchestrator.nodes.nodes.wrap_prompt_with_context") as mock_wrap:
            mock_wrap.return_value = "Wrapped prompt"
            
            result = synthesizer_node(state)
            
            # Verify wrapper was called
            assert mock_wrap.called
            # Verify synthesis passed through
            assert result.get("synthesis") == "Test [[claim_1]]"

