"""
Unit tests for AugmentationOrchestrator.

Tests the end-to-end web augmentation workflow with mocked services.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from src.orchestrator.web.augmentation_orchestrator import (
    AugmentationOrchestrator,
    _compute_domain_quality_score,
    _extract_claims_from_content,
    _triples_to_claims,
    _persist_review_task,
)
from src.orchestrator.schemas.disputes import DisputeContext, TriggerSourceType, DisputePriority
from src.orchestrator.schemas.review import ReviewTask, ReviewStatus
from src.orchestrator.schemas.claims import Claim


class TestDomainQualityScore:
    """Tests for domain quality scoring."""
    
    def test_edu_domain_high_score(self):
        """Test .edu domains get high score."""
        assert _compute_domain_quality_score("example.edu") == 0.9
    
    def test_gov_domain_high_score(self):
        """Test .gov domains get high score."""
        assert _compute_domain_quality_score("example.gov") == 0.9
    
    def test_org_domain_medium_high_score(self):
        """Test .org domains get medium-high score."""
        assert _compute_domain_quality_score("example.org") == 0.85
    
    def test_com_domain_medium_score(self):
        """Test .com domains get medium score."""
        assert _compute_domain_quality_score("example.com") == 0.7
    
    def test_net_domain_medium_score(self):
        """Test .net domains get medium score."""
        assert _compute_domain_quality_score("example.net") == 0.7
    
    def test_other_domain_low_score(self):
        """Test other domains get low score."""
        assert _compute_domain_quality_score("example.io") == 0.5


class TestTriplesToClaims:
    """Tests for triples to claims conversion."""
    
    def test_triples_to_claims_basic(self):
        """Test basic triple conversion."""
        triples = [
            {
                "subject": "Entity A",
                "predicate": "causes",
                "object": "Entity B",
                "confidence": 0.8,
                "evidence": "Some evidence text",
            }
        ]
        source_metadata = {"url": "https://example.com", "domain": "example.com"}
        
        claims = _triples_to_claims(triples, source_metadata)
        
        assert len(claims) == 1
        assert claims[0].subject == "Entity A"
        assert claims[0].predicate == "causes"
        assert claims[0].object == "Entity B"
        assert claims[0].confidence == 0.8
        assert "Some evidence text" in claims[0].claim_text  # Evidence included in claim_text
    
    def test_triples_to_claims_skips_invalid(self):
        """Test invalid triples are skipped."""
        triples = [
            {"subject": "A", "predicate": "rel", "object": "B"},  # Valid
            {"subject": "", "predicate": "rel", "object": "B"},  # Invalid (empty subject)
            {"subject": "A", "object": "B"},  # Invalid (missing predicate)
        ]
        
        claims = _triples_to_claims(triples, {})
        
        assert len(claims) == 1
        assert claims[0].subject == "A"


class TestAugmentationOrchestrator:
    """Tests for AugmentationOrchestrator."""
    
    @pytest.fixture
    def sample_dispute(self):
        """Create a sample DisputeContext."""
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
    def mock_discovery_service(self):
        """Create a mocked WebDiscoveryService."""
        service = Mock()
        service.discover.return_value = [
            "https://example.com/page1",
            "https://example.org/page2",
        ]
        return service
    
    @pytest.fixture
    def mock_firecrawl_bridge(self):
        """Create a mocked FirecrawlBridge."""
        bridge = Mock()
        bridge.scrape.return_value = [
            {
                "url": "https://example.com/page1",
                "domain": "example.com",
                "title": "Example Page 1",
                "markdown": "# Example Page 1\n\nThis is example content about quantum entanglement.",
                "retrieved_at": "2024-01-15T10:30:00Z",
                "error": None,
            },
            {
                "url": "https://example.org/page2",
                "domain": "example.org",
                "title": "Example Page 2",
                "markdown": "# Example Page 2\n\nMore content about quantum mechanics.",
                "retrieved_at": "2024-01-15T10:31:00Z",
                "error": None,
            },
        ]
        return bridge
    
    @pytest.fixture
    def mock_db(self):
        """Create a mocked ArangoDB database."""
        db = Mock()
        db.has_collection.return_value = True
        collection = Mock()
        db.collection.return_value = collection
        collection.insert.return_value = {"_key": "review-123"}
        return db
    
    @patch("src.orchestrator.web.augmentation_orchestrator.WEB_AUGMENTATION_ENABLED", True)
    @patch("src.orchestrator.web.augmentation_orchestrator._extract_claims_from_content")
    @patch("src.orchestrator.web.augmentation_orchestrator.EvidenceNormalizer")
    def test_run_full_pipeline(
        self,
        mock_normalizer,
        mock_extract,
        sample_dispute,
        mock_discovery_service,
        mock_firecrawl_bridge,
        mock_db,
    ):
        """Test full pipeline produces ReviewTask PENDING."""
        # Mock extraction to return triples
        mock_extract.return_value = (
            [
                {
                    "subject": "Quantum entanglement",
                    "predicate": "demonstrates",
                    "object": "non-local correlations",
                    "confidence": 0.9,
                    "evidence": "Experimental evidence shows...",
                }
            ],
            False,  # No fallback
            None,  # No error
        )
        
        # Mock normalizer
        from src.orchestrator.schemas.evidence import NormalizedEvidenceUnit, ProvenanceType
        
        mock_normalized_unit = NormalizedEvidenceUnit.create(
            content="# Example Page 1\n\nContent",
            provenance_type=ProvenanceType.WEB,
            provenance_metadata={"url": "https://example.com/page1", "domain": "example.com"},
        )
        mock_normalizer.normalize_web.return_value = mock_normalized_unit
        
        # Create orchestrator
        orchestrator = AugmentationOrchestrator(
            discovery_service=mock_discovery_service,
            firecrawl_bridge=mock_firecrawl_bridge,
            db=mock_db,
        )
        
        # Run
        review_task = orchestrator.run(sample_dispute)
        
        # Verify
        assert isinstance(review_task, ReviewTask)
        assert review_task.status == ReviewStatus.PENDING
        assert review_task.dispute_id == sample_dispute.dispute_id
        assert review_task.project_id == sample_dispute.project_id
        assert review_task.job_id == sample_dispute.job_id
        assert len(review_task.candidate_claims) > 0
        assert 0.0 <= review_task.source_quality_score <= 1.0
        
        # Verify services were called
        mock_discovery_service.discover.assert_called_once_with(sample_dispute)
        mock_firecrawl_bridge.scrape.assert_called_once()
        mock_db.collection.assert_called()
    
    @patch("src.orchestrator.web.augmentation_orchestrator.WEB_AUGMENTATION_ENABLED", False)
    def test_run_disabled_returns_failed(self, sample_dispute, mock_db):
        """Test that disabled feature returns FAILED ReviewTask."""
        orchestrator = AugmentationOrchestrator(db=mock_db)
        
        review_task = orchestrator.run(sample_dispute)
        
        assert review_task.status == ReviewStatus.FAILED
        assert len(review_task.candidate_claims) == 0
        assert review_task.source_quality_score == 0.0
    
    @patch("src.orchestrator.web.augmentation_orchestrator.WEB_AUGMENTATION_ENABLED", True)
    def test_run_no_urls_returns_failed(self, sample_dispute, mock_db):
        """Test that no URLs discovered returns FAILED ReviewTask."""
        mock_discovery = Mock()
        mock_discovery.discover.return_value = []  # No URLs
        
        orchestrator = AugmentationOrchestrator(
            discovery_service=mock_discovery,
            db=mock_db,
        )
        
        review_task = orchestrator.run(sample_dispute)
        
        assert review_task.status == ReviewStatus.FAILED
        assert len(review_task.candidate_claims) == 0
    
    @patch("src.orchestrator.web.augmentation_orchestrator.WEB_AUGMENTATION_ENABLED", True)
    def test_run_bounded_by_max_urls(self, sample_dispute, mock_discovery_service, mock_firecrawl_bridge, mock_db):
        """Test that URLs are bounded by WEB_MAX_URLS."""
        # Return many URLs
        mock_discovery_service.discover.return_value = [
            f"https://example.com/page{i}" for i in range(20)
        ]
        
        orchestrator = AugmentationOrchestrator(
            discovery_service=mock_discovery_service,
            firecrawl_bridge=mock_firecrawl_bridge,
            db=mock_db,
        )
        
        with patch("src.orchestrator.web.augmentation_orchestrator._extract_claims_from_content") as mock_extract:
            mock_extract.return_value = ([], False, None)
            
            review_task = orchestrator.run(sample_dispute)
            
            # Should only scrape up to WEB_MAX_URLS (default 10)
            assert mock_firecrawl_bridge.scrape.called
            call_args = mock_firecrawl_bridge.scrape.call_args[0][0]
            assert len(call_args) <= 10  # WEB_MAX_URLS default
    
    @patch("src.orchestrator.web.augmentation_orchestrator.WEB_AUGMENTATION_ENABLED", True)
    def test_run_bounded_by_max_pages(self, sample_dispute, mock_discovery_service, mock_firecrawl_bridge, mock_db):
        """Test that scraped pages are bounded by WEB_MAX_PAGES."""
        # Return many successful scrapes
        many_results = [
            {
                "url": f"https://example.com/page{i}",
                "domain": "example.com",
                "markdown": f"Content {i}",
                "error": None,
            }
            for i in range(30)
        ]
        mock_firecrawl_bridge.scrape.return_value = many_results
        
        orchestrator = AugmentationOrchestrator(
            discovery_service=mock_discovery_service,
            firecrawl_bridge=mock_firecrawl_bridge,
            db=mock_db,
        )
        
        with patch("src.orchestrator.web.augmentation_orchestrator._extract_claims_from_content") as mock_extract, \
             patch("src.orchestrator.web.augmentation_orchestrator.EvidenceNormalizer") as mock_normalizer:
            mock_extract.return_value = ([], False, None)
            
            from src.orchestrator.schemas.evidence import NormalizedEvidenceUnit, ProvenanceType
            
            def normalize_side_effect(item):
                return NormalizedEvidenceUnit.create(
                    content=item["markdown"],
                    provenance_type=ProvenanceType.WEB,
                    provenance_metadata={"url": item["url"], "domain": item["domain"]},
                )
            
            mock_normalizer.normalize_web.side_effect = normalize_side_effect
            
            review_task = orchestrator.run(sample_dispute)
            
            # Should only process up to WEB_MAX_PAGES (default 25)
            # Check that normalize_web was called at most WEB_MAX_PAGES times
            assert mock_normalizer.normalize_web.call_count <= 25


class TestPersistReviewTask:
    """Tests for ReviewTask persistence."""
    
    def test_persist_review_task_success(self):
        """Test successful ReviewTask persistence."""
        import uuid
        from unittest.mock import Mock
        
        mock_db = Mock()
        review_task = ReviewTask.create(
            project_id="p1",
            job_id="j1",
            dispute_id=str(uuid.uuid4()),
            candidate_claims=[],
            source_quality_score=0.8,
        )
        
        mock_db.has_collection.return_value = True
        collection = Mock()
        mock_db.collection.return_value = collection
        collection.insert.return_value = {"_key": review_task.review_id}
        
        result = _persist_review_task(mock_db, review_task)
        
        assert result is True
        collection.insert.assert_called_once()
        # Verify _key is set correctly
        call_args = collection.insert.call_args[0][0]
        assert call_args["_key"] == review_task.review_id
    
    def test_persist_review_task_creates_collection(self):
        """Test that collection is created if it doesn't exist."""
        import uuid
        from unittest.mock import Mock
        
        mock_db = Mock()
        review_task = ReviewTask.create(
            project_id="p1",
            job_id="j1",
            dispute_id=str(uuid.uuid4()),
            candidate_claims=[],
            source_quality_score=0.8,
        )
        
        mock_db.has_collection.return_value = False
        collection = Mock()
        mock_db.collection.return_value = collection
        collection.insert.return_value = {"_key": review_task.review_id}
        
        result = _persist_review_task(mock_db, review_task)
        
        assert result is True
        mock_db.create_collection.assert_called_once_with("review_tasks")
        collection.insert.assert_called_once()

