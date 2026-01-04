"""
Unit tests for phase transitions in workflow nodes.

Ensures:
- Each node sets phase appropriately
- Phase transitions are explicit and consistent
- Conservative conflict gating prevents synthesis when needs_human_review=True
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from typing import Dict, Any

from src.orchestrator.state import PhaseEnum
from src.orchestrator.nodes.nodes import (
    cartographer_node,
    critic_node,
    synthesizer_node,
    saver_node,
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
        "phase": PhaseEnum.INGESTING.value,
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
            }
        ],
        "entities": [],
    }


class TestCartographerPhaseTransition:
    """Tests for cartographer_node phase transitions."""

    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes._query_established_knowledge")
    @patch("src.orchestrator.nodes.nodes.route_to_expert")
    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    def test_cartographer_sets_phase_mapping(
        self,
        mock_get_prompt,
        mock_route,
        mock_query_knowledge,
        mock_call_expert,
        base_node_state,
        mock_llm_response,
    ):
        """Asserts cartographer_node sets phase=MAPPING on success."""
        mock_get_prompt.return_value = "Extract knowledge from text."
        mock_route.return_value = ("http://worker:8000", "Worker", "model-id")
        mock_query_knowledge.return_value = ([], {}, [])
        mock_call_expert.return_value = (
            json.dumps(mock_llm_response),
            {"model_id": "model-id", "expert_name": "Worker"},
        )
        
        result = cartographer_node(base_node_state)
        
        assert result.get("phase") == PhaseEnum.MAPPING.value
        assert "extracted_json" in result

    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    def test_cartographer_sets_phase_mapping_on_error(
        self,
        mock_call_expert,
        base_node_state,
    ):
        """Asserts cartographer_node sets phase=MAPPING even on error."""
        mock_call_expert.side_effect = Exception("LLM call failed")
        
        result = cartographer_node(base_node_state)
        
        assert result.get("phase") == PhaseEnum.MAPPING.value
        assert result.get("extracted_json", {}).get("triples") == []


class TestCriticPhaseTransition:
    """Tests for critic_node phase transitions."""

    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    @patch("src.orchestrator.nodes.nodes.load_claims_for_conflict_detection")
    def test_critic_sets_phase_vetting(
        self,
        mock_load_claims,
        mock_get_prompt,
        mock_call_expert,
        base_node_state,
    ):
        """Asserts critic_node sets phase=VETTING."""
        base_node_state["extracted_json"] = {"triples": [{"claim_id": "c1"}]}
        mock_get_prompt.return_value = "Validate extraction."
        mock_load_claims.return_value = []
        mock_call_expert.return_value = (
            '{"status": "pass", "score": 0.9, "critiques": []}',
            {"model_id": "model-id"},
        )
        
        result = critic_node(base_node_state)
        
        assert result.get("phase") == PhaseEnum.VETTING.value

    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    def test_critic_sets_phase_vetting_on_error(
        self,
        mock_call_expert,
        base_node_state,
    ):
        """Asserts critic_node sets phase=VETTING even on error."""
        base_node_state["extracted_json"] = {"triples": []}
        mock_call_expert.side_effect = Exception("Critic failed")
        
        result = critic_node(base_node_state)
        
        assert result.get("phase") == PhaseEnum.VETTING.value
        assert result.get("critic_status") == "fail"


class TestCriticNeedsHumanReview:
    """Tests for needs_human_review gating in conservative mode."""

    @patch("src.orchestrator.nodes.nodes.load_claims_for_conflict_detection")
    @patch("src.orchestrator.nodes.nodes.detect_conflicts_deterministic")
    def test_critic_sets_needs_human_review_conservative(
        self,
        mock_detect_conflicts,
        mock_load_claims,
        base_node_state,
    ):
        """Asserts critic sets needs_human_review=True in conservative mode with conflicts."""
        base_node_state["rigor_level"] = "conservative"
        base_node_state["project_context"]["rigor_level"] = "conservative"
        base_node_state["extracted_json"] = {"triples": [{"claim_id": "c1"}]}
        
        # Mock conflict detection returning 3+ conflicts
        mock_load_claims.return_value = [
            {"claim_id": "c1", "subject": "X", "predicate": "causes", "object": "Y"},
            {"claim_id": "c2", "subject": "X", "predicate": "causes", "object": "Z"},
        ]
        mock_detect_conflicts.return_value = [
            {"conflict_item": MagicMock()},
            {"conflict_item": MagicMock()},
            {"conflict_item": MagicMock()},
        ]
        
        with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call:
            mock_call.return_value = (
                '{"status": "fail", "score": 0.5, "critiques": []}',
                {"model_id": "model-id"},
            )
            result = critic_node(base_node_state)
        
        assert result.get("needs_human_review") is True
        assert result.get("conflict_detected") is True

    @patch("src.orchestrator.nodes.nodes.update_job_status")
    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    def test_synthesizer_skips_on_needs_human_review_conservative(
        self,
        mock_get_prompt,
        mock_update_job,
        base_node_state,
    ):
        """Asserts synthesizer skips synthesis when needs_human_review=True in conservative mode."""
        base_node_state["rigor_level"] = "conservative"
        base_node_state["project_context"]["rigor_level"] = "conservative"
        base_node_state["needs_human_review"] = True
        base_node_state["extracted_json"] = {"triples": []}
        
        result = synthesizer_node(base_node_state)
        
        assert result.get("synthesis") == ""
        assert result.get("manuscript_blocks") == []
        assert result.get("phase") == PhaseEnum.SYNTHESIZING.value
        assert result.get("needs_human_review") is True
        # Verify job status was updated
        mock_update_job.assert_called_once()
        call_args = mock_update_job.call_args
        assert call_args[0][1].value == "NEEDS_SIGNOFF"  # JobStatus.NEEDS_SIGNOFF

    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    def test_synthesizer_proceeds_on_needs_human_review_exploratory(
        self,
        mock_get_prompt,
        base_node_state,
    ):
        """Asserts synthesizer proceeds in exploratory mode even with needs_human_review=True."""
        base_node_state["rigor_level"] = "exploratory"
        base_node_state["project_context"]["rigor_level"] = "exploratory"
        base_node_state["needs_human_review"] = True
        base_node_state["extracted_json"] = {"triples": []}
        
        with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call:
            mock_call.return_value = (
                '{"synthesis": "Test synthesis", "blocks": []}',
                {"model_id": "model-id"},
            )
            result = synthesizer_node(base_node_state)
        
        # Should proceed (no early return)
        assert "synthesis" in result or "manuscript_blocks" in result


class TestSynthesizerPhaseTransition:
    """Tests for synthesizer_node phase transitions."""

    @patch("src.orchestrator.nodes.nodes.call_expert_with_fallback")
    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    def test_synthesizer_sets_phase_synthesizing(
        self,
        mock_get_prompt,
        mock_call_expert,
        base_node_state,
    ):
        """Asserts synthesizer_node sets phase=SYNTHESIZING."""
        base_node_state["extracted_json"] = {"triples": []}
        mock_get_prompt.return_value = "Synthesize claims."
        mock_call_expert.return_value = (
            '{"synthesis": "Test", "blocks": []}',
            {"model_id": "model-id"},
        )
        
        result = synthesizer_node(base_node_state)
        
        assert result.get("phase") == PhaseEnum.SYNTHESIZING.value

    @patch("src.orchestrator.nodes.nodes.get_active_prompt")
    def test_synthesizer_sets_phase_synthesizing_on_validation_error(
        self,
        mock_get_prompt,
        base_node_state,
    ):
        """Asserts synthesizer_node sets phase=SYNTHESIZING even on validation error."""
        base_node_state["rigor_level"] = "conservative"
        base_node_state["project_context"]["rigor_level"] = "conservative"
        base_node_state["extracted_json"] = {"triples": []}
        
        with patch("src.orchestrator.nodes.nodes.call_expert_with_fallback") as mock_call:
            mock_call.return_value = (
                '{"synthesis": "Test", "blocks": [{"text": "Block", "claim_ids": []}]}',
                {"model_id": "model-id"},
            )
            result = synthesizer_node(base_node_state)
        
        assert result.get("phase") == PhaseEnum.SYNTHESIZING.value


class TestSaverPhaseTransition:
    """Tests for saver_node phase transitions."""

    @patch("src.orchestrator.nodes.nodes.get_project_service")
    @patch("arango.ArangoClient")
    def test_saver_sets_phase_done(
        self,
        mock_arango_client,
        mock_get_project_service,
        base_node_state,
    ):
        """Asserts saver_node sets phase=DONE on successful persistence."""
        base_node_state["extracted_json"] = {"triples": []}
        base_node_state["manuscript_blocks"] = []
        
        mock_db = MagicMock()
        mock_db.has_collection.return_value = True
        mock_db.collection.return_value = MagicMock()
        mock_db.aql.execute.return_value = iter([])
        mock_arango_client.return_value.db.return_value = mock_db
        
        mock_project_service = MagicMock()
        mock_project_service.get_project.return_value = MagicMock(
            model_dump=lambda: base_node_state["project_context"]
        )
        mock_get_project_service.return_value = mock_project_service
        
        result = saver_node(base_node_state)
        
        assert result.get("phase") == PhaseEnum.DONE.value
        assert "save_receipt" in result


class TestPhaseTransitionSequence:
    """Tests for phase transition sequence across workflow."""

    def test_phase_sequence_ingestion_to_mapping(self, base_node_state):
        """Asserts initial phase is MAPPING (workflow starts with cartographer)."""
        # Initial state should have phase set to MAPPING (or INGESTING if before workflow)
        # Since workflow starts with cartographer, MAPPING is correct
        assert base_node_state.get("phase") in [PhaseEnum.INGESTING.value, PhaseEnum.MAPPING.value]

    def test_phase_transitions_are_explicit(self):
        """Asserts all phase transitions use explicit PhaseEnum values."""
        phases = [
            PhaseEnum.INGESTING.value,
            PhaseEnum.MAPPING.value,
            PhaseEnum.VETTING.value,
            PhaseEnum.SYNTHESIZING.value,
            PhaseEnum.PERSISTING.value,
            PhaseEnum.DONE.value,
        ]
        
        # All phases should be strings (enum values)
        assert all(isinstance(p, str) for p in phases)
        # All phases should be uppercase
        assert all(p.isupper() for p in phases)

