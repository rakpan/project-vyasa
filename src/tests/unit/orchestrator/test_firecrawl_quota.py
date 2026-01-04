"""
Unit tests for Firecrawl Cloud quota enforcement.

Tests verify:
- Quota exceeded prevents calls and creates FAILED ReviewTask
- Quota increments deterministically
- Priority gating works (MEDIUM/LOW do not spend)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from src.orchestrator.web.quota import can_spend, record_spend, get_usage, _get_month_key
from src.orchestrator.web.augmentation_orchestrator import AugmentationOrchestrator
from src.orchestrator.schemas.disputes import DisputeContext, DisputePriority, TriggerSourceType
from src.orchestrator.schemas.review import ReviewStatus


class TestQuotaTracking:
    """Tests for quota tracking functions."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock ArangoDB database."""
        db = Mock()
        collection = Mock()
        db.has_collection.return_value = True
        db.collection.return_value = collection
        db.create_collection = Mock()
        return db, collection
    
    def test_can_spend_with_available_quota(self, mock_db):
        """Test that can_spend returns True when quota is available."""
        db, collection = mock_db
        collection.get.return_value = {"requests_used": 100, "last_updated": "2025-01-01T00:00:00Z"}
        
        # Quota is 500, 100 used, checking 1 more
        result = can_spend(db, n=1)
        assert result is True
    
    def test_can_spend_exceeds_quota(self, mock_db):
        """Test that can_spend returns False when quota would be exceeded."""
        db, collection = mock_db
        collection.get.return_value = {"requests_used": 500, "last_updated": "2025-01-01T00:00:00Z"}
        
        # Quota is 500, 500 used, checking 1 more
        result = can_spend(db, n=1)
        assert result is False
    
    def test_can_spend_creates_collection_if_missing(self, mock_db):
        """Test that can_spend creates collection if it doesn't exist."""
        db, collection = mock_db
        db.has_collection.return_value = False
        collection.get.side_effect = Exception("Document not found")
        
        result = can_spend(db, n=1)
        
        # Should create collection and allow spend (new month, 0 used)
        db.create_collection.assert_called_once_with("web_usage")
        assert result is True
    
    def test_record_spend_increments_usage(self, mock_db):
        """Test that record_spend increments usage deterministically."""
        db, collection = mock_db
        collection.get.return_value = {"requests_used": 100, "last_updated": "2025-01-01T00:00:00Z"}
        
        result = record_spend(db, n=5)
        
        assert result is True
        # Verify update was called with incremented value
        collection.update.assert_called_once()
        call_args = collection.update.call_args[0][0]
        assert call_args["requests_used"] == 105
    
    def test_record_spend_creates_document_if_missing(self, mock_db):
        """Test that record_spend creates document if it doesn't exist."""
        db, collection = mock_db
        collection.get.side_effect = Exception("Document not found")
        
        result = record_spend(db, n=3)
        
        assert result is True
        # Verify update was called with initial value
        collection.update.assert_called_once()
        call_args = collection.update.call_args[0][0]
        assert call_args["requests_used"] == 3
    
    def test_get_usage_returns_stats(self, mock_db):
        """Test that get_usage returns usage statistics."""
        db, collection = mock_db
        collection.get.return_value = {"requests_used": 150, "last_updated": "2025-01-01T00:00:00Z"}
        
        stats = get_usage(db)
        
        assert stats is not None
        assert stats["requests_used"] == 150
        assert stats["quota"] == 500
        assert stats["remaining"] == 350
        assert "month" in stats
    
    def test_get_usage_handles_missing_collection(self, mock_db):
        """Test that get_usage handles missing collection gracefully."""
        db, collection = mock_db
        db.has_collection.return_value = False
        
        stats = get_usage(db)
        
        assert stats is not None
        assert stats["requests_used"] == 0
        assert stats["remaining"] == 500


