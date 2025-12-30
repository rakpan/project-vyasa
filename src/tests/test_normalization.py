"""
Unit tests for normalization utilities (src/orchestrator/normalize.py).

Tests the normalize_extracted_json function to ensure it handles various input formats
and always returns a structure with a guaranteed "triples" array.
"""

import json
import pytest

from src.orchestrator.normalize import normalize_extracted_json


def test_normalize_none_returns_empty_triples():
    """Input None -> Returns {"triples": []}."""
    result = normalize_extracted_json(None)
    
    assert isinstance(result, dict)
    assert "triples" in result
    assert result["triples"] == []
    assert len(result) == 1  # Only triples key


def test_normalize_already_correct_structure():
    """Input {"triples": [...]} -> Returns as is."""
    input_data = {
        "triples": [
            {
                "subject": "A",
                "predicate": "relates",
                "object": "B",
                "confidence": 0.9,
            }
        ],
        "entities": [{"name": "A", "type": "Entity"}],
    }
    
    result = normalize_extracted_json(input_data)
    
    assert result == input_data
    assert len(result["triples"]) == 1
    assert result["triples"][0]["subject"] == "A"


def test_normalize_dict_with_random_junk():
    """Input {"random": "junk"} -> Returns {"triples": [], "random": "junk"}."""
    input_data = {"random": "junk", "other": 123}
    
    result = normalize_extracted_json(input_data)
    
    assert "triples" in result
    assert result["triples"] == []
    assert result["random"] == "junk"
    assert result["other"] == 123


def test_normalize_dict_with_relations_key():
    """Input {"relations": [...]} -> Maps to {"triples": [...]}."""
    input_data = {
        "relations": [
            {
                "subject": "A",
                "predicate": "relates",
                "object": "B",
            }
        ],
    }
    
    result = normalize_extracted_json(input_data)
    
    assert "triples" in result
    assert len(result["triples"]) == 1
    assert result["triples"][0]["subject"] == "A"
    assert "relations" not in result  # Should be normalized to triples


def test_normalize_dict_with_edges_key():
    """Input {"edges": [...]} -> Maps to {"triples": [...]}."""
    input_data = {
        "edges": [
            {
                "subject": "A",
                "predicate": "relates",
                "object": "B",
            }
        ],
    }
    
    result = normalize_extracted_json(input_data)
    
    assert "triples" in result
    assert len(result["triples"]) == 1
    assert result["triples"][0]["subject"] == "A"


def test_normalize_list_of_lists():
    """Input [["subject", "predicate", "object"], ...] -> Converts to triples."""
    input_data = [
        ["A", "relates", "B"],
        ["B", "causes", "C"],
    ]
    
    result = normalize_extracted_json(input_data)
    
    assert "triples" in result
    assert len(result["triples"]) == 2
    assert result["triples"][0]["subject"] == "A"
    assert result["triples"][0]["predicate"] == "relates"
    assert result["triples"][0]["object"] == "B"
    assert result["triples"][1]["subject"] == "B"


def test_normalize_list_of_lists_with_confidence():
    """Input [["subject", "predicate", "object", "evidence", confidence], ...] -> Includes confidence."""
    input_data = [
        ["A", "relates", "B", "Evidence text", 0.9],
    ]
    
    result = normalize_extracted_json(input_data)
    
    assert len(result["triples"]) == 1
    assert result["triples"][0]["subject"] == "A"
    assert result["triples"][0]["confidence"] == 0.9
    assert result["triples"][0]["evidence"] == "Evidence text"


def test_normalize_string_json():
    """Input string JSON -> Parses and normalizes."""
    input_data = '{"triples": [{"subject": "A", "predicate": "relates", "object": "B"}]}'
    
    result = normalize_extracted_json(input_data)
    
    assert "triples" in result
    assert len(result["triples"]) == 1
    assert result["triples"][0]["subject"] == "A"


def test_normalize_invalid_string_json():
    """Input invalid string JSON -> Returns empty triples."""
    input_data = '{"invalid": json}'
    
    result = normalize_extracted_json(input_data)
    
    assert "triples" in result
    assert result["triples"] == []


def test_normalize_preserves_other_keys():
    """Input with triples and other keys -> Preserves all keys."""
    input_data = {
        "triples": [{"subject": "A", "predicate": "relates", "object": "B"}],
        "entities": [{"name": "A"}],
        "claims": [{"text": "Claim 1"}],
        "metadata": {"source": "test"},
    }
    
    result = normalize_extracted_json(input_data)
    
    assert "triples" in result
    assert "entities" in result
    assert "claims" in result
    assert "metadata" in result
    assert result["metadata"]["source"] == "test"


def test_normalize_empty_dict():
    """Input {} -> Returns {"triples": []}."""
    result = normalize_extracted_json({})
    
    assert "triples" in result
    assert result["triples"] == []


def test_normalize_empty_list():
    """Input [] -> Returns {"triples": []}."""
    result = normalize_extracted_json([])
    
    assert "triples" in result
    assert result["triples"] == []


def test_normalize_list_of_objects():
    """Input list of dict objects -> Converts to triples."""
    input_data = [
        {"subject": "A", "predicate": "relates", "object": "B"},
        {"s": "C", "p": "causes", "o": "D"},  # Alternative keys
    ]
    
    result = normalize_extracted_json(input_data)
    
    assert "triples" in result
    assert len(result["triples"]) == 2
    assert result["triples"][0]["subject"] == "A"
    assert result["triples"][1]["subject"] == "C"  # Mapped from "s"


def test_normalize_unknown_type():
    """Input unknown type (e.g., int) -> Returns {"triples": []}."""
    result = normalize_extracted_json(123)
    
    assert "triples" in result
    assert result["triples"] == []


def test_normalize_guarantees_triples_structure():
    """All outputs must have "triples" key, even if empty."""
    test_cases = [
        None,
        {},
        [],
        {"random": "data"},
        {"relations": []},
        {"edges": []},
        "invalid json",
        123,
        True,
    ]
    
    for input_data in test_cases:
        result = normalize_extracted_json(input_data)
        assert isinstance(result, dict), f"Input {input_data} should return dict"
        assert "triples" in result, f"Input {input_data} should have 'triples' key"
        assert isinstance(result["triples"], list), f"Input {input_data} should have list for 'triples'"

