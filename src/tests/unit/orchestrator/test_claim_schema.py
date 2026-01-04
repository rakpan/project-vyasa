"""
Unit tests for canonical Claim schema and SourceAnchor validation.

Tests ensure:
- Claim schema validates all required fields
- SourceAnchor validation (at least one of bbox/span/snippet)
- Anchor thread preservation (serialization/deserialization)
- Conservative mode requires source_anchor
"""

import pytest
from pydantic import ValidationError

from src.orchestrator.schemas.claims import Claim, SourceAnchor


class TestSourceAnchor:
    """Test SourceAnchor model validation."""
    
    def test_source_anchor_requires_location(self):
        """Test that SourceAnchor requires at least one of bbox/span/snippet."""
        # Missing all location fields should fail
        with pytest.raises(ValidationError) as exc_info:
            SourceAnchor(
                doc_id="a" * 64,
                page_number=1,
            )
        assert "bbox" in str(exc_info.value).lower() or "span" in str(exc_info.value).lower() or "snippet" in str(exc_info.value).lower()
    
    def test_source_anchor_with_bbox(self):
        """Test SourceAnchor with bbox."""
        anchor = SourceAnchor(
            doc_id="a" * 64,
            page_number=1,
            bbox={"x": 100.0, "y": 200.0, "w": 300.0, "h": 400.0},
        )
        assert anchor.doc_id == "a" * 64
        assert anchor.page_number == 1
        assert anchor.bbox == {"x": 100.0, "y": 200.0, "w": 300.0, "h": 400.0}
        assert anchor.span is None
        assert anchor.snippet is None
    
    def test_source_anchor_with_span(self):
        """Test SourceAnchor with span."""
        anchor = SourceAnchor(
            doc_id="a" * 64,
            page_number=1,
            span={"start": 0, "end": 100},
        )
        assert anchor.span == {"start": 0, "end": 100}
        assert anchor.bbox is None
        assert anchor.snippet is None
    
    def test_source_anchor_with_snippet(self):
        """Test SourceAnchor with snippet."""
        anchor = SourceAnchor(
            doc_id="a" * 64,
            page_number=1,
            snippet="Sample text snippet",
        )
        assert anchor.snippet == "Sample text snippet"
        assert anchor.bbox is None
        assert anchor.span is None
    
    def test_source_anchor_with_all_fields(self):
        """Test SourceAnchor with all fields."""
        anchor = SourceAnchor(
            doc_id="a" * 64,
            page_number=1,
            bbox={"x": 100.0, "y": 200.0, "w": 300.0, "h": 400.0},
            span={"start": 0, "end": 100},
            snippet="Sample text",
        )
        assert anchor.bbox is not None
        assert anchor.span is not None
        assert anchor.snippet == "Sample text"
    
    def test_source_anchor_bbox_validation(self):
        """Test bbox validation."""
        # Missing required keys
        with pytest.raises(ValidationError) as exc_info:
            SourceAnchor(
                doc_id="a" * 64,
                page_number=1,
                bbox={"x": 100.0, "y": 200.0},  # Missing w, h
            )
        assert "bbox" in str(exc_info.value).lower()
        
        # Invalid span (end < start)
        with pytest.raises(ValidationError) as exc_info:
            SourceAnchor(
                doc_id="a" * 64,
                page_number=1,
                span={"start": 100, "end": 50},  # Invalid
            )
        assert "span" in str(exc_info.value).lower()
    
    def test_source_anchor_page_validation(self):
        """Test page_number validation."""
        with pytest.raises(ValidationError) as exc_info:
            SourceAnchor(
                doc_id="a" * 64,
                page_number=0,  # Must be >= 1
                snippet="test",
            )
        assert "page_number" in str(exc_info.value).lower()


