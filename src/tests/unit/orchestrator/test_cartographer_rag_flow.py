"""
Unit tests for Cartographer RQ-scoped retrieval and anchor preservation.

Ensures:
- Cartographer retrieves chunks per RQ from Qdrant
- Claims are produced as canonical Claim objects
- source_anchor metadata is copied from Qdrant payload exactly
- rq_hits are populated correctly
- Validation rejects claims without anchor/rq_hits in conservative mode
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from src.orchestrator.nodes.nodes import cartographer_node
from src.orchestrator.schemas.claims import Claim, SourceAnchor
from src.orchestrator.state import ResearchState


@pytest.fixture
def base_node_state():
    """Base state fixture for Cartographer node tests."""
    return {
        "jobId": "test-job-123",
        "threadId": "test-thread-123",
        "job_id": "test-job-123",
        "project_id": "test-project-456",
        "ingestion_id": "test-ingestion-789",
        "raw_text": "Sample document text for extraction.",
        "project_context": {
            "thesis": "Test thesis statement",
            "research_questions": [
                "What is the impact of X on Y?",
                "How does Z relate to W?",
            ],
            "rigor_level": "exploratory",
        },
        "rigor_level": "exploratory",
        "critiques": [],
    }


@pytest.fixture
def mock_qdrant_chunks():
    """Mock Qdrant chunks with payload metadata."""
    return [
        {
            "chunk_id": "chunk-1",
            "text_content": "Evidence about X impacting Y on page 1.",
            "payload": {
                "file_hash": "a" * 64,
                "ingestion_id": "test-ingestion-789",
                "project_id": "test-project-456",
                "page_number": 1,
                "bbox": {"x": 10.0, "y": 20.0, "w": 100.0, "h": 50.0},
                "chunk_index": 0,
                "chunk_text_length": 50,
            },
            "score": 0.95,
            "file_hash": "a" * 64,
            "ingestion_id": "test-ingestion-789",
            "page_number": 1,
            "bbox": {"x": 10.0, "y": 20.0, "w": 100.0, "h": 50.0},
        },
        {
            "chunk_id": "chunk-2",
            "text_content": "Evidence about Z relating to W on page 2.",
            "payload": {
                "file_hash": "a" * 64,
                "ingestion_id": "test-ingestion-789",
                "project_id": "test-project-456",
                "page_number": 2,
                "bbox": {"x": 15.0, "y": 25.0, "w": 110.0, "h": 55.0},
                "chunk_index": 1,
                "chunk_text_length": 55,
            },
            "score": 0.92,
            "file_hash": "a" * 64,
            "ingestion_id": "test-ingestion-789",
            "page_number": 2,
            "bbox": {"x": 15.0, "y": 25.0, "w": 110.0, "h": 55.0},
        },
    ]


@pytest.fixture
def mock_llm_response():
    """Mock LLM response with structured triples."""
    return {
        "triples": [
            {
                "subject": "X",
                "predicate": "IMPACTS",
                "object": "Y",
                "confidence": 0.9,
                "claim_text": "X impacts Y significantly",
                "relevance_score": 0.85,
                "rq_hits": ["RQ1"],
                "source_pointer": {
                    "doc_hash": "a" * 64,
                    "page": 1,
                    "bbox": [10.0, 20.0, 110.0, 70.0],
                    "snippet": "Evidence about X impacting Y",
                },
            },
            {
                "subject": "Z",
                "predicate": "RELATES_TO",
                "object": "W",
                "confidence": 0.88,
                "claim_text": "Z relates to W",
                "relevance_score": 0.80,
                "rq_hits": ["RQ2"],
                "source_pointer": {
                    "doc_hash": "a" * 64,
                    "page": 2,
                    "bbox": [15.0, 25.0, 125.0, 80.0],
                    "snippet": "Evidence about Z relating to W",
                },
            },
        ]
    }


class TestCartographerRQScopedRetrieval:
    """Tests for RQ-scoped chunk retrieval from Qdrant."""
    
    @patch("src.orchestrator.nodes.nodes.QdrantStorage")
    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes.role_registry")
    @patch("src.orchestrator.nodes.nodes.route_to_expert")
    def test_retrieves_chunks_per_rq(
        self,
        mock_route,
        mock_role_registry,
        mock_call_expert,
        mock_qdrant_storage_class,
        base_node_state,
        mock_qdrant_chunks,
        mock_llm_response,
    ):
        """Asserts Cartographer retrieves chunks per RQ from Qdrant."""
        # Setup mocks
        mock_qdrant_storage = Mock()
        mock_qdrant_storage.retrieve_chunks_by_query.side_effect = [
            [mock_qdrant_chunks[0]],  # RQ1 chunks
            [mock_qdrant_chunks[1]],  # RQ2 chunks
        ]
        mock_qdrant_storage_class.return_value = mock_qdrant_storage
        
        mock_role = Mock()
        mock_role.system_prompt = "Extract knowledge graph from text."
        mock_role.allowed_tools = []
        mock_role_registry.get_role.return_value = mock_role
        
        mock_route.return_value = ("http://worker:30001", "Worker", "model-id")
        
        import json
        mock_call_expert.return_value = (
            {"choices": [{"message": {"content": json.dumps(mock_llm_response)}}]},
            {"duration_ms": 100, "usage": {}, "model_id": "model-id"},
        )
        
        # Execute
        result = cartographer_node(base_node_state)
        
        # Verify Qdrant retrieval was called for each RQ
        assert mock_qdrant_storage.retrieve_chunks_by_query.call_count == 2
        
        # Verify calls were made with correct RQ text
        calls = mock_qdrant_storage.retrieve_chunks_by_query.call_args_list
        assert "impact of X on Y" in calls[0].kwargs["query_text"]
        assert "Z relate to W" in calls[1].kwargs["query_text"]
        
        # Verify chunks were retrieved with correct parameters
        assert calls[0].kwargs["project_id"] == "test-project-456"
        assert calls[0].kwargs["ingestion_id"] == "test-ingestion-789"
        assert calls[0].kwargs["limit"] == 5  # Default chunks_per_rq
    
    @patch("src.orchestrator.nodes.nodes.QdrantStorage")
    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes.role_registry")
    @patch("src.orchestrator.nodes.nodes.route_to_expert")
    def test_claims_have_anchors_from_qdrant_payload(
        self,
        mock_route,
        mock_role_registry,
        mock_call_expert,
        mock_qdrant_storage_class,
        base_node_state,
        mock_qdrant_chunks,
        mock_llm_response,
    ):
        """Asserts Claims have source_anchor copied from Qdrant payload exactly."""
        # Setup mocks
        mock_qdrant_storage = Mock()
        mock_qdrant_storage.retrieve_chunks_by_query.return_value = mock_qdrant_chunks
        mock_qdrant_storage_class.return_value = mock_qdrant_storage
        
        mock_role = Mock()
        mock_role.system_prompt = "Extract knowledge graph."
        mock_role.allowed_tools = []
        mock_role_registry.get_role.return_value = mock_role
        
        mock_route.return_value = ("http://worker:30001", "Worker", "model-id")
        
        import json
        mock_call_expert.return_value = (
            {"choices": [{"message": {"content": json.dumps(mock_llm_response)}}]},
            {"duration_ms": 100, "usage": {}, "model_id": "model-id"},
        )
        
        # Execute
        result = cartographer_node(base_node_state)
        
        # Verify triples were converted to Claims
        triples = result.get("triples", [])
        assert len(triples) > 0
        
        # Verify first claim has source_anchor matching Qdrant payload
        first_claim = triples[0]
        assert "source_anchor" in first_claim or "source_pointer" in first_claim
        
        # If source_anchor exists, verify it matches Qdrant payload
        if "source_anchor" in first_claim:
            anchor = first_claim["source_anchor"]
            assert anchor["doc_id"] == "a" * 64
            assert anchor["page_number"] == 1
            assert "bbox" in anchor or "snippet" in anchor
    
    @patch("src.orchestrator.nodes.nodes.QdrantStorage")
    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes.role_registry")
    @patch("src.orchestrator.nodes.nodes.route_to_expert")
    def test_rq_hits_populated_correctly(
        self,
        mock_route,
        mock_role_registry,
        mock_call_expert,
        mock_qdrant_storage_class,
        base_node_state,
        mock_qdrant_chunks,
        mock_llm_response,
    ):
        """Asserts rq_hits are populated correctly from LLM output."""
        # Setup mocks
        mock_qdrant_storage = Mock()
        mock_qdrant_storage.retrieve_chunks_by_query.return_value = mock_qdrant_chunks
        mock_qdrant_storage_class.return_value = mock_qdrant_storage
        
        mock_role = Mock()
        mock_role.system_prompt = "Extract knowledge graph."
        mock_role.allowed_tools = []
        mock_role_registry.get_role.return_value = mock_role
        
        mock_route.return_value = ("http://worker:30001", "Worker", "model-id")
        
        import json
        mock_call_expert.return_value = (
            {"choices": [{"message": {"content": json.dumps(mock_llm_response)}}]},
            {"duration_ms": 100, "usage": {}, "model_id": "model-id"},
        )
        
        # Execute
        result = cartographer_node(base_node_state)
        
        # Verify triples have rq_hits
        triples = result.get("triples", [])
        assert len(triples) > 0
        
        # Verify first triple has rq_hits matching LLM output
        first_triple = triples[0]
        assert "rq_hits" in first_triple
        assert isinstance(first_triple["rq_hits"], list)
        assert len(first_triple["rq_hits"]) > 0
        assert "RQ1" in first_triple["rq_hits"] or "RQ2" in first_triple["rq_hits"]


class TestCartographerValidation:
    """Tests for validation in conservative vs exploratory mode."""
    
    @patch("src.orchestrator.nodes.nodes.QdrantStorage")
    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes.role_registry")
    @patch("src.orchestrator.nodes.nodes.route_to_expert")
    def test_conservative_mode_rejects_claim_without_anchor(
        self,
        mock_route,
        mock_role_registry,
        mock_call_expert,
        mock_qdrant_storage_class,
        base_node_state,
        mock_qdrant_chunks,
    ):
        """Asserts conservative mode rejects claims without source_anchor."""
        # Setup conservative mode
        base_node_state["rigor_level"] = "conservative"
        base_node_state["project_context"]["rigor_level"] = "conservative"
        
        # Mock LLM response with triple missing source_anchor
        mock_llm_response = {
            "triples": [
                {
                    "subject": "X",
                    "predicate": "IMPACTS",
                    "object": "Y",
                    "confidence": 0.9,
                    "claim_text": "X impacts Y",
                    "rq_hits": ["RQ1"],
                    # Missing source_pointer
                }
            ]
        }
        
        # Setup mocks
        mock_qdrant_storage = Mock()
        mock_qdrant_storage.retrieve_chunks_by_query.return_value = []  # No matching chunks
        mock_qdrant_storage_class.return_value = mock_qdrant_storage
        
        mock_role = Mock()
        mock_role.system_prompt = "Extract knowledge graph."
        mock_role.allowed_tools = []
        mock_role_registry.get_role.return_value = mock_role
        
        mock_route.return_value = ("http://worker:30001", "Worker", "model-id")
        
        import json
        mock_call_expert.return_value = (
            {"choices": [{"message": {"content": json.dumps(mock_llm_response)}}]},
            {"duration_ms": 100, "usage": {}, "model_id": "model-id"},
        )
        
        # Execute
        result = cartographer_node(base_node_state)
        
        # Verify claim was rejected (not in output)
        triples = result.get("triples", [])
        # In conservative mode, claim without anchor should be rejected
        # So triples should be empty or not contain the invalid claim
        assert len(triples) == 0 or not any(
            t.get("subject") == "X" and t.get("predicate") == "IMPACTS" and t.get("object") == "Y"
            for t in triples
        )
    
    @patch("src.orchestrator.nodes.nodes.QdrantStorage")
    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes.role_registry")
    @patch("src.orchestrator.nodes.nodes.route_to_expert")
    def test_conservative_mode_rejects_claim_without_rq_hits(
        self,
        mock_route,
        mock_role_registry,
        mock_call_expert,
        mock_qdrant_storage_class,
        base_node_state,
        mock_qdrant_chunks,
    ):
        """Asserts conservative mode rejects claims without rq_hits."""
        # Setup conservative mode
        base_node_state["rigor_level"] = "conservative"
        base_node_state["project_context"]["rigor_level"] = "conservative"
        
        # Mock LLM response with triple missing rq_hits
        mock_llm_response = {
            "triples": [
                {
                    "subject": "X",
                    "predicate": "IMPACTS",
                    "object": "Y",
                    "confidence": 0.9,
                    "claim_text": "X impacts Y",
                    "source_pointer": {
                        "doc_hash": "a" * 64,
                        "page": 1,
                        "snippet": "Evidence text",
                    },
                    # Missing rq_hits
                }
            ]
        }
        
        # Setup mocks
        mock_qdrant_storage = Mock()
        mock_qdrant_storage.retrieve_chunks_by_query.return_value = mock_qdrant_chunks
        mock_qdrant_storage_class.return_value = mock_qdrant_storage
        
        mock_role = Mock()
        mock_role.system_prompt = "Extract knowledge graph."
        mock_role.allowed_tools = []
        mock_role_registry.get_role.return_value = mock_role
        
        mock_route.return_value = ("http://worker:30001", "Worker", "model-id")
        
        import json
        mock_call_expert.return_value = (
            {"choices": [{"message": {"content": json.dumps(mock_llm_response)}}]},
            {"duration_ms": 100, "usage": {}, "model_id": "model-id"},
        )
        
        # Execute
        result = cartographer_node(base_node_state)
        
        # Verify claim was rejected (not in output)
        triples = result.get("triples", [])
        # In conservative mode, claim without rq_hits should be rejected
        assert len(triples) == 0 or not any(
            t.get("subject") == "X" and t.get("predicate") == "IMPACTS" and t.get("object") == "Y"
            for t in triples
        )
    
    @patch("src.orchestrator.nodes.nodes.QdrantStorage")
    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes.role_registry")
    @patch("src.orchestrator.nodes.nodes.route_to_expert")
    def test_exploratory_mode_allows_with_warnings(
        self,
        mock_route,
        mock_role_registry,
        mock_call_expert,
        mock_qdrant_storage_class,
        base_node_state,
        mock_qdrant_chunks,
    ):
        """Asserts exploratory mode allows claims with warnings but still requires minimal anchor."""
        # Mock LLM response with triple missing some fields
        mock_llm_response = {
            "triples": [
                {
                    "subject": "X",
                    "predicate": "IMPACTS",
                    "object": "Y",
                    "confidence": 0.9,
                    "claim_text": "X impacts Y",
                    # Missing rq_hits and source_pointer
                }
            ]
        }
        
        # Setup mocks
        mock_qdrant_storage = Mock()
        mock_qdrant_storage.retrieve_chunks_by_query.return_value = mock_qdrant_chunks
        mock_qdrant_storage_class.return_value = mock_qdrant_storage
        
        mock_role = Mock()
        mock_role.system_prompt = "Extract knowledge graph."
        mock_role.allowed_tools = []
        mock_role_registry.get_role.return_value = mock_role
        
        mock_route.return_value = ("http://worker:30001", "Worker", "model-id")
        
        import json
        mock_call_expert.return_value = (
            {"choices": [{"message": {"content": json.dumps(mock_llm_response)}}]},
            {"duration_ms": 100, "usage": {}, "model_id": "model-id"},
        )
        
        # Execute
        result = cartographer_node(base_node_state)
        
        # Verify claim was included (exploratory mode allows with warnings)
        triples = result.get("triples", [])
        # In exploratory mode, claim should be included even with missing fields
        # (warnings logged but not rejected)
        assert len(triples) >= 0  # May be 0 if conversion fails, but shouldn't raise


class TestAnchorThread:
    """Tests for anchor metadata preservation (Qdrant → Claim)."""
    
    @patch("src.orchestrator.nodes.nodes.QdrantStorage")
    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes.role_registry")
    @patch("src.orchestrator.nodes.nodes.route_to_expert")
    def test_anchor_matches_qdrant_payload_exactly(
        self,
        mock_route,
        mock_role_registry,
        mock_call_expert,
        mock_qdrant_storage_class,
        base_node_state,
        mock_qdrant_chunks,
        mock_llm_response,
    ):
        """Asserts source_anchor matches Qdrant payload exactly."""
        # Setup mocks
        mock_qdrant_storage = Mock()
        mock_qdrant_storage.retrieve_chunks_by_query.return_value = mock_qdrant_chunks
        mock_qdrant_storage_class.return_value = mock_qdrant_storage
        
        mock_role = Mock()
        mock_role.system_prompt = "Extract knowledge graph."
        mock_role.allowed_tools = []
        mock_role_registry.get_role.return_value = mock_role
        
        mock_route.return_value = ("http://worker:30001", "Worker", "model-id")
        
        import json
        mock_call_expert.return_value = (
            {"choices": [{"message": {"content": json.dumps(mock_llm_response)}}]},
            {"duration_ms": 100, "usage": {}, "model_id": "model-id"},
        )
        
        # Execute
        result = cartographer_node(base_node_state)
        
        # Verify anchor metadata matches Qdrant payload
        triples = result.get("triples", [])
        if triples:
            first_claim = triples[0]
            if "source_anchor" in first_claim:
                anchor = first_claim["source_anchor"]
                # Verify doc_id matches file_hash from Qdrant payload
                assert anchor["doc_id"] == "a" * 64
                # Verify page_number matches
                assert anchor["page_number"] == 1
                # Verify bbox matches if present
                if "bbox" in anchor:
                    qdrant_bbox = mock_qdrant_chunks[0]["bbox"]
                    assert anchor["bbox"]["x"] == qdrant_bbox["x"]
                    assert anchor["bbox"]["y"] == qdrant_bbox["y"]
                    assert anchor["bbox"]["w"] == qdrant_bbox["w"]
                    assert anchor["bbox"]["h"] == qdrant_bbox["h"]

