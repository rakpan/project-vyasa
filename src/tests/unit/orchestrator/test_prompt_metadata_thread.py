"""
Unit tests for prompt metadata tracking in job runs.

Ensures:
- When Opik disabled -> resolved_source is "default"
- prompt_hash is stable (same template = same hash)
- prompt_manifest includes all nodes used in run
"""

import pytest
import hashlib
from unittest.mock import MagicMock, patch, Mock
from typing import Dict, Any

from src.orchestrator.prompts.registry import get_active_prompt_with_meta
from src.orchestrator.prompts.models import PromptUse
from src.orchestrator.prompts.defaults import (
    DEFAULT_CARTOGRAPHER_PROMPT,
    DEFAULT_CRITIC_PROMPT,
    DEFAULT_SYNTHESIZER_PROMPT,
)
from src.orchestrator.nodes.nodes import (
    cartographer_node,
    critic_node,
    synthesizer_node,
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
        "prompt_manifest": {},
    }


@pytest.fixture
def mock_opik_disabled():
    """Mock Opik disabled configuration."""
    with patch("src.orchestrator.prompts.registry.PROMPT_REGISTRY_ENABLED", False), \
         patch("src.orchestrator.prompts.registry.OPIK_ENABLED", False):
        yield


class TestPromptMetadataResolvedSource:
    """Tests for resolved_source metadata."""

    def test_resolved_source_default_when_opik_disabled(
        self,
        mock_opik_disabled,
    ):
        """Asserts resolved_source is 'default' when Opik is disabled."""
        template, metadata = get_active_prompt_with_meta(
            "test-prompt",
            "Default prompt text",
        )
        
        assert metadata.resolved_source == "default"
        assert template == "Default prompt text"

    @patch("src.orchestrator.prompts.registry.PROMPT_REGISTRY_ENABLED", True)
    @patch("src.orchestrator.prompts.registry.OPIK_ENABLED", True)
    @patch("src.orchestrator.prompts.registry.OPIK_BASE_URL", "http://opik:8000")
    def test_resolved_source_opik_when_fetched(
        self,
    ):
        """Asserts resolved_source is 'opik' when successfully fetched from Opik."""
        opik_template = "Opik prompt template"
        
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"template": opik_template}
            mock_requests.get.return_value = mock_response
            
            template, metadata = get_active_prompt_with_meta(
                "test-prompt",
                "Default prompt text",
            )
            
            assert metadata.resolved_source == "opik"
            assert template == opik_template

    @patch("src.orchestrator.prompts.registry.PROMPT_REGISTRY_ENABLED", True)
    @patch("src.orchestrator.prompts.registry.OPIK_ENABLED", True)
    @patch("src.orchestrator.prompts.registry.OPIK_BASE_URL", "http://opik:8000")
    def test_resolved_source_default_on_opik_error(
        self,
    ):
        """Asserts resolved_source is 'default' when Opik fetch fails."""
        with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
            mock_requests.get.side_effect = Exception("Connection failed")
            
            template, metadata = get_active_prompt_with_meta(
                "test-prompt",
                "Default prompt text",
            )
            
            assert metadata.resolved_source == "default"
            assert template == "Default prompt text"


class TestPromptHashStability:
    """Tests for prompt_hash stability."""

    def test_prompt_hash_stable_for_same_template(
        self,
        mock_opik_disabled,
    ):
        """Asserts prompt_hash is stable (same template = same hash)."""
        template = "Test prompt template"
        
        _, metadata1 = get_active_prompt_with_meta("test-prompt-1", template)
        _, metadata2 = get_active_prompt_with_meta("test-prompt-2", template)
        
        # Same template should produce same hash
        assert metadata1.prompt_hash == metadata2.prompt_hash
        
        # Verify hash is SHA256
        assert len(metadata1.prompt_hash) == 64  # SHA256 hex length
        assert all(c in "0123456789abcdef" for c in metadata1.prompt_hash)

    def test_prompt_hash_different_for_different_templates(
        self,
        mock_opik_disabled,
    ):
        """Asserts prompt_hash differs for different templates."""
        template1 = "Test prompt template 1"
        template2 = "Test prompt template 2"
        
        _, metadata1 = get_active_prompt_with_meta("test-prompt", template1)
        _, metadata2 = get_active_prompt_with_meta("test-prompt", template2)
        
        # Different templates should produce different hashes
        assert metadata1.prompt_hash != metadata2.prompt_hash

    def test_prompt_hash_matches_manual_computation(
        self,
        mock_opik_disabled,
    ):
        """Asserts prompt_hash matches manual SHA256 computation."""
        template = "Test prompt template"
        
        _, metadata = get_active_prompt_with_meta("test-prompt", template)
        
        # Manually compute hash
        expected_hash = hashlib.sha256(template.encode("utf-8")).hexdigest()
        
        assert metadata.prompt_hash == expected_hash


