"""
Unit tests for graceful Firecrawl unavailability handling.

Tests verify that web augmentation fails gracefully when Firecrawl
sidecar is unreachable, without crashing jobs or attempting graph writes.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from src.orchestrator.web.augmentation_orchestrator import AugmentationOrchestrator
from src.orchestrator.web.firecrawl import FirecrawlBridge
from src.orchestrator.schemas.disputes import DisputeContext, TriggerSourceType, Priority
from src.orchestrator.schemas.review import ReviewTask, ReviewStatus
import requests.exceptions


class TestFirecrawlUnavailable:
    """Tests for graceful handling when Firecrawl is unavailable."""
    
    @pytest.fixture
    def dispute_context(self):
        """Create a sample DisputeContext for testing."""
        return DisputeContext(
            dispute_id="test-dispute-123",
            project_id="test-project-456",
            job_id="test-job-789",
            trigger_source_type=TriggerSourceType.RQ,
            disagreement_summary="Test disagreement",
            required_evidence_type=None,
            priority=Priority.HIGH,
            created_at=datetime.now(timezone.utc),
        )
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock ArangoDB database."""
        db = Mock()
        db.has_collection.return_value = True
        collection = Mock()
        db.collection.return_value = collection
        collection.insert.return_value = {"_key": "test-review-id"}
        return db
    
    def test_firecrawl_connection_error_returns_structured_errors(self):
        """Test that FirecrawlBridge handles connection errors gracefully."""
        bridge = FirecrawlBridge(service_url="http://unreachable:3002", timeout=1)
        
        # Mock requests.post to raise ConnectionError
        with patch("src.orchestrator.web.firecrawl.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
            
            results = bridge.scrape(["https://example.com"])
            
            # Should return structured error result, not raise exception
            assert len(results) == 1
            assert results[0]["url"] == "https://example.com"
            assert results[0]["error"] is not None
            assert "Connection refused" in results[0]["error"]
            assert results[0]["error_type"] == "connection_error"
            assert results[0]["markdown"] == ""
    
    def test_firecrawl_timeout_returns_structured_errors(self):
        """Test that FirecrawlBridge handles timeouts gracefully."""
        bridge = FirecrawlBridge(service_url="http://slow:3002", timeout=1)
        
        with patch("src.orchestrator.web.firecrawl.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
            
            results = bridge.scrape(["https://example.com"])
            
            assert len(results) == 1
            assert results[0]["error"] is not None
            assert results[0]["error_type"] == "timeout"
    
    def test_firecrawl_all_connection_errors_creates_failed_review_task(self, dispute_context, mock_db):
        """Test that orchestrator creates FAILED ReviewTask when Firecrawl is completely unavailable."""
        # Create orchestrator with mocked FirecrawlBridge
        mock_firecrawl = Mock(spec=FirecrawlBridge)
        # All URLs fail with connection errors
        mock_firecrawl.scrape.return_value = [
            {
                "url": "https://example.com",
                "domain": "example.com",
                "title": None,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "markdown": "",
                "error": "Connection refused",
                "error_type": "connection_error",
            },
            {
                "url": "https://test.com",
                "domain": "test.com",
                "title": None,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "markdown": "",
                "error": "Connection refused",
                "error_type": "connection_error",
            },
        ]
        
        mock_discovery = Mock()
        mock_discovery.discover.return_value = ["https://example.com", "https://test.com"]
        
        orchestrator = AugmentationOrchestrator(
            discovery_service=mock_discovery,
            firecrawl_bridge=mock_firecrawl,
            db=mock_db,
        )
        
        # Run augmentation
        review_task = orchestrator.run(dispute_context)
        
        # Should return FAILED ReviewTask with reason
        assert review_task.status == ReviewStatus.FAILED
        assert review_task.reason == "firecrawl_unavailable"
        assert len(review_task.candidate_claims) == 0
        assert review_task.source_quality_score == 0.0
        assert review_task.dispute_id == dispute_context.dispute_id
        assert review_task.project_id == dispute_context.project_id
        assert review_task.job_id == dispute_context.job_id
    
    def test_firecrawl_unavailable_persists_failed_task(self, dispute_context, mock_db):
        """Test that FAILED ReviewTask is persisted when Firecrawl is unavailable."""
        mock_firecrawl = Mock(spec=FirecrawlBridge)
        mock_firecrawl.scrape.return_value = [
            {
                "url": "https://example.com",
                "domain": "example.com",
                "error": "Connection refused",
                "error_type": "connection_error",
            },
        ]
        
        mock_discovery = Mock()
        mock_discovery.discover.return_value = ["https://example.com"]
        
        orchestrator = AugmentationOrchestrator(
            discovery_service=mock_discovery,
            firecrawl_bridge=mock_firecrawl,
            db=mock_db,
        )
        
        review_task = orchestrator.run(dispute_context)
        
        # Verify task was persisted
        assert mock_db.collection.called
        collection = mock_db.collection.return_value
        assert collection.insert.called
        
        # Verify persisted document has correct structure
        call_args = collection.insert.call_args[0][0]
        assert call_args["status"] == "FAILED"
        assert call_args["reason"] == "firecrawl_unavailable"
        assert call_args["dispute_id"] == dispute_context.dispute_id
    
    def test_firecrawl_unavailable_no_graph_writes(self, dispute_context, mock_db):
        """Test that no knowledge graph writes occur when Firecrawl is unavailable."""
        mock_firecrawl = Mock(spec=FirecrawlBridge)
        mock_firecrawl.scrape.return_value = [
            {
                "url": "https://example.com",
                "error": "Connection refused",
                "error_type": "connection_error",
            },
        ]
        
        mock_discovery = Mock()
        mock_discovery.discover.return_value = ["https://example.com"]
        
        # Mock extraction function to verify it's never called
        with patch("src.orchestrator.web.augmentation_orchestrator._extract_claims_from_content") as mock_extract:
            orchestrator = AugmentationOrchestrator(
                discovery_service=mock_discovery,
                firecrawl_bridge=mock_firecrawl,
                db=mock_db,
            )
            
            review_task = orchestrator.run(dispute_context)
            
            # Extraction should never be called (no successful scrapes)
            assert not mock_extract.called
            
            # ReviewTask should be FAILED
            assert review_task.status == ReviewStatus.FAILED
            assert review_task.reason == "firecrawl_unavailable"
    
    def test_firecrawl_partial_failures_continues_workflow(self, dispute_context, mock_db):
        """Test that partial failures (some connection errors, some successes) continue workflow."""
        mock_firecrawl = Mock(spec=FirecrawlBridge)
        # Mix of connection errors and successes
        mock_firecrawl.scrape.return_value = [
            {
                "url": "https://example.com",
                "domain": "example.com",
                "error": "Connection refused",
                "error_type": "connection_error",
            },
            {
                "url": "https://test.com",
                "domain": "test.com",
                "title": "Test Page",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "markdown": "# Test Content",
                "error": None,
            },
        ]
        
        mock_discovery = Mock()
        mock_discovery.discover.return_value = ["https://example.com", "https://test.com"]
        
        # Mock normalization and extraction to return empty (simplified test)
        with patch("src.orchestrator.web.augmentation_orchestrator.EvidenceNormalizer") as mock_normalizer:
            mock_unit = Mock()
            mock_unit.content = "# Test Content"
            mock_unit.provenance_metadata = {"domain": "test.com", "url": "https://test.com"}
            mock_normalizer.normalize_web.return_value = mock_unit
            
            with patch("src.orchestrator.web.augmentation_orchestrator._extract_claims_from_content") as mock_extract:
                mock_extract.return_value = ([], False, None)  # No claims extracted
                
                orchestrator = AugmentationOrchestrator(
                    discovery_service=mock_discovery,
                    firecrawl_bridge=mock_firecrawl,
                    db=mock_db,
                )
                
                review_task = orchestrator.run(dispute_context)
                
                # Should continue workflow (not fail immediately)
                # Since no claims extracted, will return FAILED with reason
                assert review_task.status == ReviewStatus.FAILED
                assert review_task.reason == "no_claims_extracted"
                
                # Normalization should be called for successful scrape
                assert mock_normalizer.normalize_web.called
    
    def test_firecrawl_unavailable_logs_once(self, dispute_context, mock_db):
        """Test that connection errors are logged once, not per-URL."""
        mock_firecrawl = Mock(spec=FirecrawlBridge)
        mock_firecrawl.scrape.return_value = [
            {
                "url": f"https://example{i}.com",
                "error": "Connection refused",
                "error_type": "connection_error",
            }
            for i in range(5)  # 5 URLs, all connection errors
        ]
        
        mock_discovery = Mock()
        mock_discovery.discover.return_value = [f"https://example{i}.com" for i in range(5)]
        
        with patch("src.orchestrator.web.augmentation_orchestrator.logger") as mock_logger:
            orchestrator = AugmentationOrchestrator(
                discovery_service=mock_discovery,
                firecrawl_bridge=mock_firecrawl,
                db=mock_db,
            )
            
            orchestrator.run(dispute_context)
            
            # Should log error once (not 5 times)
            error_calls = [
                call for call in mock_logger.error.call_args_list
                if "Firecrawl service unavailable" in str(call)
            ]
            assert len(error_calls) == 1

