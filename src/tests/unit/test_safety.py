"""
Safety tests for schema enforcement and citation validation.
"""

import pytest
from pydantic import ValidationError, BaseModel, Field
from typing import List, Optional


# Test schema models
class TripleModel(BaseModel):
    """Test triple model for schema validation."""
    subject: str = Field(..., min_length=1)
    predicate: str = Field(..., min_length=1)
    object: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)


class GraphModel(BaseModel):
    """Test graph model for schema validation."""
    triples: List[TripleModel] = Field(default_factory=list)
    entities: Optional[List[dict]] = None


class CitationError(Exception):
    """Exception raised when citation validation fails."""
    pass


def validate_citations(text: str, valid_ids: List[str]) -> None:
    """Validate that all citations in text reference valid IDs.
    
    Args:
        text: Text containing citations in format [ID].
        valid_ids: List of valid citation IDs.
        
    Raises:
        CitationError: If text contains citations not in valid_ids.
    """
    import re
    
    # Find all citations in format [ID]
    citations = re.findall(r'\[(\d+)\]', text)
    
    # Check if all citations are in valid_ids
    for citation in citations:
        if citation not in valid_ids:
            raise CitationError(f"Citation [{citation}] not found in valid IDs: {valid_ids}")


class TestSchemaEnforcement:
    """Test suite for schema enforcement using Pydantic."""
    
    def test_valid_schema_passes(self):
        """Test that valid JSON schema passes validation."""
        valid_data = {
            "triples": [
                {
                    "subject": "Input validation",
                    "predicate": "mitigates",
                    "object": "SQL injection",
                    "confidence": 0.9
                }
            ],
            "entities": []
        }
        
        graph = GraphModel(**valid_data)
        assert len(graph.triples) == 1
        assert graph.triples[0].subject == "Input validation"
        assert graph.triples[0].confidence == 0.9
    
    def test_invalid_schema_raises_validation_error(self):
        """Test that invalid JSON schema raises ValidationError."""
        invalid_data = {
            "triples": [
                {
                    "subject": "",  # Empty subject (min_length=1 violation)
                    "predicate": "mitigates",
                    "object": "SQL injection",
                    "confidence": 0.9
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            GraphModel(**invalid_data)
        
        # Verify the error contains field information
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("subject" in str(error) for error in errors)
    
    def test_confidence_out_of_range_raises_error(self):
        """Test that confidence values outside [0.0, 1.0] raise ValidationError."""
        invalid_data = {
            "triples": [
                {
                    "subject": "A",
                    "predicate": "relates",
                    "object": "B",
                    "confidence": 1.5  # Out of range
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            GraphModel(**invalid_data)
        
        errors = exc_info.value.errors()
        assert any("confidence" in str(error).lower() for error in errors)
        assert any("less than or equal to 1" in str(error) or "1.0" in str(error) for error in errors)
    
    def test_missing_required_field_raises_error(self):
        """Test that missing required fields raise ValidationError."""
        invalid_data = {
            "triples": [
                {
                    "subject": "A",
                    "predicate": "relates",
                    # Missing "object" field
                    "confidence": 0.8
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            GraphModel(**invalid_data)
        
        errors = exc_info.value.errors()
        assert any("object" in str(error) for error in errors)
        assert any("required" in str(error).lower() or "missing" in str(error).lower() for error in errors)
    
    def test_wrong_type_raises_error(self):
        """Test that wrong field types raise ValidationError."""
        invalid_data = {
            "triples": [
                {
                    "subject": "A",
                    "predicate": "relates",
                    "object": "B",
                    "confidence": "not-a-number"  # String instead of float that cannot be coerced
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            GraphModel(**invalid_data)
        
        errors = exc_info.value.errors()
        assert any("confidence" in str(error) for error in errors)
        assert any("float" in str(error).lower() or "number" in str(error).lower() for error in errors)


class TestCitationEnforcement:
    """Test suite for citation validation."""
    
    def test_valid_citations_pass(self):
        """Test that valid citations pass validation."""
        text = "This is a fact [claim_a]. Another fact [claim_b]."
        valid_ids = ["claim_a", "claim_b"]
        
        # Should not raise
        validate_citations(text, valid_ids)
    
    def test_invalid_citation_raises_citation_error(self):
        """Test that invalid citation raises CitationError."""
        text = "This is a fact [99]."
        valid_ids = ["claim_a", "claim_b"]
        
        with pytest.raises(CitationError) as exc_info:
            validate_citations(text, valid_ids)
        
        assert "99" in str(exc_info.value)
        assert "not found in valid IDs" in str(exc_info.value)
    
    def test_multiple_invalid_citations_raises_error(self):
        """Test that multiple invalid citations are caught."""
        text = "Fact one [99]. Fact two [100]."
        valid_ids = ["claim_a"]
        
        with pytest.raises(CitationError) as exc_info:
            validate_citations(text, valid_ids)
        
        # Should catch at least one invalid citation
        error_msg = str(exc_info.value)
        assert ("99" in error_msg or "100" in error_msg)
    
    def test_mixed_valid_invalid_citations_raises_error(self):
        """Test that mixed valid/invalid citations raise error."""
        text = "Valid [claim_a]. Invalid [99]."
        valid_ids = ["claim_a", "claim_b"]
        
        with pytest.raises(CitationError) as exc_info:
            validate_citations(text, valid_ids)
        
        assert "99" in str(exc_info.value)
    
    def test_no_citations_passes(self):
        """Test that text with no citations passes validation."""
        text = "This text has no citations."
        valid_ids = ["claim_a"]
        
        # Should not raise
        validate_citations(text, valid_ids)
    
    def test_empty_valid_ids_raises_error(self):
        """Test that citations in text raise error when valid_ids is empty."""
        text = "This has a citation [99]."
        valid_ids = []
        
        with pytest.raises(CitationError):
            validate_citations(text, valid_ids)
    
    def test_citation_format_edge_cases(self):
        """Test citation validation with edge cases."""
        # Multiple citations in one sentence
        text = "Fact [1] and fact [2] and fact [3]."
        valid_ids = ["1", "2", "3"]
        validate_citations(text, valid_ids)  # Should pass
        
        # One invalid
        text = "Fact [1] and fact [99]."
        valid_ids = ["1", "2"]
        with pytest.raises(CitationError):
            validate_citations(text, valid_ids)
