"""
Unit tests for Web Augmentation schemas.

Tests DisputeContext, NormalizedEvidenceUnit, and ReviewTask schemas
for validation, serialization, and helper methods.
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from src.orchestrator.schemas.disputes import (
    DisputeContext,
    TriggerSourceType,
    DisputePriority,
)
from src.orchestrator.schemas.evidence import (
    NormalizedEvidenceUnit,
    ProvenanceType,
)
from src.orchestrator.schemas.review import (
    ReviewTask,
    ReviewStatus,
)
from src.orchestrator.schemas.claims import Claim, SourceAnchor


class TestDisputeContext:
    """Tests for DisputeContext schema."""
    
    def test_create_dispute_context(self):
        """Test creating a DisputeContext with helper method."""
        dispute = DisputeContext.create(
            project_id="project-123",
            job_id="job-456",
            trigger_source_type=TriggerSourceType.RQ,
            trigger_source_id="rq-789",
            disagreement_summary="Conflicting evidence found",
            required_evidence_type="quantitative",
            priority=DisputePriority.HIGH,
        )
        
        assert dispute.project_id == "project-123"
        assert dispute.job_id == "job-456"
        assert dispute.trigger_source_type == TriggerSourceType.RQ
        assert dispute.trigger_source_id == "rq-789"
        assert dispute.disagreement_summary == "Conflicting evidence found"
        assert dispute.required_evidence_type == "quantitative"
        assert dispute.priority == DisputePriority.HIGH
        assert dispute.dispute_id is not None
        assert isinstance(dispute.created_at, datetime)
        assert dispute.created_at.tzinfo is not None
    
    def test_dispute_context_round_trip(self):
        """Test schema round-trip serialization."""
        dispute = DisputeContext.create(
            project_id="project-123",
            job_id="job-456",
            trigger_source_type=TriggerSourceType.CLAIM,
            trigger_source_id="claim-abc",
            disagreement_summary="Test dispute",
        )
        
        # Serialize to dict
        data = dispute.model_dump()
        
        # Deserialize from dict
        dispute2 = DisputeContext(**data)
        
        assert dispute2.dispute_id == dispute.dispute_id
        assert dispute2.project_id == dispute.project_id
        assert dispute2.trigger_source_type == dispute.trigger_source_type
    
    def test_dispute_context_invalid_uuid(self):
        """Test validation rejects invalid UUID."""
        with pytest.raises(ValidationError) as exc_info:
            DisputeContext(
                dispute_id="not-a-uuid",
                project_id="project-123",
                job_id="job-456",
                trigger_source_type=TriggerSourceType.RQ,
                trigger_source_id="rq-789",
                disagreement_summary="Test",
            )
        
        assert "dispute_id must be a valid UUID" in str(exc_info.value)
    
    def test_dispute_context_required_fields(self):
        """Test required fields are enforced."""
        with pytest.raises(ValidationError):
            DisputeContext(
                dispute_id="123e4567-e89b-12d3-a456-426614174000",
                # Missing required fields
            )


class TestNormalizedEvidenceUnit:
    """Tests for NormalizedEvidenceUnit schema."""
    
    def test_create_evidence_unit_web(self):
        """Test creating a NormalizedEvidenceUnit from web source."""
        evidence = NormalizedEvidenceUnit.create(
            content="Evidence text from web",
            provenance_type=ProvenanceType.WEB,
            provenance_metadata={"url": "https://example.com/article"},
        )
        
        assert evidence.content == "Evidence text from web"
        assert evidence.provenance_type == ProvenanceType.WEB
        assert evidence.provenance_metadata["url"] == "https://example.com/article"
        assert evidence.id is not None
        assert len(evidence.content_hash) == 64  # SHA256 hex length
        assert isinstance(evidence.retrieval_timestamp, datetime)
        assert evidence.retrieval_timestamp.tzinfo is not None
    
    def test_create_evidence_unit_pdf(self):
        """Test creating a NormalizedEvidenceUnit from PDF source."""
        evidence = NormalizedEvidenceUnit.create(
            content="Evidence text from PDF",
            provenance_type=ProvenanceType.PDF,
            provenance_metadata={"doc_hash": "abc123", "page": 5},
        )
        
        assert evidence.provenance_type == ProvenanceType.PDF
        assert evidence.provenance_metadata["doc_hash"] == "abc123"
        assert evidence.provenance_metadata["page"] == 5
    
    def test_content_hash_computation(self):
        """Test content_hash is computed correctly."""
        content = "Test evidence content"
        hash1 = NormalizedEvidenceUnit.compute_content_hash(content)
        hash2 = NormalizedEvidenceUnit.compute_content_hash(content)
        
        # Same content should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length
        
        # Different content should produce different hash
        hash3 = NormalizedEvidenceUnit.compute_content_hash("Different content")
        assert hash3 != hash1
    
    def test_evidence_unit_round_trip(self):
        """Test schema round-trip serialization."""
        evidence = NormalizedEvidenceUnit.create(
            content="Test evidence",
            provenance_type=ProvenanceType.WEB,
            provenance_metadata={"url": "https://example.com"},
        )
        
        # Serialize to dict
        data = evidence.model_dump()
        
        # Deserialize from dict
        evidence2 = NormalizedEvidenceUnit(**data)
        
        assert evidence2.id == evidence.id
        assert evidence2.content == evidence.content
        assert evidence2.content_hash == evidence.content_hash
    
    def test_evidence_unit_web_requires_url(self):
        """Test WEB provenance requires URL in metadata."""
        with pytest.raises(ValidationError) as exc_info:
            NormalizedEvidenceUnit.create(
                content="Test",
                provenance_type=ProvenanceType.WEB,
                provenance_metadata={},  # Missing URL
            )
        
        assert "url" in str(exc_info.value).lower()
    
    def test_evidence_unit_pdf_requires_doc_hash(self):
        """Test PDF provenance requires doc_hash in metadata."""
        with pytest.raises(ValidationError) as exc_info:
            NormalizedEvidenceUnit.create(
                content="Test",
                provenance_type=ProvenanceType.PDF,
                provenance_metadata={},  # Missing doc_hash
            )
        
        assert "doc_hash" in str(exc_info.value).lower()
    
    def test_evidence_unit_invalid_hash(self):
        """Test validation rejects invalid content_hash."""
        with pytest.raises(ValidationError) as exc_info:
            NormalizedEvidenceUnit(
                id="123e4567-e89b-12d3-a456-426614174000",
                content="Test",
                content_hash="invalid-hash",  # Not 64 chars
                provenance_type=ProvenanceType.WEB,
                provenance_metadata={"url": "https://example.com"},
            )
        
        assert "content_hash" in str(exc_info.value)


class TestReviewTask:
    """Tests for ReviewTask schema."""
    
    @pytest.fixture
    def sample_claim(self):
        """Create a sample claim for testing."""
        return Claim(
            claim_id="claim-123",
            subject="Entity",
            predicate="has_property",
            object="Value",
            confidence=0.8,
            rq_hits=["rq-1"],
            ingestion_id="ingestion-1",
            file_hash="abc123",
        )
    
    def test_create_review_task(self, sample_claim):
        """Test creating a ReviewTask with helper method."""
        dispute_id = "123e4567-e89b-12d3-a456-426614174000"
        task = ReviewTask.create(
            project_id="project-123",
            job_id="job-456",
            dispute_id=dispute_id,
            candidate_claims=[sample_claim],
            source_quality_score=0.85,
            status=ReviewStatus.PENDING,
        )
        
        assert task.project_id == "project-123"
        assert task.job_id == "job-456"
        assert task.dispute_id == dispute_id
        assert len(task.candidate_claims) == 1
        assert task.candidate_claims[0].claim_id == "claim-123"
        assert task.source_quality_score == 0.85
        assert task.status == ReviewStatus.PENDING
        assert task.review_id is not None
        assert isinstance(task.created_at, datetime)
        assert isinstance(task.updated_at, datetime)
        assert task.updated_at >= task.created_at
    
    def test_review_task_round_trip(self, sample_claim):
        """Test schema round-trip serialization."""
        dispute_id = "123e4567-e89b-12d3-a456-426614174000"
        task = ReviewTask.create(
            project_id="project-123",
            job_id="job-456",
            dispute_id=dispute_id,
            candidate_claims=[sample_claim],
            source_quality_score=0.9,
        )
        
        # Serialize to dict
        data = task.model_dump()
        
        # Deserialize from dict
        task2 = ReviewTask(**data)
        
        assert task2.review_id == task.review_id
        assert task2.project_id == task.project_id
        assert len(task2.candidate_claims) == 1
        assert task2.candidate_claims[0].claim_id == sample_claim.claim_id
    
    def test_review_task_update_status(self, sample_claim):
        """Test updating review task status."""
        dispute_id = "123e4567-e89b-12d3-a456-426614174000"
        task = ReviewTask.create(
            project_id="project-123",
            job_id="job-456",
            dispute_id=dispute_id,
            candidate_claims=[sample_claim],
            source_quality_score=0.8,
        )
        
        original_updated_at = task.updated_at
        
        # Update status
        task2 = task.update_status(ReviewStatus.APPROVED)
        
        assert task2.status == ReviewStatus.APPROVED
        assert task2.updated_at > original_updated_at
        assert task2.review_id == task.review_id
    
    def test_review_task_invalid_uuid(self, sample_claim):
        """Test validation rejects invalid UUID."""
        with pytest.raises(ValidationError) as exc_info:
            ReviewTask(
                review_id="not-a-uuid",
                project_id="project-123",
                job_id="job-456",
                dispute_id="dispute-789",
                candidate_claims=[sample_claim],
                source_quality_score=0.8,
            )
        
        assert "review_id must be a valid UUID" in str(exc_info.value)
    
    def test_review_task_quality_score_bounds(self, sample_claim):
        """Test quality score must be between 0.0 and 1.0."""
        dispute_id = "123e4567-e89b-12d3-a456-426614174000"
        # Valid score
        task = ReviewTask.create(
            project_id="project-123",
            job_id="job-456",
            dispute_id=dispute_id,
            candidate_claims=[sample_claim],
            source_quality_score=0.5,
        )
        assert task.source_quality_score == 0.5
        
        # Invalid: too high
        with pytest.raises(ValidationError):
            ReviewTask.create(
                project_id="project-123",
                job_id="job-456",
                dispute_id=dispute_id,
                candidate_claims=[sample_claim],
                source_quality_score=1.5,  # > 1.0
            )
        
        # Invalid: too low
        with pytest.raises(ValidationError):
            ReviewTask.create(
                project_id="project-123",
                job_id="job-456",
                dispute_id=dispute_id,
                candidate_claims=[sample_claim],
                source_quality_score=-0.1,  # < 0.0
            )
    
    def test_review_task_required_fields(self):
        """Test required fields are enforced."""
        with pytest.raises(ValidationError):
            ReviewTask(
                review_id="123e4567-e89b-12d3-a456-426614174000",
                # Missing required fields
            )