class TestClaimSchema:
    """Test Claim model validation."""
    
    def test_claim_required_fields(self):
        """Test that required fields are validated."""
        # Missing claim_id
        with pytest.raises(ValidationError) as exc_info:
            Claim(
                subject="Subject",
                predicate="predicate",
                object="Object",
                confidence=0.9,
                ingestion_id="ingestion-123",
                file_hash="a" * 64,
            )
        assert "claim_id" in str(exc_info.value)
        
        # Missing subject
        with pytest.raises(ValidationError) as exc_info:
            Claim(
                claim_id="claim-123",
                predicate="predicate",
                object="Object",
                confidence=0.9,
                ingestion_id="ingestion-123",
                file_hash="a" * 64,
            )
        assert "subject" in str(exc_info.value)
    
    def test_claim_valid_instantiation(self):
        """Test valid Claim instantiation."""
        anchor = SourceAnchor(
            doc_id="a" * 64,
            page_number=1,
            snippet="Sample text",
        )
        
        claim = Claim(
            claim_id="claim-123",
            subject="Subject",
            predicate="predicate",
            object="Object",
            confidence=0.9,
            rq_hits=["rq1"],
            ingestion_id="ingestion-123",
            file_hash="a" * 64,
            source_anchor=anchor,
        )
        
        assert claim.claim_id == "claim-123"
        assert claim.subject == "Subject"
        assert claim.predicate == "predicate"
        assert claim.object == "Object"
        assert claim.confidence == 0.9
        assert claim.source_anchor is not None
        assert claim.source_anchor.doc_id == "a" * 64
    
    def test_claim_confidence_validation(self):
        """Test confidence score validation."""
        # Confidence > 1.0 should fail
        with pytest.raises(ValidationError) as exc_info:
            Claim(
                claim_id="claim-123",
                subject="Subject",
                predicate="predicate",
                object="Object",
                confidence=1.5,  # Invalid
                ingestion_id="ingestion-123",
                file_hash="a" * 64,
            )
        assert "confidence" in str(exc_info.value).lower()
        
        # Confidence < 0.0 should fail
        with pytest.raises(ValidationError) as exc_info:
            Claim(
                claim_id="claim-123",
                subject="Subject",
                predicate="predicate",
                object="Object",
                confidence=-0.1,  # Invalid
                ingestion_id="ingestion-123",
                file_hash="a" * 64,
            )
        assert "confidence" in str(exc_info.value).lower()
    
    def test_claim_generate_claim_id(self):
        """Test deterministic claim_id generation."""
        claim_id1 = Claim.generate_claim_id(
            subject="Subject",
            predicate="predicate",
            obj="Object",
            file_hash="a" * 64,
            page_number=1,
        )
        
        claim_id2 = Claim.generate_claim_id(
            subject="Subject",
            predicate="predicate",
            obj="Object",
            file_hash="a" * 64,
            page_number=1,
        )
        
        # Should be deterministic
        assert claim_id1 == claim_id2
        assert len(claim_id1) == 64  # SHA256 hex digest
        
        # Different page should produce different ID
        claim_id3 = Claim.generate_claim_id(
            subject="Subject",
            predicate="predicate",
            obj="Object",
            file_hash="a" * 64,
            page_number=2,
        )
        assert claim_id1 != claim_id3
    
    def test_claim_from_triple_dict(self):
        """Test creating Claim from triple dictionary."""
        triple = {
            "subject": "Subject",
            "predicate": "predicate",
            "object": "Object",
            "confidence": 0.9,
            "rq_hits": ["rq1"],
            "source_pointer": {
                "doc_hash": "a" * 64,
                "page": 1,
                "bbox": [100, 200, 400, 600],
                "snippet": "Sample text",
            },
        }
        
        claim = Claim.from_triple_dict(triple, ingestion_id="ingestion-123", rigor_level="exploratory")
        
        assert claim.subject == "Subject"
        assert claim.predicate == "predicate"
        assert claim.object == "Object"
        assert claim.confidence == 0.9
        assert claim.ingestion_id == "ingestion-123"
        assert claim.source_anchor is not None
        assert claim.source_anchor.doc_id == "a" * 64
        assert claim.source_anchor.page_number == 1
        assert claim.source_anchor.bbox is not None
        assert claim.source_anchor.bbox["x"] == 100.0
        assert claim.source_anchor.bbox["y"] == 200.0
        assert claim.source_anchor.bbox["w"] == 300.0  # 400 - 100
        assert claim.source_anchor.bbox["h"] == 400.0  # 600 - 200
    
    def test_claim_from_triple_dict_conservative_mode(self):
        """Test that conservative mode requires source_anchor."""
        triple = {
            "subject": "Subject",
            "predicate": "predicate",
            "object": "Object",
            "confidence": 0.9,
        }
        
        # Should fail in conservative mode without source_pointer
        with pytest.raises(ValueError) as exc_info:
            Claim.from_triple_dict(triple, ingestion_id="ingestion-123", rigor_level="conservative")
        assert "source_anchor" in str(exc_info.value).lower()
        
        # Should succeed in exploratory mode
        claim = Claim.from_triple_dict(triple, ingestion_id="ingestion-123", rigor_level="exploratory")
        assert claim.source_anchor is None
    
    def test_claim_from_triple_dict_with_existing_source_anchor(self):
        """Test creating Claim from triple with existing source_anchor."""
        triple = {
            "subject": "Subject",
            "predicate": "predicate",
            "object": "Object",
            "confidence": 0.9,
            "source_anchor": {
                "doc_id": "a" * 64,
                "page_number": 1,
                "snippet": "Sample text",
            },
        }
        
        claim = Claim.from_triple_dict(triple, ingestion_id="ingestion-123")
        
        assert claim.source_anchor is not None
        assert claim.source_anchor.doc_id == "a" * 64
        assert claim.source_anchor.snippet == "Sample text"