class TestPromptManifestInNodes:
    """Tests for prompt_manifest recording in nodes."""

    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes._query_established_knowledge")
    @patch("src.orchestrator.nodes.nodes.route_to_expert")
    def test_cartographer_records_prompt_manifest(
        self,
        mock_route,
        mock_query_knowledge,
        mock_call_expert,
        base_node_state,
    ):
        """Asserts Cartographer records prompt usage in manifest."""
        import json
        
        mock_route.return_value = ("http://worker:8000", "Worker", "model-id")
        mock_query_knowledge.return_value = ([], {}, [])
        mock_call_expert.return_value = (
            json.dumps({"triples": []}),
            {"model_id": "model-id", "expert_name": "Worker"},
        )
        
        result = cartographer_node(base_node_state)
        
        # Verify prompt_manifest was recorded
        assert "prompt_manifest" in result
        assert "cartographer" in result["prompt_manifest"]
        
        cartographer_meta = result["prompt_manifest"]["cartographer"]
        assert cartographer_meta["prompt_name"] == "vyasa-cartographer"
        assert cartographer_meta["resolved_source"] in ("opik", "default")
        assert "prompt_hash" in cartographer_meta
        assert "retrieved_at" in cartographer_meta

    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes.load_claims_for_conflict_detection")
    def test_critic_records_prompt_manifest(
        self,
        mock_load_claims,
        mock_call_expert,
        base_node_state,
    ):
        """Asserts Critic records prompt usage in manifest."""
        base_node_state["extracted_json"] = {"triples": []}
        mock_load_claims.return_value = []
        mock_call_expert.return_value = (
            '{"status": "pass", "score": 0.9, "critiques": []}',
            {"model_id": "model-id"},
        )
        
        result = critic_node(base_node_state)
        
        # Verify prompt_manifest was recorded
        assert "prompt_manifest" in result
        assert "critic" in result["prompt_manifest"]
        
        critic_meta = result["prompt_manifest"]["critic"]
        assert critic_meta["prompt_name"] == "vyasa-critic"
        assert critic_meta["resolved_source"] in ("opik", "default")
        assert "prompt_hash" in critic_meta

    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    def test_synthesizer_records_prompt_manifest(
        self,
        mock_call_expert,
        base_node_state,
    ):
        """Asserts Synthesizer records prompt usage in manifest."""
        base_node_state["extracted_json"] = {"triples": []}
        mock_call_expert.return_value = (
            '{"synthesis": "Test", "blocks": [{"text": "Block", "claim_ids": ["c1"]}]}',
            {"model_id": "model-id"},
        )
        
        result = synthesizer_node(base_node_state)
        
        # Verify prompt_manifest was recorded
        assert "prompt_manifest" in result
        assert "synthesizer" in result["prompt_manifest"]
        
        synthesizer_meta = result["prompt_manifest"]["synthesizer"]
        assert synthesizer_meta["prompt_name"] == "vyasa-synthesizer"
        assert synthesizer_meta["resolved_source"] in ("opik", "default")
        assert "prompt_hash" in synthesizer_meta


