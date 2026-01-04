"""
Unit tests for FirecrawlBridge Cloud API integration.

Tests verify:
- API key validation when WEB_AUGMENTATION_ENABLED=true
- Allowlist enforcement before cloud calls
- Cloud API response mapping (markdown + metadata)
- Per-URL error handling
- Crawl endpoint (disabled by default)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from src.orchestrator.web.firecrawl import FirecrawlBridge
from src.orchestrator.config import WEB_AUGMENTATION_ENABLED


class TestFirecrawlBridgeInitialization:
    """Tests for FirecrawlBridge initialization."""
    
    @patch('src.orchestrator.web.firecrawl.WEB_AUGMENTATION_ENABLED', True)
    def test_missing_api_key_when_enabled_raises_error(self):
        """Test that missing API key raises ValueError when WEB_AUGMENTATION_ENABLED=true."""
        with patch('src.orchestrator.web.firecrawl.FIRECRAWL_API_KEY', ''):
            with pytest.raises(ValueError, match="FIRECRAWL_API_KEY is required"):
                FirecrawlBridge()
    
    @patch('src.orchestrator.web.firecrawl.WEB_AUGMENTATION_ENABLED', False)
    def test_missing_api_key_when_disabled_allowed(self):
        """Test that missing API key is allowed when WEB_AUGMENTATION_ENABLED=false."""
        with patch('src.orchestrator.web.firecrawl.FIRECRAWL_API_KEY', ''):
            bridge = FirecrawlBridge()
            assert bridge.api_key == ""
    
    @patch('src.orchestrator.web.firecrawl.WEB_AUGMENTATION_ENABLED', True)
    def test_api_key_provided_initializes_successfully(self):
        """Test that providing API key initializes successfully."""
        with patch('src.orchestrator.web.firecrawl.FIRECRAWL_API_KEY', 'test-api-key'):
            bridge = FirecrawlBridge()
            assert bridge.api_key == "test-api-key"
            assert bridge.base_url == "https://api.firecrawl.dev"
    
    def test_custom_base_url(self):
        """Test that custom base URL is used."""
        bridge = FirecrawlBridge(api_key="test-key", base_url="https://custom.firecrawl.dev")
        assert bridge.base_url == "https://custom.firecrawl.dev"
        assert bridge.scrape_endpoint == "https://custom.firecrawl.dev/v0/scrape"


class TestFirecrawlBridgeScrape:
    """Tests for FirecrawlBridge.scrape() method."""
    
    @pytest.fixture
    def bridge(self):
        """Create a FirecrawlBridge instance for testing."""
        with patch('src.orchestrator.web.firecrawl.WEB_AUGMENTATION_ENABLED', False):
            return FirecrawlBridge(api_key="test-api-key")
    
    @patch('src.orchestrator.web.firecrawl.requests.post')
    @patch('src.orchestrator.web.firecrawl.filter_urls_by_allowlist')
    def test_allowlist_enforced_before_cloud_call(self, mock_filter, mock_post, bridge):
        """Test that allowlist is enforced before calling Firecrawl Cloud."""
        urls = ["https://fda.gov/page", "https://example.com/page"]
        mock_filter.return_value = ["https://fda.gov/page"]  # Only fda.gov passes
        
        bridge.scrape(urls)
        
        # Verify filter_urls_by_allowlist was called
        mock_filter.assert_called_once_with(urls, bridge.allowlist_patterns)
        
        # Verify only allowlisted URL was scraped
        assert mock_post.call_count == 1
        call_url = mock_post.call_args[1]['json']['url']
        assert call_url == "https://fda.gov/page"
    
    @patch('src.orchestrator.web.firecrawl.requests.post')
    @patch('src.orchestrator.web.firecrawl.filter_urls_by_allowlist')
    def test_cloud_response_mapping_yields_markdown_metadata(self, mock_filter, mock_post, bridge):
        """Test that cloud API response is correctly mapped to markdown + metadata."""
        urls = ["https://fda.gov/page"]
        mock_filter.return_value = urls
        
        # Mock Firecrawl Cloud API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "url": "https://fda.gov/page",
                "markdown": "# Test Content\n\nThis is test markdown.",
                "title": "Test Page Title"
            }
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        results = bridge.scrape(urls)
        
        assert len(results) == 1
        result = results[0]
        assert result["url"] == "https://fda.gov/page"
        assert result["domain"] == "fda.gov"
        assert result["markdown"] == "# Test Content\n\nThis is test markdown."
        assert result["title"] == "Test Page Title"
        assert result["error"] is None
        assert "retrieved_at" in result
        assert isinstance(result["retrieved_at"], str)
    
    @patch('src.orchestrator.web.firecrawl.requests.post')
    @patch('src.orchestrator.web.firecrawl.filter_urls_by_allowlist')
    def test_http_error_handled_per_url(self, mock_filter, mock_post, bridge):
        """Test that HTTP errors are handled per-URL without crashing batch."""
        urls = ["https://fda.gov/page1", "https://fda.gov/page2"]
        mock_filter.return_value = urls
        
        # First URL succeeds, second fails
        mock_response1 = Mock()
        mock_response1.json.return_value = {"data": {"markdown": "Content 1", "title": "Page 1"}}
        mock_response1.raise_for_status = Mock()
        
        mock_response2 = Mock()
        mock_response2.raise_for_status.side_effect = Exception("HTTP 404")
        mock_response2.status_code = 404
        
        mock_post.side_effect = [
            mock_response1,
            Exception("HTTP 404")
        ]
        
        results = bridge.scrape(urls)
        
        assert len(results) == 2
        assert results[0]["error"] is None
        assert results[0]["markdown"] == "Content 1"
        assert results[1]["error"] is not None
        assert "error_type" in results[1]
    
    @patch('src.orchestrator.web.firecrawl.requests.post')
    @patch('src.orchestrator.web.firecrawl.filter_urls_by_allowlist')
    def test_connection_error_handled_gracefully(self, mock_filter, mock_post, bridge):
        """Test that connection errors are handled gracefully."""
        urls = ["https://fda.gov/page"]
        mock_filter.return_value = urls
        
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        results = bridge.scrape(urls)
        
        assert len(results) == 1
        assert results[0]["error"] is not None
        assert results[0]["error_type"] == "connection_error"
        assert "Connection refused" in results[0]["error"]
    
    @patch('src.orchestrator.web.firecrawl.requests.post')
    @patch('src.orchestrator.web.firecrawl.filter_urls_by_allowlist')
    def test_timeout_error_handled_per_url(self, mock_filter, mock_post, bridge):
        """Test that timeout errors are handled per-URL."""
        urls = ["https://fda.gov/page"]
        mock_filter.return_value = urls
        
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Request timeout")
        
        results = bridge.scrape(urls)
        
        assert len(results) == 1
        assert results[0]["error"] is not None
        assert results[0]["error_type"] == "timeout"
    
    @patch('src.orchestrator.web.firecrawl.filter_urls_by_allowlist')
    def test_all_urls_rejected_returns_error_results(self, mock_filter, bridge):
        """Test that if all URLs are rejected by allowlist, error results are returned."""
        urls = ["https://example.com/page1", "https://test.com/page2"]
        mock_filter.return_value = []  # All rejected
        
        results = bridge.scrape(urls)
        
        assert len(results) == 2
        for result in results:
            assert result["error"] is not None
            assert result["error_type"] == "not_allowlisted"
            assert "not in allowlist" in result["error"]


class TestFirecrawlBridgeCrawl:
    """Tests for FirecrawlBridge.crawl() method."""
    
    @pytest.fixture
    def bridge(self):
        """Create a FirecrawlBridge instance for testing."""
        with patch('src.orchestrator.web.firecrawl.WEB_AUGMENTATION_ENABLED', False):
            return FirecrawlBridge(api_key="test-api-key")
    
    @patch('src.orchestrator.web.firecrawl.WEB_CRAWL_ENABLED', False)
    def test_crawl_disabled_raises_error(self, bridge):
        """Test that crawl raises error when WEB_CRAWL_ENABLED=false."""
        with pytest.raises(ValueError, match="Crawl is disabled"):
            bridge.crawl("https://fda.gov")
    
    @patch('src.orchestrator.web.firecrawl.WEB_CRAWL_ENABLED', True)
    @patch('src.orchestrator.web.firecrawl.domain_matches')
    def test_crawl_rejects_non_allowlisted_root_url(self, mock_domain_matches, bridge):
        """Test that crawl rejects root URL not in allowlist."""
        mock_domain_matches.return_value = False  # Domain not in allowlist
        
        with pytest.raises(ValueError, match="not in allowlist"):
            bridge.crawl("https://example.com")
    
    @patch('src.orchestrator.web.firecrawl.WEB_CRAWL_ENABLED', True)
    @patch('src.orchestrator.web.firecrawl.requests.post')
    @patch('src.orchestrator.web.firecrawl.domain_matches')
    def test_crawl_calls_cloud_api_when_enabled(self, mock_domain_matches, mock_post, bridge):
        """Test that crawl calls Firecrawl Cloud API when enabled."""
        mock_domain_matches.return_value = True  # Domain in allowlist
        
        # Mock Firecrawl Cloud crawl API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {
                    "url": "https://fda.gov/page1",
                    "markdown": "# Page 1",
                    "title": "Page 1"
                },
                {
                    "url": "https://fda.gov/page2",
                    "markdown": "# Page 2",
                    "title": "Page 2"
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        results = bridge.crawl("https://fda.gov", max_pages=10, max_depth=2)
        
        assert len(results) == 2
        assert results[0]["url"] == "https://fda.gov/page1"
        assert results[0]["markdown"] == "# Page 1"
        assert results[1]["url"] == "https://fda.gov/page2"
        assert results[1]["markdown"] == "# Page 2"
        
        # Verify API call was made with correct payload
        mock_post.assert_called_once()
        call_payload = mock_post.call_args[1]['json']
        assert call_payload["url"] == "https://fda.gov"
        assert call_payload["crawlerOptions"]["maxPages"] == 10
        assert call_payload["crawlerOptions"]["maxDepth"] == 2
        assert call_payload["formats"] == ["markdown"]
        assert call_payload["onlyMainContent"] is True
        
        # Verify Authorization header
        call_headers = mock_post.call_args[1]['headers']
        assert call_headers["Authorization"] == "Bearer test-api-key"


class TestFirecrawlBridgeHeaders:
    """Tests for FirecrawlBridge HTTP headers."""
    
    @pytest.fixture
    def bridge(self):
        """Create a FirecrawlBridge instance for testing."""
        with patch('src.orchestrator.web.firecrawl.WEB_AUGMENTATION_ENABLED', False):
            return FirecrawlBridge(api_key="test-api-key")
    
    def test_headers_include_authorization(self, bridge):
        """Test that headers include Authorization with API key."""
        headers = bridge._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-api-key"
        assert headers["Content-Type"] == "application/json"
    
    def test_headers_without_api_key(self):
        """Test that headers work without API key (when disabled)."""
        with patch('src.orchestrator.web.firecrawl.WEB_AUGMENTATION_ENABLED', False):
            bridge = FirecrawlBridge(api_key="")
            headers = bridge._get_headers()
            assert "Content-Type" in headers
            assert "Authorization" not in headers

