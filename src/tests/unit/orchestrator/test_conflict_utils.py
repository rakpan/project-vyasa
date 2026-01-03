"""
Tests for conflict_utils module.
Tests deterministic explanation generation and conflict payload extraction.

Verifies:
1. Explanations use enum-based conflict types
2. Explanations use template-based formatting (no LLM variance)
3. Same inputs produce identical outputs
"""

import pytest
from src.orchestrator.conflict_utils import (
    generate_conflict_explanation,
    extract_conflict_payload,
    DeterministicConflictType,
    _map_conflict_type_to_deterministic,
)
from src.shared.schema import ConflictItem, ConflictType, ConflictSeverity, ConflictProducer, SourcePointer


def test_generate_conflict_explanation_with_pages():
    """Test explanation generation with page numbers."""
    source_a = {"doc_hash": "abc123def456", "page": 5, "snippet": "Some text"}
    source_b = {"doc_hash": "xyz789ghi012", "page": 12, "snippet": "Other text"}
    claim_text = "Subject predicate Object"
    
    explanation = generate_conflict_explanation(claim_text, source_a, source_b)
    
    assert "Subject predicate Object" in explanation
    assert "page 5" in explanation
    assert "page 12" in explanation
    assert "Source A" in explanation
    assert "Source B" in explanation
    assert explanation.endswith(".")


def test_generate_conflict_explanation_without_pages():
    """Test explanation generation without page numbers (uses 'unknown')."""
    source_a = {"doc_hash": "abc123def456"}
    source_b = {"doc_hash": "xyz789ghi012"}
    claim_text = "X relates Y"
    
    explanation = generate_conflict_explanation(claim_text, source_a, source_b)
    
    # Should use template with 'unknown' for missing pages
    assert "X relates Y" in explanation or "X relates..." in explanation
    assert "page unknown" in explanation
    assert "Source A" in explanation
    assert "Source B" in explanation
    assert explanation.endswith(".")


def test_generate_conflict_explanation_with_conflict_type():
    """Test explanation generation with conflict type enum."""
    source_a = {"doc_hash": "abc123", "page": 1}
    source_b = {"doc_hash": "xyz789", "page": 2}
    claim_text = "Test claim"
    
    explanation = generate_conflict_explanation(
        claim_text, source_a, source_b, conflict_type=ConflictType.STRUCTURAL_CONFLICT
    )
    
    # Should use template format (not LLM-generated)
    assert "page 1" in explanation or "page unknown" in explanation
    assert "page 2" in explanation or "page unknown" in explanation
    assert "Test claim" in explanation or "Test claim..." in explanation
    assert explanation.endswith(".")


def test_extract_conflict_payload_no_flags():
    """Test that extract_conflict_payload returns None for non-flagged claims."""
    triple = {
        "subject": "A",
        "predicate": "relates",
        "object": "B",
        "source_pointer": {"doc_hash": "abc123", "page": 1},
    }
    
    payload = extract_conflict_payload(triple)
    
    assert payload is None


def test_extract_conflict_payload_with_flags():
    """Test conflict payload extraction for flagged claims."""
    triple = {
        "subject": "A",
        "predicate": "relates",
        "object": "B",
        "conflict_flags": ["Conflict detected"],
        "source_pointer": {
            "doc_hash": "abc123def456",
            "page": 5,
            "snippet": "Source A text",
        },
    }
    
    payload = extract_conflict_payload(triple)
    
    assert payload is not None
    assert "source_a" in payload
    assert "source_b" in payload
    assert "explanation" in payload
    assert payload["source_a"]["doc_id"] == "abc123def456"
    assert payload["source_a"]["page"] == 5
    assert payload["source_a"]["excerpt"] == "Source A text"
    assert "A relates B" in payload["explanation"]


def test_extract_conflict_payload_with_conflict_item():
    """Test conflict payload extraction with ConflictItem."""
    triple = {
        "subject": "X",
        "predicate": "contradicts",
        "object": "Y",
        "conflict_flags": ["Flag"],
        "source_pointer": {
            "doc_hash": "source_a_hash",
            "page": 1,
            "snippet": "Source A excerpt",
        },
    }
    
    conflict_item = {
        "conflict_id": "conflict-1",
        "conflict_type": "STRUCTURAL_CONFLICT",
        "evidence_anchors": [
            {
                "doc_hash": "source_a_hash",
                "page": 1,
                "snippet": "Source A excerpt",
            },
            {
                "doc_hash": "source_b_hash",
                "page": 2,
                "snippet": "Source B excerpt",
            },
        ],
    }
    
    payload = extract_conflict_payload(triple, conflict_item=conflict_item)
    
    assert payload is not None
    assert payload["source_a"]["doc_id"] == "source_a_hash"
    assert payload["source_b"]["doc_id"] == "source_b_hash"
    assert payload["source_b"]["page"] == 2
    assert payload["source_b"]["excerpt"] == "Source B excerpt"
    assert "Source A" in payload["explanation"]
    assert "Source B" in payload["explanation"]