class TestQuotaEnforcementInOrchestrator:
    """Tests for quota enforcement in AugmentationOrchestrator."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock ArangoDB database."""
        db = Mock()
        collection = Mock()
        db.has_collection.return_value = True
        db.collection.return_value = collection
        db.create_collection = Mock()
        return db
    
    @pytest.fixture
    def high_priority_dispute(self):
        """Create a HIGH priority dispute."""
        return DisputeContext.create(
            project_id="test-project",
            job_id="test-job",
            trigger_source_type=TriggerSourceType.RQ,
            trigger_source_id="rq-1",
            disagreement_summary="Test disagreement",
            priority=DisputePriority.HIGH,
        )
    
    @pytest.fixture
    def medium_priority_dispute(self):
        """Create a MEDIUM priority dispute."""
        return DisputeContext.create(
            project_id="test-project",
            job_id="test-job",
            trigger_source_type=TriggerSourceType.RQ,
            trigger_source_id="rq-1",
            disagreement_summary="Test disagreement",
            priority=DisputePriority.MEDIUM,
        )
    
    @pytest.fixture
    def manual_search_dispute(self):
        """Create a MANUAL_SEARCH dispute (bypasses priority gate)."""
        return DisputeContext.create(
            project_id="test-project",
            job_id="test-job",
            trigger_source_type=TriggerSourceType.MANUAL_SEARCH,
            trigger_source_id="manual-1",
            disagreement_summary="User-initiated search",
            priority=DisputePriority.MEDIUM,  # Even MEDIUM is allowed for MANUAL_SEARCH
        )
    
    @patch('src.orchestrator.web.augmentation_orchestrator.WEB_AUGMENTATION_ENABLED', True)
    @patch('src.orchestrator.web.augmentation_orchestrator.can_spend')
    @patch('src.orchestrator.web.augmentation_orchestrator.WebDiscoveryService')
    @patch('src.orchestrator.web.augmentation_orchestrator.FirecrawlBridge')
    def test_quota_exceeded_creates_failed_review_task(
        self, mock_firecrawl, mock_discovery, mock_can_spend, mock_db, high_priority_dispute
    ):
        """Test that quota exceeded prevents calls and creates FAILED ReviewTask."""
        mock_can_spend.return_value = False  # Quota exceeded
        
        orchestrator = AugmentationOrchestrator(db=mock_db)
        result = orchestrator.run(high_priority_dispute)
        
        assert result.status == ReviewStatus.FAILED
        assert result.reason == "quota_exceeded"
        assert len(result.candidate_claims) == 0
        
        # Verify Firecrawl was never called
        mock_firecrawl.return_value.scrape.assert_not_called()
    
    @patch('src.orchestrator.web.augmentation_orchestrator.WEB_AUGMENTATION_ENABLED', True)
    @patch('src.orchestrator.web.augmentation_orchestrator.can_spend')
    @patch('src.orchestrator.web.augmentation_orchestrator.record_spend')
    @patch('src.orchestrator.web.augmentation_orchestrator.WebDiscoveryService')
    @patch('src.orchestrator.web.augmentation_orchestrator.FirecrawlBridge')
    def test_quota_increments_after_successful_scrape(
        self, mock_firecrawl, mock_discovery, mock_record_spend, mock_can_spend, mock_db, high_priority_dispute
    ):
        """Test that quota increments deterministically after successful scrape."""
        mock_can_spend.return_value = True  # Quota available
        mock_discovery.return_value.discover.return_value = ["https://fda.gov/page1", "https://fda.gov/page2"]
        mock_firecrawl.return_value.scrape.return_value = [
            {"url": "https://fda.gov/page1", "markdown": "# Content", "error": None},
            {"url": "https://fda.gov/page2", "markdown": "# Content 2", "error": None},
        ]
        
        orchestrator = AugmentationOrchestrator(db=mock_db)
        orchestrator.run(high_priority_dispute)
        
        # Verify record_spend was called with correct count (2 URLs = 2 requests)
        mock_record_spend.assert_called_once_with(mock_db, n=2)
    
    @patch('src.orchestrator.web.augmentation_orchestrator.WEB_AUGMENTATION_ENABLED', True)
    @patch('src.orchestrator.web.augmentation_orchestrator.WebDiscoveryService')
    @patch('src.orchestrator.web.augmentation_orchestrator.FirecrawlBridge')
    def test_medium_priority_does_not_spend(
        self, mock_firecrawl, mock_discovery, mock_db, medium_priority_dispute
    ):
        """Test that MEDIUM priority disputes do not spend quota."""
        orchestrator = AugmentationOrchestrator(db=mock_db)
        result = orchestrator.run(medium_priority_dispute)
        
        assert result.status == ReviewStatus.FAILED
        assert result.reason == "priority_gate_failed"
        
        # Verify Firecrawl was never called
        mock_firecrawl.return_value.scrape.assert_not_called()
    
    @patch('src.orchestrator.web.augmentation_orchestrator.WEB_AUGMENTATION_ENABLED', True)
    @patch('src.orchestrator.web.augmentation_orchestrator.WebDiscoveryService')
    @patch('src.orchestrator.web.augmentation_orchestrator.FirecrawlBridge')
    def test_low_priority_does_not_spend(
        self, mock_firecrawl, mock_discovery, mock_db
    ):
        """Test that LOW priority disputes do not spend quota."""
        low_priority_dispute = DisputeContext.create(
            project_id="test-project",
            job_id="test-job",
            trigger_source_type=TriggerSourceType.RQ,
            trigger_source_id="rq-1",
            disagreement_summary="Test disagreement",
            priority=DisputePriority.LOW,
        )
        
        orchestrator = AugmentationOrchestrator(db=mock_db)
        result = orchestrator.run(low_priority_dispute)
        
        assert result.status == ReviewStatus.FAILED
        assert result.reason == "priority_gate_failed"
        
        # Verify Firecrawl was never called
        mock_firecrawl.return_value.scrape.assert_not_called()
    
    @patch('src.orchestrator.web.augmentation_orchestrator.WEB_AUGMENTATION_ENABLED', True)
    @patch('src.orchestrator.web.augmentation_orchestrator.can_spend')
    @patch('src.orchestrator.web.augmentation_orchestrator.WebDiscoveryService')
    @patch('src.orchestrator.web.augmentation_orchestrator.FirecrawlBridge')
    def test_manual_search_bypasses_priority_gate(
        self, mock_firecrawl, mock_discovery, mock_can_spend, mock_db, manual_search_dispute
    ):
        """Test that MANUAL_SEARCH bypasses priority gate (even with MEDIUM priority)."""
        mock_can_spend.return_value = True
        mock_discovery.return_value.discover.return_value = ["https://fda.gov/page1"]
        
        orchestrator = AugmentationOrchestrator(db=mock_db)
        result = orchestrator.run(manual_search_dispute)
        
        # Should proceed past priority gate (not fail with priority_gate_failed)
        # May fail for other reasons (no URLs, etc.) but not priority
        assert result.reason != "priority_gate_failed"
    
    @patch('src.orchestrator.web.augmentation_orchestrator.WEB_AUGMENTATION_ENABLED', True)
    @patch('src.orchestrator.web.augmentation_orchestrator.can_spend')
    @patch('src.orchestrator.web.augmentation_orchestrator.record_spend')
    @patch('src.orchestrator.web.augmentation_orchestrator.WebDiscoveryService')
    @patch('src.orchestrator.web.augmentation_orchestrator.FirecrawlBridge')
    def test_quota_counts_failed_requests(
        self, mock_firecrawl, mock_discovery, mock_record_spend, mock_can_spend, mock_db, high_priority_dispute
    ):
        """Test that quota counts both successful and failed requests."""
        mock_can_spend.return_value = True
        mock_discovery.return_value.discover.return_value = ["https://fda.gov/page1", "https://fda.gov/page2"]
        mock_firecrawl.return_value.scrape.return_value = [
            {"url": "https://fda.gov/page1", "markdown": "# Content", "error": None},
            {"url": "https://fda.gov/page2", "markdown": "", "error": "Connection error", "error_type": "connection_error"},
        ]
        
        orchestrator = AugmentationOrchestrator(db=mock_db)
        orchestrator.run(high_priority_dispute)
        
        # Verify record_spend was called with 2 (both successful and failed count)
        mock_record_spend.assert_called_once_with(mock_db, n=2)

