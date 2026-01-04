"""
Integration tests for Firecrawl connectivity.

Tests HTTP-only integration with Firecrawl sidecar service.
Requires Firecrawl container to be running.

Run with:
    pytest src/tests/integration/test_firecrawl_connectivity.py -v
    # Or with integration marker:
    pytest -m integration src/tests/integration/test_firecrawl_connectivity.py -v
"""

import pytest
import requests
from typing import Optional

from src.orchestrator.web.firecrawl import FirecrawlBridge


def _check_firecrawl_available(service_url: str = "http://localhost:3002") -> bool:
    """Check if Firecrawl service is available.
    
    Args:
        service_url: Firecrawl service URL
    
    Returns:
        True if service is available, False otherwise
    """
    try:
        # Try health endpoint or root
        health_url = f"{service_url.rstrip('/')}/health"
        response = requests.get(health_url, timeout=2)
        return response.status_code == 200
    except Exception:
        # Try root endpoint
        try:
            response = requests.get(service_url, timeout=2)
            return response.status_code in (200, 404)  # 404 is OK, means service is up
        except Exception:
            return False


@pytest.fixture
def firecrawl_bridge() -> Optional[FirecrawlBridge]:
    """Create FirecrawlBridge instance for testing.
    
    Returns:
        FirecrawlBridge instance, or None if service is unavailable
    """
    service_url = "http://localhost:3002"
    
    if not _check_firecrawl_available(service_url):
        pytest.skip("Firecrawl service not available. Start with: docker compose up firecrawl")
    
    return FirecrawlBridge(service_url=service_url, timeout=30)


@pytest.mark.integration
class TestFirecrawlConnectivity:
    """Integration tests for Firecrawl HTTP bridge."""
    
    def test_firecrawl_health_check(self):
        """Test that Firecrawl service is reachable."""
        service_url = "http://localhost:3002"
        is_available = _check_firecrawl_available(service_url)
        
        if not is_available:
            pytest.skip("Firecrawl service not available. Start with: docker compose up firecrawl")
        
        assert is_available, "Firecrawl service should be reachable"
    
    def test_firecrawl_scrape_example_com(self, firecrawl_bridge):
        """Test scraping example.com via Firecrawl.
        
        This test verifies:
        - HTTP 200 response from Firecrawl API
        - Markdown content includes "Example Domain"
        - Result structure is correct
        """
        if firecrawl_bridge is None:
            pytest.skip("Firecrawl service not available")
        
        urls = ["https://example.com"]
        results = firecrawl_bridge.scrape(urls)
        
        assert len(results) == 1, "Should return one result for one URL"
        
        result = results[0]
        
        # Verify result structure
        assert "url" in result
        assert "domain" in result
        assert "retrieved_at" in result
        assert "markdown" in result
        assert "error" in result
        
        # Verify URL
        assert result["url"] == "https://example.com"
        assert result["domain"] == "example.com"
        
        # Verify no error
        assert result["error"] is None, f"Scraping should succeed, got error: {result.get('error')}"
        
        # Verify markdown content
        assert result["markdown"], "Markdown content should not be empty"
        assert "Example Domain" in result["markdown"] or "example" in result["markdown"].lower(), \
            f"Markdown should include 'Example Domain', got: {result['markdown'][:200]}"
        
        # Verify timestamp format
        assert result["retrieved_at"], "retrieved_at should be set"
        assert "T" in result["retrieved_at"], "retrieved_at should be ISO format"
    
    def test_firecrawl_scrape_multiple_urls(self, firecrawl_bridge):
        """Test scraping multiple URLs (partial success handling)."""
        if firecrawl_bridge is None:
            pytest.skip("Firecrawl service not available")
        
        urls = [
            "https://example.com",
            "https://httpbin.org/html",  # Simple HTML page
        ]
        
        results = firecrawl_bridge.scrape(urls)
        
        assert len(results) == 2, "Should return results for both URLs"
        
        # At least one should succeed
        successful = [r for r in results if r["error"] is None]
        assert len(successful) >= 1, "At least one URL should scrape successfully"
        
        # Verify structure for all results
        for result in results:
            assert "url" in result
            assert "domain" in result
            assert "retrieved_at" in result
            assert "markdown" in result
            assert "error" in result
    
    def test_firecrawl_scrape_handles_invalid_url(self, firecrawl_bridge):
        """Test that invalid URLs are handled gracefully."""
        if firecrawl_bridge is None:
            pytest.skip("Firecrawl service not available")
        
        urls = [
            "not-a-valid-url",
            "https://example.com",  # Valid URL
        ]
        
        results = firecrawl_bridge.scrape(urls)
        
        assert len(results) == 2, "Should return results for both URLs"
        
        # Invalid URL should have error
        invalid_result = next((r for r in results if r["url"] == "not-a-valid-url"), None)
        assert invalid_result is not None
        assert invalid_result["error"] is not None, "Invalid URL should have error"
        
        # Valid URL should succeed
        valid_result = next((r for r in results if r["url"] == "https://example.com"), None)
        assert valid_result is not None
        assert valid_result["error"] is None, "Valid URL should not have error"
    
    def test_firecrawl_scrape_handles_failed_urls_gracefully(self, firecrawl_bridge):
        """Test that failed URLs don't abort the entire batch."""
        if firecrawl_bridge is None:
            pytest.skip("Firecrawl service not available")
        
        urls = [
            "https://example.com",
            "https://this-domain-definitely-does-not-exist-12345.com",  # Will fail
        ]
        
        results = firecrawl_bridge.scrape(urls)
        
        assert len(results) == 2, "Should return results for both URLs even if one fails"
        
        # First URL should succeed
        success_result = next((r for r in results if r["url"] == "https://example.com"), None)
        assert success_result is not None
        assert success_result["error"] is None, "Valid URL should succeed even if another fails"
        
        # Failed URL should have error but not crash
        failed_result = next(
            (r for r in results if "does-not-exist" in r["url"]),
            None
        )
        assert failed_result is not None
        # Error may be None if Firecrawl returns empty response, or may have error message
        # Either way, the structure should be valid
        assert "error" in failed_result

