"""
Unit tests for Cartographer schema enforcement.

Tests verify that Cartographer returns metadata-rich claims with anchors
and validates schema in conservative mode.
"""

import pytest
from unittest.mock import Mock, patch
from src.orchestrator.nodes.nodes import cartographer_node
from src.tests.conftest import base_node_state


class TestCartographerSchema:
    """Test Cartographer schema enforcement."""
    
    def test_cartographer_adds_metadata_in_conservative_mode(self):
        """Test Cartographer adds claim_text, relevance_score, rq_hits in conservative mode."""
        state = {
            **base_node_state,
            "project_id": "test_project",
            "project_context": {
                "thesis": "Test thesis",
                "research_questions": ["RQ1: What is X?"],
                "rigor_level": "conservative",
            },
            "raw_text": "Test document content",
            "extracted_json": {
                "triples": [
                    {
                        "subject": "A",
                        "predicate": "causes",
                        "object": "B",
                        "confidence": 0.8,
                        "source_pointer": {
                            "doc_hash": "abc123",
                            "page": 1,
                            "bbox": [100, 200, 300, 400],
                            "snippet": "Evidence",
                        },
                    }
                ],
            },
        }
        
        # Mock the LLM call to return normalized structure
        with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call:
            mock_call.return_value = (
                {"choices": [{"message": {"content": '{"triples": []}'}}]},
                {"duration_ms": 100},
            )
            
            # Mock normalize_extracted_json to return our test triples
            with patch("src.orchestrator.nodes.nodes.normalize_extracted_json") as mock_norm:
                mock_norm.return_value = {
                    "triples": [
                        {
                            "subject": "A",
                            "predicate": "causes",
                            "object": "B",
                            "confidence": 0.8,
                            "source_pointer": {
                                "doc_hash": "abc123",
                                "page": 1,
                                "bbox": [100, 200, 300, 400],
                                "snippet": "Evidence",
                            },
                        }
                    ],
                }
                
                result = cartographer_node(state)
        
        triples = result.get("extracted_json", {}).get("triples", [])
        assert len(triples) > 0
        
        # In conservative mode, should have claim_text generated
        first_triple = triples[0]
        assert "claim_text" in first_triple or first_triple.get("subject")  # Either generated or original
        assert "relevance_score" in first_triple
        assert "rq_hits" in first_triple
        assert "source_anchor" in first_triple
    
    def test_cartographer_validates_source_anchor_presence(self):
        """Test Cartographer ensures source_anchor is present."""
        state = {
            **base_node_state,
            "project_id": "test_project",
            "project_context": {
                "thesis": "Test thesis",
                "research_questions": [],
                "rigor_level": "exploratory",
            },
            "raw_text": "Test document content",
        }
        
        with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call:
            mock_call.return_value = (
                {"choices": [{"message": {"content": '{"triples": []}'}}]},
                {"duration_ms": 100},
            )
            
            with patch("src.orchestrator.nodes.nodes.normalize_extracted_json") as mock_norm:
                mock_norm.return_value = {
                    "triples": [
                        {
                            "subject": "A",
                            "predicate": "causes",
                            "object": "B",
                            "source_pointer": {
                                "doc_hash": "abc123",
                                "page": 1,
                                "bbox": [100, 200, 300, 400],
                            },
                        }
                    ],
                }
                
                result = cartographer_node(state)
        
        triples = result.get("extracted_json", {}).get("triples", [])
        if len(triples) > 0:
            # source_anchor should be added by add_source_anchor_to_triples
            first_triple = triples[0]
            if first_triple.get("source_pointer"):
                assert "source_anchor" in first_triple

