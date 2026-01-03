"""
Tests for deterministic first glance computation.

Verifies:
1. compute_first_glance produces identical outputs for same PDF
2. Metrics are non-negative and reasonable
3. No LLM variance in results
"""

import pytest
from pathlib import Path
import tempfile

from src.orchestrator.first_glance import compute_first_glance, compute_first_glance_from_path


@pytest.fixture
def mock_pdf_path(tmp_path):
    """Create a minimal mock PDF for testing.
    
    Note: This creates a simple text file, not a real PDF.
    For real PDF tests, use an actual PDF fixture.
    """
    # For now, return None to skip tests that require real PDFs
    # In a real test environment, this would create or reference a test PDF
    return None


class TestFirstGlanceDeterminism:
    """Test that first glance computation is deterministic."""
    
    def test_compute_first_glance_deterministic(self, tmp_path):
        """Test that same PDF produces identical results on multiple runs.
        
        Note: This test requires pymupdf and a real PDF. If pymupdf is not available,
        the test will be skipped or fail gracefully.
        """
        # Create a minimal test PDF using pymupdf if available
        try:
            import pymupdf
        except ImportError:
            pytest.skip("pymupdf not available")
        
        # Create a simple test PDF
        test_pdf_path = tmp_path / "test.pdf"
        doc = pymupdf.open()  # Create new document
        page = doc.new_page()
        page.insert_text((50, 50), "Test document content for first glance computation.")
        doc.save(str(test_pdf_path))
        doc.close()
        
        # Run twice on same PDF
        result1 = compute_first_glance_from_path(test_pdf_path)
        result2 = compute_first_glance_from_path(test_pdf_path)
        
        # Results must be identical
        assert result1 == result2
        
        # Verify required fields exist
        assert "pages" in result1
        assert "text_density" in result1
        assert "tables_detected" in result1
        assert "figures_detected" in result1
    
    def test_compute_first_glance_metrics_non_negative(self, tmp_path):
        """Test that all metrics are non-negative."""
        try:
            import pymupdf
        except ImportError:
            pytest.skip("pymupdf not available")
        
        # Create a simple test PDF
        test_pdf_path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Test content")
        doc.save(str(test_pdf_path))
        doc.close()
        
        result = compute_first_glance_from_path(test_pdf_path)
        
        assert result["pages"] >= 0
        assert result["text_density"] >= 0.0
        assert result["tables_detected"] >= 0
        assert result["figures_detected"] >= 0
    
    def test_compute_first_glance_pages_count(self, tmp_path):
        """Test that pages_count is accurate."""
        try:
            import pymupdf
        except ImportError:
            pytest.skip("pymupdf not available")
        
        # Create a test PDF with 2 pages
        test_pdf_path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page1 = doc.new_page()
        page1.insert_text((50, 50), "Page 1 content")
        page2 = doc.new_page()
        page2.insert_text((50, 50), "Page 2 content")
        doc.save(str(test_pdf_path))
        doc.close()
        
        result = compute_first_glance_from_path(test_pdf_path)
        
        # Pages should be at least 1
        assert result["pages"] >= 1
        assert isinstance(result["pages"], int)
        assert result["pages"] == 2  # We created 2 pages
    
    def test_compute_first_glance_from_bytes(self, tmp_path):
        """Test that compute_first_glance works with bytes input."""
        try:
            import pymupdf
        except ImportError:
            pytest.skip("pymupdf not available")
        
        # Create a test PDF
        test_pdf_path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Test content")
        doc.save(str(test_pdf_path))
        doc.close()
        
        pdf_bytes = test_pdf_path.read_bytes()
        result = compute_first_glance(pdf_bytes)
        
        assert "pages" in result
        assert result["pages"] >= 1
    
    def test_compute_first_glance_missing_file(self):
        """Test that compute_first_glance raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            compute_first_glance_from_path("/nonexistent/file.pdf")
    
    def test_compute_first_glance_invalid_input(self):
        """Test that compute_first_glance raises ValueError for invalid input."""
        with pytest.raises(ValueError):
            compute_first_glance(123)  # Invalid type

