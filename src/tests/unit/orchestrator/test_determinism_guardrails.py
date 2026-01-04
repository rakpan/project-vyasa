"""
Determinism Guardrails Test Suite.

Prevents regression where deterministic fields accidentally become LLM-generated
via prompt changes or code modifications.

Tests ensure:
1. conflict.explanation is always produced by conflict_utils templates (never from LLM)
2. precision formatting never calls LLM
3. tone linter detection is deterministic (regex-based) and rewrite touches only flagged sentences
4. citation integrity validation remains deterministic

All tests use mocks/stubs and static fixtures to ensure CI fails if determinism boundaries are violated.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from src.orchestrator.conflict_utils import (
    generate_conflict_explanation,
    extract_conflict_payload,
    DeterministicConflictType,
)
from src.orchestrator.validators.citation_integrity import (
    validate_citation_integrity,
    validate_manuscript_blocks,
    extract_claim_ids_from_text,
)
from src.orchestrator.guards.precision_guard import check_table_precision, infer_decimal_places
from src.orchestrator.guards.precision_contract import validate_table_precision
from src.orchestrator.tone_guard import lint_tone, tone_linter_node
from src.orchestrator.guards.tone_guard import scan_text


class TestConflictExplanationDeterminism:
    """Tests that conflict explanations are always template-based, never LLM-generated."""
    
    def test_generate_conflict_explanation_uses_templates_only(self):
        """Verify that generate_conflict_explanation uses templates, not LLM."""
        source_a = {"doc_hash": "abc123", "page": 5, "snippet": "Source A text"}
        source_b = {"doc_hash": "def456", "page": 10, "snippet": "Source B text"}
        
        # Mock LLM client to ensure it's never called (patch where chat is actually imported)
        with patch("src.shared.llm_client.chat") as mock_chat, \
             patch("requests.post") as mock_requests_post:
            
            explanation = generate_conflict_explanation(
                claim_text="Subject predicate Object",
                source_a=source_a,
                source_b=source_b,
                conflict_type=DeterministicConflictType.CONTRADICTION,
                claim_a_text="Claim A",
                claim_b_text="Claim B",
            )
            
            # Verify LLM was never called
            mock_chat.assert_not_called()
            mock_requests_post.assert_not_called()
            
            # Verify explanation matches template format
            assert "Source A (page 5)" in explanation
            assert "Source B (page 10)" in explanation
            assert "contradict" in explanation.lower()
            # Should not contain LLM-like phrases
            assert "I believe" not in explanation.lower()
            assert "in my opinion" not in explanation.lower()
    
    def test_generate_conflict_explanation_deterministic_for_same_input(self):
        """Verify that same input always produces same explanation."""
        source_a = {"doc_hash": "abc123", "page": 5}
        source_b = {"doc_hash": "def456", "page": 10}
        
        explanation1 = generate_conflict_explanation(
            claim_text="Test claim",
            source_a=source_a,
            source_b=source_b,
            conflict_type=DeterministicConflictType.CONTRADICTION,
        )
        
        explanation2 = generate_conflict_explanation(
            claim_text="Test claim",
            source_a=source_a,
            source_b=source_b,
            conflict_type=DeterministicConflictType.CONTRADICTION,
        )
        
        assert explanation1 == explanation2
    
    def test_extract_conflict_payload_uses_templates(self):
        """Verify that extract_conflict_payload uses template-based explanations."""
        triple = {
            "subject": "Subject",
            "predicate": "predicate",
            "object": "Object",
            "source_pointer": {"doc_hash": "abc123", "page": 5, "snippet": "Snippet"},
            "conflict_flags": ["CONTRADICTION"],
        }
        
        with patch("src.shared.llm_client.chat") as mock_chat:
            payload = extract_conflict_payload(triple)
            
            # Verify LLM was never called
            mock_chat.assert_not_called()
            
            # Verify explanation exists and is template-based
            assert payload is not None
            assert "explanation" in payload
            explanation = payload["explanation"]
            assert "page" in explanation.lower() or "unknown" in explanation.lower()
            # Should not contain LLM-like phrases
            assert "I think" not in explanation.lower()
            assert "it seems" not in explanation.lower()
    
    def test_conflict_explanation_matches_template_patterns(self):
        """Verify that explanations match known template patterns."""
        source_a = {"page": 1}
        source_b = {"page": 2}
        
        # Test CONTRADICTION template
        explanation = generate_conflict_explanation(
            claim_text="Test",
            source_a=source_a,
            source_b=source_b,
            conflict_type=DeterministicConflictType.CONTRADICTION,
            claim_a_text="Claim A",
            claim_b_text="Claim B",
        )
        assert "Source A" in explanation
        assert "Source B" in explanation
        assert "contradict" in explanation.lower()
        
        # Test MISSING_EVIDENCE template
        explanation_missing = generate_conflict_explanation(
            claim_text="Test claim",
            source_a=source_a,
            source_b=source_b,
            conflict_type=DeterministicConflictType.MISSING_EVIDENCE,
        )
        # Check for MISSING_EVIDENCE template text
        assert "lacks sufficient evidence" in explanation_missing.lower() or "does not confirm" in explanation_missing.lower()
        
        # Test AMBIGUOUS template
        explanation = generate_conflict_explanation(
            claim_text="Test claim",
            source_a=source_a,
            source_b=source_b,
            conflict_type=DeterministicConflictType.AMBIGUOUS,
        )
        assert "ambiguous" in explanation.lower()


class TestPrecisionDeterminism:
    """Tests that precision formatting never calls LLM."""
    
    def test_check_table_precision_no_llm(self):
        """Verify that check_table_precision never calls LLM."""
        table = {
            "table_id": "test_table",
            "rows": [
                {"colA": "1.234", "colB": "2.345"},
                {"colA": "1.235", "colB": "2.346"},
            ],
        }
        
        with patch("src.shared.llm_client.chat") as mock_chat:
            
            flags = check_table_precision(table, max_decimals_default=2)
            
            # Verify LLM was never called
            mock_chat.assert_not_called()
            
            # Verify deterministic output
            assert isinstance(flags, list)
            # Should flag excessive precision
            assert len(flags) > 0
    
    def test_infer_decimal_places_deterministic(self):
        """Verify that infer_decimal_places is deterministic."""
        assert infer_decimal_places("1.23") == 2
        assert infer_decimal_places("1.234") == 3
        assert infer_decimal_places("1") == 0
        assert infer_decimal_places("1.2e-3") == 1  # Scientific notation
    
    def test_validate_table_precision_no_llm(self):
        """Verify that validate_table_precision never calls LLM."""
        from src.shared.schema import PrecisionContract
        
        table = {
            "table_id": "test_table",
            "rows": [
                {"colA": "1.234567", "colB": "2.345"},
            ],
        }
        
        contract = PrecisionContract(
            max_decimals=2,
            max_sig_figs=3,
            rounding_rule="bankers",
            consistency_rule="per_column",
        )
        
        with patch("src.shared.llm_client.chat") as mock_chat:
            
            rewritten_table, flags, warnings = validate_table_precision(
                table, contract, rigor="conservative"
            )
            
            # Verify LLM was never called
            mock_chat.assert_not_called()
            
            # Verify deterministic output
            assert isinstance(flags, list)
            assert isinstance(warnings, list)
            # Should have formatted the values
            assert rewritten_table["rows"][0]["colA"] != "1.234567"
    
    def test_precision_formatting_idempotent(self):
        """Verify that precision formatting is idempotent (same input -> same output)."""
        from src.shared.schema import PrecisionContract
        
        table = {
            "table_id": "test_table",
            "rows": [
                {"colA": "1.23", "colB": "2.34"},
            ],
        }
        
        contract = PrecisionContract(
            max_decimals=2,
            max_sig_figs=3,
            rounding_rule="bankers",
            consistency_rule="per_column",
        )
        
        # First pass
        rewritten1, flags1, warnings1 = validate_table_precision(
            table, contract, rigor="exploratory"
        )
        
        # Second pass (should be idempotent)
        rewritten2, flags2, warnings2 = validate_table_precision(
            rewritten1, contract, rigor="exploratory"
        )
        
        # Values should not change on second pass
        assert rewritten1["rows"][0]["colA"] == rewritten2["rows"][0]["colA"]
        assert rewritten1["rows"][0]["colB"] == rewritten2["rows"][0]["colB"]


class TestToneLinterDeterminism:
    """Tests that tone linter detection is deterministic (regex-based)."""
    
    def test_lint_tone_regex_based(self):
        """Verify that lint_tone uses regex patterns, not LLM."""
        text = "This is an amazing breakthrough that will revolutionize everything!"
        
        with patch("src.orchestrator.tone_guard.chat") as mock_chat, \
             patch("src.shared.llm_client.chat") as mock_llm_chat:
            
            findings = lint_tone(text)
            
            # Verify LLM was never called for detection
            mock_chat.assert_not_called()
            mock_llm_chat.assert_not_called()
            
            # Verify findings are deterministic
            assert isinstance(findings, list)
            # Should detect "amazing" if it's in the forbidden list
    
    def test_lint_tone_deterministic_for_same_input(self):
        """Verify that same input always produces same findings."""
        text = "This is a test sentence with amazing results."
        
        findings1 = lint_tone(text)
        findings2 = lint_tone(text)
        
        # Findings should be identical
        assert len(findings1) == len(findings2)
        if findings1:
            assert findings1[0]["word"] == findings2[0]["word"]
            assert findings1[0]["location"] == findings2[0]["location"]
    
    def test_scan_text_regex_based(self):
        """Verify that scan_text uses regex patterns."""
        text = "This is an amazing breakthrough!"
        
        with patch("src.shared.llm_client.chat") as mock_chat:
            flags = scan_text(text)
            
            # Verify LLM was never called
            mock_chat.assert_not_called()
            
            # Verify flags are deterministic
            assert isinstance(flags, list)
    
    def test_tone_rewrite_touches_only_flagged_sentences(self):
        """Verify that tone rewrite only modifies flagged sentences."""
        # Create a state with manuscript blocks
        state = {
            "job_id": "test_job",
            "project_id": "test_project",
            "rigor_level": "conservative",
            "manuscript_blocks": [
                {
                    "block_id": "block1",
                    "text": "This is a normal sentence. This is an amazing sentence!",
                    "claim_ids": ["claim1"],
                    "citation_keys": ["cite1"],
                },
            ],
        }
        
        # Mock the LLM rewrite to return a specific response
        def mock_chat(*args, **kwargs):
            # Extract the sentence being rewritten
            messages = kwargs.get("messages", [])
            user_content = messages[-1]["content"] if messages else ""
            if "amazing" in user_content.lower():
                return {
                    "choices": [{"message": {"content": "This is a significant sentence!"}}]
                }, {}
            return {"choices": [{"message": {"content": ""}}]}, {}
        
        with patch("src.orchestrator.tone_guard.chat", side_effect=mock_chat):
            result = tone_linter_node(state)
            
            # Verify that only the flagged sentence was rewritten
            updated_blocks = result.get("manuscript_blocks", [])
            assert len(updated_blocks) == 1
            updated_text = updated_blocks[0]["text"]
            
            # Normal sentence should remain unchanged
            assert "This is a normal sentence." in updated_text
            # Flagged sentence should be rewritten (or removed if rewrite fails)
            # The exact behavior depends on the rewrite, but we verify it's not a full LLM rewrite
    
    def test_tone_rewrite_preserves_claim_ids(self):
        """Verify that tone rewrite preserves claim_ids and citation_keys."""
        state = {
            "job_id": "test_job",
            "project_id": "test_project",
            "rigor_level": "conservative",
            "manuscript_blocks": [
                {
                    "block_id": "block1",
                    "text": "This is an amazing result!",
                    "claim_ids": ["claim1", "claim2"],
                    "citation_keys": ["cite1"],
                },
            ],
        }
        
        # Mock rewrite to return rewritten text
        def mock_chat(*args, **kwargs):
            return {
                "choices": [{"message": {"content": "This is a significant result!"}}]
            }, {}
        
        with patch("src.orchestrator.tone_guard.chat", side_effect=mock_chat):
            result = tone_linter_node(state)
            
            updated_blocks = result.get("manuscript_blocks", [])
            assert len(updated_blocks) == 1
            updated_block = updated_blocks[0]
            
            # Verify claim_ids and citation_keys are preserved
            assert updated_block["claim_ids"] == ["claim1", "claim2"]
            assert updated_block["citation_keys"] == ["cite1"]


class TestCitationIntegrityDeterminism:
    """Tests that citation integrity validation remains deterministic."""
    
    def test_validate_citation_integrity_no_llm(self):
        """Verify that validate_citation_integrity never calls LLM."""
        block = {
            "block_id": "block1",
            "text": "This is a claim [[claim_id_123]].",
            "claim_ids": ["claim_id_123"],
        }
        
        with patch("src.shared.llm_client.chat") as mock_chat:
            
            is_valid, error = validate_citation_integrity(
                block=block,
                available_claim_ids=["claim_id_123"],
                rigor_level="conservative",
            )
            
            # Verify LLM was never called
            mock_chat.assert_not_called()
            
            # Verify deterministic output
            assert isinstance(is_valid, bool)
            assert error is None or isinstance(error, str)
    
    def test_extract_claim_ids_from_text_regex_based(self):
        """Verify that extract_claim_ids_from_text uses regex, not LLM."""
        text = "This is a claim [[claim_id_123]] and another [[claim_id_456]]."
        
        with patch("src.shared.llm_client.chat") as mock_chat:
            claim_ids = extract_claim_ids_from_text(text)
            
            # Verify LLM was never called
            mock_chat.assert_not_called()
            
            # Verify deterministic extraction
            assert "claim_id_123" in claim_ids
            assert "claim_id_456" in claim_ids
    
    def test_validate_manuscript_blocks_deterministic(self):
        """Verify that validate_manuscript_blocks is deterministic."""
        blocks = [
            {
                "block_id": "block1",
                "text": "Claim [[claim_id_123]].",
                "claim_ids": ["claim_id_123"],
            },
            {
                "block_id": "block2",
                "text": "No claim references.",
            },
        ]
        
        with patch("src.shared.llm_client.chat") as mock_chat:
            valid_blocks, errors = validate_manuscript_blocks(
                blocks=blocks,
                available_claim_ids=["claim_id_123"],
                rigor_level="conservative",
            )
            
            # Verify LLM was never called
            mock_chat.assert_not_called()
            
            # Verify deterministic output
            assert isinstance(valid_blocks, list)
            assert isinstance(errors, list)
            # Block 1 should be valid, block 2 should fail in conservative mode
            assert len(valid_blocks) == 1
            assert len(errors) == 1
    
    def test_citation_integrity_same_input_same_output(self):
        """Verify that same input always produces same validation result."""
        block = {
            "block_id": "block1",
            "text": "Claim [[claim_id_123]].",
            "claim_ids": ["claim_id_123"],
        }
        
        result1 = validate_citation_integrity(
            block=block,
            available_claim_ids=["claim_id_123"],
            rigor_level="conservative",
        )
        
        result2 = validate_citation_integrity(
            block=block,
            available_claim_ids=["claim_id_123"],
            rigor_level="conservative",
        )
        
        assert result1 == result2


class TestDeterminismBoundaryViolations:
    """Tests that detect if determinism boundaries are accidentally violated."""
    
    def test_conflict_explanation_never_from_llm_response(self):
        """Verify that conflict explanations are never extracted from LLM response fields."""
        # This test ensures that if someone accidentally tries to use LLM for explanations,
        # the test will fail by detecting LLM calls
        
        source_a = {"page": 1}
        source_b = {"page": 2}
        
        # Create a mock that will raise if LLM is called
        def fail_if_llm_called(*args, **kwargs):
            raise AssertionError("LLM should not be called for conflict explanations!")
        
        with patch("src.shared.llm_client.chat", side_effect=fail_if_llm_called):
            
            # This should work without calling LLM
            explanation = generate_conflict_explanation(
                claim_text="Test",
                source_a=source_a,
                source_b=source_b,
                conflict_type=DeterministicConflictType.CONTRADICTION,
            )
            
            # Verify explanation is template-based
            assert explanation is not None
            assert isinstance(explanation, str)
    
    def test_precision_never_calls_llm(self):
        """Verify that precision validation never calls LLM."""
        table = {
            "table_id": "test",
            "rows": [{"colA": "1.234"}],
        }
        
        def fail_if_llm_called(*args, **kwargs):
            raise AssertionError("LLM should not be called for precision formatting!")
        
        with patch("src.shared.llm_client.chat", side_effect=fail_if_llm_called):
            
            # This should work without calling LLM
            flags = check_table_precision(table)
            assert isinstance(flags, list)
    
    def test_tone_detection_never_calls_llm(self):
        """Verify that tone detection never calls LLM (only rewrite does)."""
        text = "This is an amazing result!"
        
        def fail_if_llm_called(*args, **kwargs):
            raise AssertionError("LLM should not be called for tone detection!")
        
        with patch("src.orchestrator.tone_guard.chat", side_effect=fail_if_llm_called), \
             patch("src.shared.llm_client.chat", side_effect=fail_if_llm_called):
            
            # Detection should work without LLM
            findings = lint_tone(text)
            assert isinstance(findings, list)
    
    def test_citation_validation_never_calls_llm(self):
        """Verify that citation integrity validation never calls LLM."""
        block = {
            "block_id": "block1",
            "text": "Claim [[claim_id_123]].",
            "claim_ids": ["claim_id_123"],
        }
        
        def fail_if_llm_called(*args, **kwargs):
            raise AssertionError("LLM should not be called for citation validation!")
        
        with patch("src.shared.llm_client.chat", side_effect=fail_if_llm_called):
            
            # Validation should work without LLM
            is_valid, error = validate_citation_integrity(
                block=block,
                available_claim_ids=["claim_id_123"],
                rigor_level="conservative",
            )
            assert isinstance(is_valid, bool)

