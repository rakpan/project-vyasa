"""
Unit tests for Web Discovery Service.

Tests query generation, domain filtering, deduplication, and Google API integration.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from typing import List

from src.orchestrator.web.discovery import WebDiscoveryService
from src.orchestrator.web.domain_policy import filter_urls, parse_domain_lists, _normalize_domain
from src.orchestrator.schemas.disputes import (
    DisputeContext,
    TriggerSourceType,
    DisputePriority,
)


class TestDomainPolicy:
    """Tests for domain policy filtering."""
    
    def test_normalize_domain_strips_www(self):
        """Test domain normalization strips www. prefix."""
        assert _normalize_domain("www.example.com") == "example.com"
        assert _normalize_domain("WWW.EXAMPLE.COM") == "example.com"
        assert _normalize_domain("example.com") == "example.com"
    
    def test_normalize_domain_strips_protocol(self):
        """Test domain normalization strips protocol."""
        assert _normalize_domain("https://example.com") == "example.com"
        assert _normalize_domain("http://example.com") == "example.com"
        assert _normalize_domain("ftp://example.com") == "example.com"
    
    def test_normalize_domain_strips_path(self):
        """Test domain normalization strips path."""
        assert _normalize_domain("example.com/path/to/page") == "example.com"
        assert _normalize_domain("example.com:8080/path") == "example.com"
    
    def test_normalize_domain_strips_port(self):
        """Test domain normalization strips port."""
        assert _normalize_domain("example.com:8080") == "example.com"
        assert _normalize_domain("example.com:443") == "example.com"
    
    def test_parse_domain_lists(self):
        """Test parsing comma-separated domain lists."""
        allowlist, blocklist = parse_domain_lists(
            "example.com, test.org",
            "blocked.com, another.blocked.com"
        )
        
        assert "example.com" in allowlist
        assert "test.org" in allowlist
        assert "blocked.com" in blocklist
        assert "another.blocked.com" in blocklist
    
    def test_parse_domain_lists_normalizes(self):
        """Test parsing normalizes domains."""
        allowlist, blocklist = parse_domain_lists(
            "www.example.com, https://test.org",
            "http://blocked.com"
        )
        
        assert "example.com" in allowlist
        assert "test.org" in allowlist
        assert "blocked.com" in blocklist
    
    def test_filter_urls_blocklist(self):
        """Test URL filtering removes blocklisted domains."""
        urls = [
            "https://example.com/page1",
            "https://blocked.com/page2",
            "https://test.org/page3",
        ]
        
        blocklist = {"blocked.com"}
        filtered = filter_urls(urls, blocklist=blocklist)
        
        assert "https://example.com/page1" in filtered
        assert "https://test.org/page3" in filtered
        assert "https://blocked.com/page2" not in filtered
    
    def test_filter_urls_allowlist(self):
        """Test URL filtering only allows allowlisted domains."""
        urls = [
            "https://example.com/page1",
            "https://blocked.com/page2",
            "https://test.org/page3",
        ]
        
        allowlist = {"example.com"}
        filtered = filter_urls(urls, allowlist=allowlist)
        
        assert "https://example.com/page1" in filtered
        assert "https://blocked.com/page2" not in filtered
        assert "https://test.org/page3" not in filtered
    
    def test_filter_urls_allowlist_empty_allows_all(self):
        """Test empty allowlist allows all except blocklist."""
        urls = [
            "https://example.com/page1",
            "https://test.org/page2",
        ]
        
        allowlist = set()  # Empty allowlist
        blocklist = set()  # Empty blocklist
        
        filtered = filter_urls(urls, allowlist=allowlist, blocklist=blocklist)
        
        assert len(filtered) == 2
        assert "https://example.com/page1" in filtered
        assert "https://test.org/page2" in filtered
    
    def test_filter_urls_preserves_order(self):
        """Test URL filtering preserves original order."""
        urls = [
            "https://example.com/page1",
            "https://test.org/page2",
            "https://example.com/page3",
        ]
        
        filtered = filter_urls(urls)
        
        assert filtered == urls  # Order preserved
    
    def test_filter_urls_handles_www_variants(self):
        """Test filtering handles www. variants correctly."""
        urls = [
            "https://www.example.com/page1",
            "https://example.com/page2",
        ]
        
        allowlist = {"example.com"}
        filtered = filter_urls(urls, allowlist=allowlist)
        
        # Both should pass (www. is normalized)
        assert len(filtered) == 2


class TestWebDiscoveryService:
    """Tests for WebDiscoveryService."""
    
    @pytest.fixture
    def sample_dispute(self):
        """Create a sample DisputeContext for testing."""
        return DisputeContext.create(
            project_id="project-123",
            job_id="job-456",
            trigger_source_type=TriggerSourceType.RQ,
            trigger_source_id="rq-789",
            disagreement_summary="Conflicting evidence on quantum entanglement",
            required_evidence_type="empirical",
            priority=DisputePriority.HIGH,
        )
    
    @pytest.fixture
    def discovery_service(self):
        """Create a WebDiscoveryService instance with mocked API."""
        return WebDiscoveryService(
            api_key="test-key",
            engine_id="test-engine",
            allowlist="",
            blocklist="blocked.com",
        )
    
    def test_build_queries_generates_3_to_5_queries(self, sample_dispute, discovery_service):
        """Test query generation produces 3-5 queries."""
        queries = discovery_service.build_queries(sample_dispute)
        
        assert 3 <= len(queries) <= 5
        assert all(isinstance(q, str) for q in queries)
        assert all(q.strip() for q in queries)
    
    def test_build_queries_includes_base_summary(self, sample_dispute, discovery_service):
        """Test queries include the disagreement summary."""
        queries = discovery_service.build_queries(sample_dispute)
        
        # At least one query should contain the summary
        summary_words = sample_dispute.disagreement_summary.lower().split()
        found = False
        for query in queries:
            query_lower = query.lower()
            if any(word in query_lower for word in summary_words[:3]):  # Check first 3 words
                found = True
                break
        assert found, "No query contains disagreement summary"
    
    def test_build_queries_includes_evidence_type(self, sample_dispute, discovery_service):
        """Test queries include required evidence type when specified."""
        queries = discovery_service.build_queries(sample_dispute)
        
        # Should have at least one query with evidence type
        assert any("empirical" in q.lower() for q in queries)
    
    def test_build_queries_handles_empty_summary(self, discovery_service):
        """Test query generation handles empty disagreement summary."""
        dispute = DisputeContext.create(
            project_id="project-123",
            job_id="job-456",
            trigger_source_type=TriggerSourceType.CLAIM,
            trigger_source_id="claim-abc",
            disagreement_summary="",  # Empty
        )
        
        queries = discovery_service.build_queries(dispute)
        
        assert queries == []
    
    def test_build_queries_variants_by_trigger_type(self, discovery_service):
        """Test query variants differ based on trigger source type."""
        dispute_rq = DisputeContext.create(
            project_id="p1",
            job_id="j1",
            trigger_source_type=TriggerSourceType.RQ,
            trigger_source_id="rq-1",
            disagreement_summary="Test query",
        )
        
        dispute_claim = DisputeContext.create(
            project_id="p1",
            job_id="j1",
            trigger_source_type=TriggerSourceType.CLAIM,
            trigger_source_id="claim-1",
            disagreement_summary="Test query",
        )
        
        queries_rq = discovery_service.build_queries(dispute_rq)
        queries_claim = discovery_service.build_queries(dispute_claim)
        
        # Should have different query sets
        assert queries_rq != queries_claim
    
    @patch("src.orchestrator.web.discovery.requests.get")
    def test_search_executes_api_calls(self, mock_get, discovery_service):
        """Test search method executes Google API calls."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [
                {"link": "https://example.com/page1"},
                {"link": "https://test.org/page2"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        queries = ["test query 1", "test query 2"]
        urls = discovery_service.search(queries)
        
        assert len(urls) == 2
        assert "https://example.com/page1" in urls
        assert "https://test.org/page2" in urls
        assert mock_get.call_count == 2  # One call per query
    
    @patch("src.orchestrator.web.discovery.requests.get")
    def test_search_deduplicates_urls(self, mock_get, discovery_service):
        """Test search deduplicates URLs across queries."""
        # Mock API responses with duplicate URLs
        mock_response1 = Mock()
        mock_response1.json.return_value = {
            "items": [
                {"link": "https://example.com/page1"},
                {"link": "https://test.org/page2"},
            ]
        }
        mock_response1.raise_for_status = Mock()
        
        mock_response2 = Mock()
        mock_response2.json.return_value = {
            "items": [
                {"link": "https://example.com/page1"},  # Duplicate
                {"link": "https://another.com/page3"},
            ]
        }
        mock_response2.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_response1, mock_response2]
        
        queries = ["query1", "query2"]
        urls = discovery_service.search(queries)
        
        # Should have 3 unique URLs
        assert len(urls) == 3
        assert urls.count("https://example.com/page1") == 1  # Deduplicated
    
    @patch("src.orchestrator.web.discovery.requests.get")
    def test_search_handles_api_errors_gracefully(self, mock_get, discovery_service):
        """Test search handles API errors without crashing."""
        import requests
        
        # Mock API error
        mock_get.side_effect = requests.exceptions.RequestException("API error")
        
        queries = ["test query"]
        urls = discovery_service.search(queries)
        
        # Should return empty list, not crash
        assert urls == []
    
    @patch("src.orchestrator.web.discovery.requests.get")
    def test_discover_full_pipeline(self, mock_get, sample_dispute, discovery_service):
        """Test discover method executes full pipeline."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [
                {"link": "https://example.com/page1"},
                {"link": "https://blocked.com/page2"},  # Should be filtered
                {"link": "https://test.org/page3"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        urls = discovery_service.discover(sample_dispute)
        
        # Should filter out blocked.com
        assert "https://example.com/page1" in urls
        assert "https://test.org/page3" in urls
        assert "https://blocked.com/page2" not in urls
    
    def test_discover_returns_empty_when_api_disabled(self, sample_dispute):
        """Test discover returns empty list when API is not configured."""
        service = WebDiscoveryService(
            api_key="",  # Empty = disabled
            engine_id="",
        )
        
        urls = service.discover(sample_dispute)
        
        assert urls == []
    
    def test_discover_handles_no_queries(self, discovery_service):
        """Test discover handles case when no queries are generated."""
        dispute = DisputeContext.create(
            project_id="p1",
            job_id="j1",
            trigger_source_type=TriggerSourceType.CLAIM,
            trigger_source_id="c1",
            disagreement_summary="",  # Empty = no queries
        )
        
        urls = discovery_service.discover(dispute)
        
        assert urls == []