def test_extract_conflict_payload_finds_contradicting_claim():
    """Test that extract_conflict_payload can find contradicting claims from all_triples."""
    triple_a = {
        "subject": "X",
        "predicate": "enables",
        "object": "Y",
        "conflict_flags": ["Flag"],
        "source_pointer": {
            "doc_hash": "doc_a",
            "page": 1,
        },
    }
    
    triple_b = {
        "subject": "X",
        "predicate": "prevents",
        "object": "Y",
        "source_pointer": {
            "doc_hash": "doc_b",
            "page": 2,
            "snippet": "Contradicting text",
        },
    }
    
    all_triples = [triple_a, triple_b]
    
    payload = extract_conflict_payload(triple_a, all_triples=all_triples)
    
    assert payload is not None
    assert payload["source_b"]["doc_id"] == "doc_b"
    assert payload["source_b"]["page"] == 2


def test_deterministic_explanation_same_inputs():
    """Test that explanations are deterministic (same inputs produce same output)."""
    source_a = {"doc_hash": "abc123", "page": 5}
    source_b = {"doc_hash": "xyz789", "page": 12}
    claim_text = "Test claim"
    
    explanation1 = generate_conflict_explanation(claim_text, source_a, source_b)
    explanation2 = generate_conflict_explanation(claim_text, source_a, source_b)
    
    assert explanation1 == explanation2


def test_conflict_type_mapping():
    """Test that ConflictType enum values map to deterministic types."""
    # Test mapping of ConflictType enum values
    assert _map_conflict_type_to_deterministic(ConflictType.STRUCTURAL_CONFLICT) == DeterministicConflictType.CONTRADICTION
    assert _map_conflict_type_to_deterministic(ConflictType.EVIDENCE_BINDING_FAILURE) == DeterministicConflictType.MISSING_EVIDENCE
    assert _map_conflict_type_to_deterministic(ConflictType.SCOPE_MISMATCH) == DeterministicConflictType.AMBIGUOUS
    assert _map_conflict_type_to_deterministic(None) == DeterministicConflictType.CONTRADICTION


def test_explanation_uses_templates():
    """Test that explanations use template-based formatting."""
    source_a = {"doc_hash": "abc123", "page": 5}
    source_b = {"doc_hash": "xyz789", "page": 12}
    claim_text = "Subject predicate Object"
    
    # Test with different conflict types
    explanation_contradiction = generate_conflict_explanation(
        claim_text, source_a, source_b, ConflictType.STRUCTURAL_CONFLICT
    )
    explanation_missing = generate_conflict_explanation(
        claim_text, source_a, source_b, ConflictType.EVIDENCE_BINDING_FAILURE
    )
    explanation_ambiguous = generate_conflict_explanation(
        claim_text, source_a, source_b, ConflictType.SCOPE_MISMATCH
    )
    
    # All should be different (different templates)
    assert explanation_contradiction != explanation_missing
    assert explanation_contradiction != explanation_ambiguous
    assert explanation_missing != explanation_ambiguous
    
    # All should contain claim text and page numbers
    assert "Subject predicate Object" in explanation_contradiction or "Subject predicate..." in explanation_contradiction
    assert "5" in explanation_contradiction
    assert "12" in explanation_contradiction


def test_explanation_template_format():
    """Test that explanations follow template format (no LLM-generated strings)."""
    source_a = {"doc_hash": "abc123", "page": 5}
    source_b = {"doc_hash": "xyz789", "page": 12}
    claim_text = "Test claim text"
    
    explanation = generate_conflict_explanation(claim_text, source_a, source_b)
    
    # Should contain template markers (page numbers, claim text)
    assert "page 5" in explanation or "page unknown" in explanation
    assert "page 12" in explanation or "page unknown" in explanation
    assert "Test claim text" in explanation or "Test claim..." in explanation
    
    # Should end with period (template format)
    assert explanation.endswith(".")


def test_explanation_without_pages():
    """Test that explanations work when page numbers are missing."""
    source_a = {"doc_hash": "abc123"}
    source_b = {"doc_hash": "xyz789"}
    claim_text = "Test claim"
    
    explanation = generate_conflict_explanation(claim_text, source_a, source_b)
    
    # Should still generate explanation (uses "unknown" for missing pages)
    assert len(explanation) > 0
    assert explanation.endswith(".")


