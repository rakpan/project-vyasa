"""
Unit tests for Evidence Normalizer.

Tests mapping of Firecrawl results and PDF chunks to NormalizedEvidenceUnit.
"""

import pytest
from datetime import datetime, timezone

from src.orchestrator.web.normalizer import EvidenceNormalizer
from src.orchestrator.schemas.evidence import NormalizedEvidenceUnit, ProvenanceType


class TestEvidenceNormalizerWeb:
    """Tests for normalizing Firecrawl web results."""
    
    def test_normalize_web_basic(self):
        """Test basic web normalization with required fields."""
        firecrawl_item = {
            "url": "https://example.com/page",
            "domain": "example.com",
            "markdown": "# Example Page\n\nThis is example content.",
            "retrieved_at": "2024-01-15T10:30:00Z",
        }
        
        result = EvidenceNormalizer.normalize_web(firecrawl_item)
        
        assert isinstance(result, NormalizedEvidenceUnit)
        assert result.provenance_type == ProvenanceType.WEB
        assert result.content == firecrawl_item["markdown"]
        assert result.provenance_metadata["url"] == "https://example.com/page"
        assert result.provenance_metadata["domain"] == "example.com"
        assert result.content_hash == NormalizedEvidenceUnit.compute_content_hash(
            firecrawl_item["markdown"]
        )
    
    def test_normalize_web_with_title(self):
        """Test web normalization includes title in metadata."""
        firecrawl_item = {
            "url": "https://example.com",
            "domain": "example.com",
            "title": "Example Domain",
            "markdown": "# Example Domain\n\nThis domain is for use in illustrative examples.",
        }
        
        result = EvidenceNormalizer.normalize_web(firecrawl_item)
        
        assert result.provenance_metadata["title"] == "Example Domain"
        assert "url" in result.provenance_metadata
        assert "domain" in result.provenance_metadata
    
    def test_normalize_web_with_headers(self):
        """Test web normalization includes headers if present."""
        firecrawl_item = {
            "url": "https://example.com",
            "domain": "example.com",
            "markdown": "Content here",
            "headers": {
                "content-type": "text/html",
                "x-custom-header": "value",
            },
        }
        
        result = EvidenceNormalizer.normalize_web(firecrawl_item)
        
        assert "headers" in result.provenance_metadata
        assert result.provenance_metadata["headers"]["content-type"] == "text/html"
        assert result.provenance_metadata["headers"]["x-custom-header"] == "value"
    
    def test_normalize_web_content_hash_deterministic(self):
        """Test content hash is deterministic for same content."""
        firecrawl_item = {
            "url": "https://example.com",
            "markdown": "Same content",
        }
        
        result1 = EvidenceNormalizer.normalize_web(firecrawl_item)
        result2 = EvidenceNormalizer.normalize_web(firecrawl_item)
        
        # Hashes should be the same for same content
        assert result1.content_hash == result2.content_hash
        assert result1.content_hash == NormalizedEvidenceUnit.compute_content_hash("Same content")
    
    def test_normalize_web_requires_url(self):
        """Test normalization fails if URL is missing."""
        firecrawl_item = {
            "markdown": "Content without URL",
        }
        
        with pytest.raises(ValueError, match="must include 'url'"):
            EvidenceNormalizer.normalize_web(firecrawl_item)
    
    def test_normalize_web_rejects_error_items(self):
        """Test normalization fails if firecrawl item has error."""
        firecrawl_item = {
            "url": "https://example.com",
            "markdown": "Content",
            "error": "Failed to scrape",
        }
        
        with pytest.raises(ValueError, match="has error"):
            EvidenceNormalizer.normalize_web(firecrawl_item)
    
    def test_normalize_web_handles_empty_markdown(self):
        """Test normalization handles empty markdown with warning."""
        firecrawl_item = {
            "url": "https://example.com",
            "markdown": "",
        }
        
        result = EvidenceNormalizer.normalize_web(firecrawl_item)
        
        assert result.content == ""
        assert result.content_hash == NormalizedEvidenceUnit.compute_content_hash("")
    
    def test_normalize_web_parses_retrieved_at_iso(self):
        """Test normalization parses ISO timestamp correctly."""
        firecrawl_item = {
            "url": "https://example.com",
            "markdown": "Content",
            "retrieved_at": "2024-01-15T10:30:00Z",
        }
        
        result = EvidenceNormalizer.normalize_web(firecrawl_item)
        
        assert result.retrieval_timestamp is not None
        assert result.retrieval_timestamp.tzinfo is not None  # Should be timezone-aware


