"""
Unit tests for Qdrant payload contract enforcement.

Ensures that PDF chunk ingestion into Qdrant always stores the payload
needed for context anchors and lineage, and that missing payload fields
raise errors in conservative mode.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile

from src.orchestrator.storage.qdrant import QdrantStorage


@pytest.fixture
def mock_qdrant_client():
    """Mock QdrantClient for testing."""
    client = Mock()
    client.get_collections.return_value = Mock(collections=[])
    client.create_collection = Mock()
    client.upsert = Mock()
    client.count = Mock(return_value=Mock(count=0))
    return client


@pytest.fixture
def sample_pdf_path():
    """Create a temporary PDF file for testing."""
    # Create a minimal PDF file (just for testing structure)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        # Write minimal PDF header (not a valid PDF, but enough for testing)
        f.write(b"%PDF-1.4\n")
        f.write(b"1 0 obj\n<< /Type /Catalog >>\nendobj\n")
        f.write(b"xref\n0 0\ntrailer\n<< /Size 0 /Root 1 0 R >>\n")
        f.write(b"startxref\n0\n%%EOF\n")
        pdf_path = Path(f.name)
    
    yield pdf_path
    
    # Cleanup
    if pdf_path.exists():
        pdf_path.unlink()


@pytest.fixture
def qdrant_storage(mock_qdrant_client):
    """Create QdrantStorage instance with mocked client."""
    with patch("src.orchestrator.storage.qdrant.get_qdrant_client", return_value=mock_qdrant_client):
        storage = QdrantStorage(client=mock_qdrant_client)
        return storage


class TestQdrantPayloadContract:
    """Tests for Qdrant payload contract enforcement."""
    
    def test_ingest_generates_payload_fields(self, qdrant_storage, sample_pdf_path, mock_qdrant_client):
        """Asserts ingestion generates payload fields exactly."""
        file_hash = "a" * 64  # SHA256 hex digest
        ingestion_id = "test-ingestion-123"
        project_id = "test-project-456"
        
        # Mock pymupdf to return a simple document
        with patch("pymupdf.open") as mock_open:
            mock_doc = Mock()
            mock_page = Mock()
            mock_page.get_text.return_value = "Sample text content for testing chunking."
            mock_page.rect = Mock(width=612.0, height=792.0)  # Standard US Letter size
            mock_doc.__len__ = Mock(return_value=1)
            mock_doc.__getitem__ = Mock(return_value=mock_page)
            mock_doc.close = Mock()
            mock_open.return_value = mock_doc
            
            # Ingest document
            chunk_count, chunk_metadata = qdrant_storage.ingest_document_chunks(
                pdf_path=str(sample_pdf_path),
                file_hash=file_hash,
                ingestion_id=ingestion_id,
                project_id=project_id,
                rigor_level="exploratory",
            )
            
            # Verify upsert was called
            assert mock_qdrant_client.upsert.called
            
            # Get the points that were upserted
            call_args = mock_qdrant_client.upsert.call_args
            points = call_args.kwargs.get("points") or call_args.args[1] if len(call_args.args) > 1 else []
            
            if not points:
                # Try to get from the first positional arg
                if call_args.args:
                    points = call_args.args[0] if isinstance(call_args.args[0], list) else []
            
            # Verify at least one point was created
            assert len(points) > 0, "No points were upserted"
            
            # Verify each point has required payload fields
            for point in points:
                payload = point.payload if hasattr(point, "payload") else point.get("payload", {})
                
                assert "file_hash" in payload, "Payload missing file_hash"
                assert payload["file_hash"] == file_hash
                
                assert "ingestion_id" in payload, "Payload missing ingestion_id"
                assert payload["ingestion_id"] == ingestion_id
                
                assert "project_id" in payload, "Payload missing project_id"
                assert payload["project_id"] == project_id
                
                assert "page_number" in payload, "Payload missing page_number"
                assert isinstance(payload["page_number"], int)
                assert payload["page_number"] >= 1
                
                assert "chunk_index" in payload, "Payload missing chunk_index"
                assert isinstance(payload["chunk_index"], int)
                
                assert "chunk_text_length" in payload, "Payload missing chunk_text_length"
                assert isinstance(payload["chunk_text_length"], int)
                assert payload["chunk_text_length"] >= 0
    
    def test_conservative_mode_requires_bbox(self, qdrant_storage, sample_pdf_path, mock_qdrant_client):
        """Asserts error if bbox is missing in conservative mode."""
        file_hash = "a" * 64
        ingestion_id = "test-ingestion-123"
        project_id = "test-project-456"
        
        # Mock pymupdf to return a document with no bbox extraction
        with patch("pymupdf.open") as mock_open:
            mock_doc = Mock()
            mock_page = Mock()
            mock_page.get_text.return_value = "Sample text."
            mock_page.rect = Mock(width=612.0, height=792.0)
            # Mock _extract_chunk_bbox to return None (no bbox)
            mock_doc.__len__ = Mock(return_value=1)
            mock_doc.__getitem__ = Mock(return_value=mock_page)
            mock_doc.close = Mock()
            mock_open.return_value = mock_doc
            
            # Mock _extract_chunk_bbox to return None
            with patch.object(qdrant_storage, "_extract_chunk_bbox", return_value=None):
                # In conservative mode, this should raise an error
                with pytest.raises(ValueError, match="missing required field: bbox or span"):
                    qdrant_storage.ingest_document_chunks(
                        pdf_path=str(sample_pdf_path),
                        file_hash=file_hash,
                        ingestion_id=ingestion_id,
                        project_id=project_id,
                        rigor_level="conservative",  # Conservative mode
                    )
    
    def test_exploratory_mode_allows_no_bbox(self, qdrant_storage, sample_pdf_path, mock_qdrant_client):
        """Asserts exploratory mode allows ingestion without bbox."""
        file_hash = "a" * 64
        ingestion_id = "test-ingestion-123"
        project_id = "test-project-456"
        
        # Mock pymupdf
        with patch("pymupdf.open") as mock_open:
            mock_doc = Mock()
            mock_page = Mock()
            mock_page.get_text.return_value = "Sample text."
            mock_page.rect = Mock(width=612.0, height=792.0)
            mock_doc.__len__ = Mock(return_value=1)
            mock_doc.__getitem__ = Mock(return_value=mock_page)
            mock_doc.close = Mock()
            mock_open.return_value = mock_doc
            
            # Mock _extract_chunk_bbox to return None
            with patch.object(qdrant_storage, "_extract_chunk_bbox", return_value=None):
                # In exploratory mode, this should succeed
                chunk_count, chunk_metadata = qdrant_storage.ingest_document_chunks(
                    pdf_path=str(sample_pdf_path),
                    file_hash=file_hash,
                    ingestion_id=ingestion_id,
                    project_id=project_id,
                    rigor_level="exploratory",  # Exploratory mode
                )
                
                # Should succeed without error
                assert chunk_count >= 0
                assert isinstance(chunk_metadata, list)
    
    def test_payload_fields_preserved_in_chunk_metadata(self, qdrant_storage, sample_pdf_path, mock_qdrant_client):
        """Asserts chunk metadata includes payload fields."""
        file_hash = "a" * 64
        ingestion_id = "test-ingestion-123"
        project_id = "test-project-456"
        
        # Mock pymupdf
        with patch("pymupdf.open") as mock_open:
            mock_doc = Mock()
            mock_page = Mock()
            mock_page.get_text.return_value = "Sample text content for testing."
            mock_page.rect = Mock(width=612.0, height=792.0)
            mock_doc.__len__ = Mock(return_value=1)
            mock_doc.__getitem__ = Mock(return_value=mock_page)
            mock_doc.close = Mock()
            mock_open.return_value = mock_doc
            
            chunk_count, chunk_metadata = qdrant_storage.ingest_document_chunks(
                pdf_path=str(sample_pdf_path),
                file_hash=file_hash,
                ingestion_id=ingestion_id,
                project_id=project_id,
                rigor_level="exploratory",
            )
            
            # Verify chunk metadata structure
            assert len(chunk_metadata) > 0, "No chunk metadata returned"
            
            for metadata in chunk_metadata:
                assert "chunk_id" in metadata
                assert "page_number" in metadata
                assert "text_length" in metadata
                assert isinstance(metadata["page_number"], int)
                assert isinstance(metadata["text_length"], int)
                assert metadata["text_length"] >= 0

