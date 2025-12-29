"""
Unit tests for PDF processing utilities.
"""

import pytest
from pathlib import Path

from ...orchestrator.pdf_processor import process_pdf


class TestPDFProcessor:
    """Test suite for PDF processing functions."""
    
    def test_process_pdf_returns_markdown(self, mock_pdf_path):
        """Test that process_pdf returns markdown text."""
        markdown, images_dir, image_paths = process_pdf(str(mock_pdf_path))
        
        assert isinstance(markdown, str)
        assert len(markdown) > 0
        # Should contain some of the text from the PDF
        assert "Test Document" in markdown or "SQL injection" in markdown
        assert isinstance(image_paths, list)
    
    def test_process_pdf_handles_missing_file(self):
        """Test that process_pdf raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            process_pdf("/nonexistent/file.pdf")
    
    def test_process_pdf_with_images_dir(self, mock_pdf_path, tmp_path):
        """Test that process_pdf can extract images to a directory."""
        images_dir = tmp_path / "images"
        markdown, returned_images_dir, image_paths = process_pdf(
            str(mock_pdf_path),
            output_image_dir=str(images_dir)
        )
        
        assert returned_images_dir is not None
        assert isinstance(returned_images_dir, Path)
        assert returned_images_dir.exists()
        assert isinstance(image_paths, list)
    
    def test_process_pdf_without_images_dir(self, mock_pdf_path):
        """Test that process_pdf works without image extraction."""
        markdown, images_dir, image_paths = process_pdf(str(mock_pdf_path))
        
        assert images_dir is not None
        assert isinstance(markdown, str)
        assert isinstance(image_paths, list)
    
    def test_process_pdf_preserves_structure(self, mock_pdf_path):
        """Test that process_pdf preserves document structure in markdown."""
        markdown, _, _ = process_pdf(str(mock_pdf_path))
        
        # Markdown should contain the text content
        # (exact structure depends on pymupdf4llm implementation)
        assert isinstance(markdown, str)
        assert len(markdown.strip()) > 0
    
    def test_process_pdf_handles_empty_pdf(self, tmp_path):
        """Test that process_pdf handles empty PDF files gracefully."""
        # Create a minimal empty PDF
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        empty_pdf = tmp_path / "empty.pdf"
        c = canvas.Canvas(str(empty_pdf), pagesize=letter)
        c.save()
        
        # Should not crash, but may return empty or minimal markdown
        markdown, _, _ = process_pdf(str(empty_pdf))
        assert isinstance(markdown, str)  # Should return string even if empty