class TestPromptManifestComplete:
    """Tests for complete prompt_manifest across workflow."""

    def test_prompt_manifest_includes_all_nodes(
        self,
        base_node_state,
    ):
        """Asserts prompt_manifest includes entries for all nodes that use prompts."""
        # This test verifies that when a full workflow runs, all nodes record their prompts
        # We'll simulate by checking that each node records its prompt
        
        with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call, \
             patch("src.orchestrator.nodes.nodes._query_established_knowledge", return_value=([], {}, [])), \
             patch("src.orchestrator.nodes.nodes.route_to_expert", return_value=("http://worker:8000", "Worker", "model-id")), \
             patch("src.orchestrator.nodes.nodes.load_claims_for_conflict_detection", return_value=[]):
            import json
            
            mock_call.return_value = (
                json.dumps({"triples": []}),
                {"model_id": "model-id"},
            )
            
            # Run cartographer
            state = cartographer_node(base_node_state)
            assert "cartographer" in state.get("prompt_manifest", {})
            
            # Run critic
            state["extracted_json"] = {"triples": []}
            state = critic_node(state)
            assert "critic" in state.get("prompt_manifest", {})
            
            # Run synthesizer
            state = synthesizer_node(state)
            assert "synthesizer" in state.get("prompt_manifest", {})
            
            # Verify all three are present
            manifest = state.get("prompt_manifest", {})
            assert len(manifest) == 3
            assert "cartographer" in manifest
            assert "critic" in manifest
            assert "synthesizer" in manifest

    def test_prompt_manifest_preserves_previous_entries(
        self,
        base_node_state,
    ):
        """Asserts prompt_manifest preserves previous node entries."""
        # Set up initial manifest with cartographer
        base_node_state["prompt_manifest"] = {
            "cartographer": {
                "prompt_name": "vyasa-cartographer",
                "resolved_source": "default",
                "prompt_hash": "abc123",
            }
        }
        
        with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call, \
             patch("src.orchestrator.nodes.nodes.load_claims_for_conflict_detection", return_value=[]):
            mock_call.return_value = (
                '{"status": "pass", "score": 0.9, "critiques": []}',
                {"model_id": "model-id"},
            )
            
            base_node_state["extracted_json"] = {"triples": []}
            result = critic_node(base_node_state)
            
            # Verify both entries are present
            manifest = result.get("prompt_manifest", {})
            assert "cartographer" in manifest
            assert "critic" in manifest
            assert len(manifest) == 2


class TestPromptManifestMetadataFields:
    """Tests for completeness of prompt_manifest metadata fields."""

    def test_prompt_manifest_includes_all_required_fields(
        self,
        mock_opik_disabled,
    ):
        """Asserts prompt_manifest includes all required PromptUse fields."""
        template, metadata = get_active_prompt_with_meta(
            "test-prompt",
            "Default prompt text",
        )
        
        meta_dict = metadata.model_dump(mode="python")
        
        # Verify all required fields are present
        assert "prompt_name" in meta_dict
        assert "tag" in meta_dict
        assert "resolved_source" in meta_dict
        assert "retrieved_at" in meta_dict
        assert "prompt_hash" in meta_dict
        
        # Verify field types
        assert isinstance(meta_dict["prompt_name"], str)
        assert isinstance(meta_dict["tag"], str)
        assert meta_dict["resolved_source"] in ("opik", "default")
        assert isinstance(meta_dict["retrieved_at"], str)
        assert isinstance(meta_dict["prompt_hash"], str)

    def test_prompt_manifest_cache_hit_field(
        self,
    ):
        """Asserts cache_hit field is set when prompt is cached."""
        with patch("src.orchestrator.prompts.registry.PROMPT_REGISTRY_ENABLED", True), \
             patch("src.orchestrator.prompts.registry.OPIK_ENABLED", True), \
             patch("src.orchestrator.prompts.registry.OPIK_BASE_URL", "http://opik:8000"), \
             patch("src.orchestrator.prompts.registry.time.time", return_value=1000.0):
            import requests
            
            opik_template = "Opik prompt template"
            
            with patch("src.orchestrator.prompts.registry.requests") as mock_requests:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"template": opik_template}
                mock_requests.get.return_value = mock_response
                
                # First fetch (not cached)
                _, metadata1 = get_active_prompt_with_meta("test-prompt", "Default")
                assert metadata1.cache_hit is False
                
                # Second fetch (cached)
                with patch("src.orchestrator.prompts.registry.time.time", return_value=1000.0 + 10):  # Within TTL
                    _, metadata2 = get_active_prompt_with_meta("test-prompt", "Default")
                    assert metadata2.cache_hit is True

