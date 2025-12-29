"""
Unit tests for JSON normalization utilities.
"""

import pytest
from src.orchestrator.normalize import normalize_extracted_json


def test_already_correct_structure():
    """Test normalization of already-correct structure."""
    input_data = {
        "triples": [
            {"subject": "A", "predicate": "relates", "object": "B", "confidence": 0.9}
        ],
        "entities": [{"name": "A"}],
    }
    result = normalize_extracted_json(input_data)
    assert "triples" in result
    assert len(result["triples"]) == 1
    assert result["triples"][0]["subject"] == "A"
    assert result["triples"][0]["predicate"] == "relates"
    assert result["triples"][0]["object"] == "B"
    assert result["triples"][0]["confidence"] == 0.9
    assert "entities" in result  # Preserved


def test_list_of_lists():
    """Test normalization of list-of-lists format."""
    input_data = [
        ["subject1", "predicate1", "object1"],
        ["subject2", "predicate2", "object2", "evidence2", 0.8],
    ]
    result = normalize_extracted_json(input_data)
    assert "triples" in result
    assert len(result["triples"]) == 2
    assert result["triples"][0]["subject"] == "subject1"
    assert result["triples"][0]["predicate"] == "predicate1"
    assert result["triples"][0]["object"] == "object1"
    assert result["triples"][1]["evidence"] == "evidence2"
    assert result["triples"][1]["confidence"] == 0.8


def test_relations_key():
    """Test normalization when triples are under 'relations' key."""
    input_data = {
        "relations": [
            {"subject": "A", "predicate": "causes", "object": "B"}
        ],
        "entities": [{"name": "A"}],
    }
    result = normalize_extracted_json(input_data)
    assert "triples" in result
    assert len(result["triples"]) == 1
    assert result["triples"][0]["subject"] == "A"
    assert "entities" in result  # Preserved


def test_edges_key():
    """Test normalization when triples are under 'edges' key."""
    input_data = {
        "edges": [
            {"s": "A", "p": "relates", "o": "B"}  # Short form keys
        ],
    }
    result = normalize_extracted_json(input_data)
    assert "triples" in result
    assert len(result["triples"]) == 1
    assert result["triples"][0]["subject"] == "A"
    assert result["triples"][0]["predicate"] == "relates"
    assert result["triples"][0]["object"] == "B"


def test_string_json():
    """Test normalization of JSON string."""
    input_data = '{"triples": [{"subject": "A", "predicate": "relates", "object": "B"}]}'
    result = normalize_extracted_json(input_data)
    assert "triples" in result
    assert len(result["triples"]) == 1


def test_invalid_json_string():
    """Test normalization of invalid JSON string."""
    input_data = "not valid json"
    result = normalize_extracted_json(input_data)
    assert "triples" in result
    assert result["triples"] == []  # Empty on error


def test_none_input():
    """Test normalization of None input."""
    result = normalize_extracted_json(None)
    assert "triples" in result
    assert result["triples"] == []


def test_empty_dict():
    """Test normalization of empty dict."""
    result = normalize_extracted_json({})
    assert "triples" in result
    assert result["triples"] == []


def test_missing_triples_key():
    """Test normalization when triples key is missing."""
    input_data = {
        "entities": [{"name": "A"}],
        "metadata": {"source": "test"},
    }
    result = normalize_extracted_json(input_data)
    assert "triples" in result
    assert result["triples"] == []
    assert "entities" in result  # Preserved
    assert "metadata" in result  # Preserved


def test_short_form_keys():
    """Test normalization with short form keys (s, p, o)."""
    input_data = {
        "triples": [
            {"s": "subject1", "p": "predicate1", "o": "object1", "conf": 0.7}
        ],
    }
    result = normalize_extracted_json(input_data)
    assert result["triples"][0]["subject"] == "subject1"
    assert result["triples"][0]["predicate"] == "predicate1"
    assert result["triples"][0]["object"] == "object1"
    assert result["triples"][0]["confidence"] == 0.7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