class TestEvidenceNormalizerPDF:
    """Tests for normalizing PDF chunks."""
    
    def test_normalize_pdf_basic(self):
        """Test basic PDF normalization with required fields."""
        pdf_chunk = {
            "text": "This is a PDF text chunk.",
            "doc_hash": "abc123def456",
        }
        
        result = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        
        assert isinstance(result, NormalizedEvidenceUnit)
        assert result.provenance_type == ProvenanceType.PDF
        assert result.content == pdf_chunk["text"]
        assert result.provenance_metadata["doc_hash"] == "abc123def456"
        assert result.content_hash == NormalizedEvidenceUnit.compute_content_hash(
            pdf_chunk["text"]
        )
    
    def test_normalize_pdf_with_page_number(self):
        """Test PDF normalization includes page number in metadata."""
        pdf_chunk = {
            "text": "Page 5 content",
            "doc_hash": "doc123",
            "page_number": 5,
        }
        
        result = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        
        assert result.provenance_metadata["page_number"] == 5
        assert result.provenance_metadata["doc_hash"] == "doc123"
    
    def test_normalize_pdf_with_bbox(self):
        """Test PDF normalization includes bbox in metadata."""
        pdf_chunk = {
            "text": "Text with bounding box",
            "doc_hash": "doc123",
            "bbox": [100, 200, 300, 400],
        }
        
        result = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        
        assert "bbox" in result.provenance_metadata
        assert result.provenance_metadata["bbox"] == [100, 200, 300, 400]
    
    def test_normalize_pdf_with_span(self):
        """Test PDF normalization includes span in metadata."""
        pdf_chunk = {
            "text": "Text with span",
            "doc_hash": "doc123",
            "span": {"start": 0, "end": 10},
        }
        
        result = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        
        assert "span" in result.provenance_metadata
        assert result.provenance_metadata["span"] == {"start": 0, "end": 10}
    
    def test_normalize_pdf_uses_doc_id_if_no_doc_hash(self):
        """Test PDF normalization uses doc_id if doc_hash not present."""
        pdf_chunk = {
            "text": "Content",
            "doc_id": "document-123",
        }
        
        result = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        
        assert result.provenance_metadata["doc_hash"] == "document-123"
    
    def test_normalize_pdf_uses_content_field(self):
        """Test PDF normalization accepts 'content' field as text."""
        pdf_chunk = {
            "content": "Content from content field",
            "doc_hash": "doc123",
        }
        
        result = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        
        assert result.content == "Content from content field"
    
    def test_normalize_pdf_uses_page_field(self):
        """Test PDF normalization accepts 'page' field as page_number."""
        pdf_chunk = {
            "text": "Content",
            "doc_hash": "doc123",
            "page": 10,
        }
        
        result = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        
        assert result.provenance_metadata["page_number"] == 10
    
    def test_normalize_pdf_content_hash_deterministic(self):
        """Test content hash is deterministic for same content."""
        pdf_chunk = {
            "text": "Same content",
            "doc_hash": "doc123",
        }
        
        result1 = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        result2 = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        
        # Hashes should be the same for same content
        assert result1.content_hash == result2.content_hash
        assert result1.content_hash == NormalizedEvidenceUnit.compute_content_hash("Same content")
    
    def test_normalize_pdf_requires_text(self):
        """Test normalization fails if text is missing."""
        pdf_chunk = {
            "doc_hash": "doc123",
        }
        
        with pytest.raises(ValueError, match="must include 'text' or 'content'"):
            EvidenceNormalizer.normalize_pdf(pdf_chunk)
    
    def test_normalize_pdf_requires_doc_hash(self):
        """Test normalization fails if doc_hash/doc_id is missing."""
        pdf_chunk = {
            "text": "Content",
        }
        
        with pytest.raises(ValueError, match="must include 'doc_hash' or 'doc_id'"):
            EvidenceNormalizer.normalize_pdf(pdf_chunk)
    
    def test_normalize_pdf_rejects_invalid_bbox(self):
        """Test normalization handles invalid bbox gracefully."""
        pdf_chunk = {
            "text": "Content",
            "doc_hash": "doc123",
            "bbox": "invalid",  # Should be list of 4 numbers
        }
        
        # Should not raise, but should not include invalid bbox
        result = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        
        assert "bbox" not in result.provenance_metadata or result.provenance_metadata["bbox"] != "invalid"
    
    def test_normalize_pdf_includes_doc_id_if_different(self):
        """Test PDF normalization includes doc_id if different from doc_hash."""
        pdf_chunk = {
            "text": "Content",
            "doc_hash": "hash123",
            "doc_id": "id456",
        }
        
        result = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        
        assert result.provenance_metadata["doc_hash"] == "hash123"
        assert result.provenance_metadata["doc_id"] == "id456"


class TestEvidenceNormalizerCrossSource:
    """Tests for cross-source consistency."""
    
    def test_web_and_pdf_have_same_structure(self):
        """Test that web and PDF normalization produce same structure."""
        firecrawl_item = {
            "url": "https://example.com",
            "markdown": "Test content",
        }
        
        pdf_chunk = {
            "text": "Test content",
            "doc_hash": "doc123",
        }
        
        web_result = EvidenceNormalizer.normalize_web(firecrawl_item)
        pdf_result = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        
        # Both should have same content hash for same content
        assert web_result.content_hash == pdf_result.content_hash
        
        # Both should have same structure
        assert hasattr(web_result, "id")
        assert hasattr(pdf_result, "id")
        assert hasattr(web_result, "content")
        assert hasattr(pdf_result, "content")
        assert hasattr(web_result, "content_hash")
        assert hasattr(pdf_result, "content_hash")
        assert hasattr(web_result, "provenance_type")
        assert hasattr(pdf_result, "provenance_type")
        assert hasattr(web_result, "provenance_metadata")
        assert hasattr(pdf_result, "provenance_metadata")
        assert hasattr(web_result, "retrieval_timestamp")
        assert hasattr(pdf_result, "retrieval_timestamp")
    
    def test_content_hash_independent_of_provenance(self):
        """Test content hash depends only on content, not provenance."""
        firecrawl_item = {
            "url": "https://example.com",
            "markdown": "Same content",
        }
        
        pdf_chunk = {
            "text": "Same content",
            "doc_hash": "doc123",
        }
        
        web_result = EvidenceNormalizer.normalize_web(firecrawl_item)
        pdf_result = EvidenceNormalizer.normalize_pdf(pdf_chunk)
        
        # Same content should produce same hash regardless of source
        assert web_result.content_hash == pdf_result.content_hash