class TestAnchorThread:
    """Test anchor thread preservation through serialization."""
    
    def test_anchor_serialization_round_trip(self):
        """Test that source_anchor is preserved through serialization."""
        anchor = SourceAnchor(
            doc_id="a" * 64,
            page_number=1,
            bbox={"x": 100.0, "y": 200.0, "w": 300.0, "h": 400.0},
            snippet="Sample text",
        )
        
        claim = Claim(
            claim_id="claim-123",
            subject="Subject",
            predicate="predicate",
            object="Object",
            confidence=0.9,
            ingestion_id="ingestion-123",
            file_hash="a" * 64,
            source_anchor=anchor,
        )
        
        # Serialize to dict
        claim_dict = claim.model_dump()
        
        # Deserialize from dict
        restored_claim = Claim(**claim_dict)
        
        # Verify anchor fields are identical
        assert restored_claim.source_anchor is not None
        assert restored_claim.source_anchor.doc_id == anchor.doc_id
        assert restored_claim.source_anchor.page_number == anchor.page_number
        assert restored_claim.source_anchor.bbox == anchor.bbox
        assert restored_claim.source_anchor.snippet == anchor.snippet
    
    def test_anchor_preserved_in_claim_dict(self):
        """Test that source_anchor is included in claim.model_dump()."""
        anchor = SourceAnchor(
            doc_id="a" * 64,
            page_number=1,
            span={"start": 0, "end": 100},
        )
        
        claim = Claim(
            claim_id="claim-123",
            subject="Subject",
            predicate="predicate",
            object="Object",
            confidence=0.9,
            ingestion_id="ingestion-123",
            file_hash="a" * 64,
            source_anchor=anchor,
        )
        
        claim_dict = claim.model_dump()
        
        assert "source_anchor" in claim_dict
        assert claim_dict["source_anchor"]["doc_id"] == "a" * 64
        assert claim_dict["source_anchor"]["page_number"] == 1
        assert claim_dict["source_anchor"]["span"] == {"start": 0, "end": 100}
    
    def test_anchor_from_source_pointer_conversion(self):
        """Test conversion from source_pointer to source_anchor preserves data."""
        triple = {
            "subject": "Subject",
            "predicate": "predicate",
            "object": "Object",
            "confidence": 0.9,
            "file_hash": "a" * 64,
            "source_pointer": {
                "doc_hash": "a" * 64,
                "page": 2,
                "bbox": [50, 100, 250, 300],
                "snippet": "Evidence text",
            },
        }
        
        claim = Claim.from_triple_dict(triple, ingestion_id="ingestion-123")
        
        # Verify conversion preserved all data
        assert claim.source_anchor is not None
        assert claim.source_anchor.doc_id == "a" * 64
        assert claim.source_anchor.page_number == 2
        assert claim.source_anchor.bbox is not None
        assert claim.source_anchor.bbox["x"] == 50.0
        assert claim.source_anchor.bbox["y"] == 100.0
        assert claim.source_anchor.bbox["w"] == 200.0  # 250 - 50
        assert claim.source_anchor.bbox["h"] == 200.0  # 300 - 100
        assert claim.source_anchor.snippet == "Evidence text"

