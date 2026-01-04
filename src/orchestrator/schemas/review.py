"""
ReviewTask schema for Web Augmentation workflows.

Represents a review task for evaluating candidate claims from web augmentation,
aligning with Vyasa's evidence-binding and governance philosophy.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator

from .claims import Claim


class ReviewStatus(str, Enum):
    """Status of a review task."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUEST_MORE = "REQUEST_MORE"
    FAILED = "FAILED"


class ReviewTask(BaseModel):
    """Review task for evaluating candidate claims from web augmentation.
    
    Tracks the review process for claims extracted from web sources,
    including quality scoring and approval workflow.
    """
    
    review_id: str = Field(
        ...,
        description="Unique review identifier (UUID)"
    )
    project_id: str = Field(
        ...,
        description="Project identifier"
    )
    job_id: str = Field(
        ...,
        description="Job identifier"
    )
    dispute_id: str = Field(
        ...,
        description="Dispute identifier that triggered this review"
    )
    candidate_claims: List[Claim] = Field(
        ...,
        description="Candidate claims extracted from web sources"
    )
    source_quality_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Quality score of the source (0.0 to 1.0)"
    )
    status: ReviewStatus = Field(
        default=ReviewStatus.PENDING,
        description="Current review status"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when review was created"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when review was last updated"
    )
    
    @field_validator("review_id")
    @classmethod
    def validate_review_id(cls, v: str) -> str:
        """Validate review_id is a valid UUID."""
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError(f"review_id must be a valid UUID, got: {v}")
        return v
    
    @field_validator("dispute_id")
    @classmethod
    def validate_dispute_id(cls, v: str) -> str:
        """Validate dispute_id is a valid UUID."""
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError(f"dispute_id must be a valid UUID, got: {v}")
        return v
    
    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, v: datetime) -> datetime:
        """Ensure timestamps are timezone-aware."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    
    @field_validator("updated_at")
    @classmethod
    def validate_updated_at_after_created_at(cls, v: datetime, info) -> datetime:
        """Ensure updated_at is not before created_at."""
        created_at = info.data.get("created_at") if hasattr(info, "data") else None
        if created_at and v < created_at:
            raise ValueError("updated_at must be >= created_at")
        return v
    
    @classmethod
    def create(
        cls,
        project_id: str,
        job_id: str,
        dispute_id: str,
        candidate_claims: List[Claim],
        source_quality_score: float,
        status: ReviewStatus = ReviewStatus.PENDING,
    ) -> "ReviewTask":
        """Create a new ReviewTask with generated UUID.
        
        Args:
            project_id: Project identifier
            job_id: Job identifier
            dispute_id: Dispute identifier
            candidate_claims: List of candidate claims
            source_quality_score: Quality score of source (0.0 to 1.0)
            status: Initial review status (default: PENDING)
        
        Returns:
            ReviewTask instance with generated review_id
        """
        now = datetime.now(timezone.utc)
        return cls(
            review_id=str(uuid.uuid4()),
            project_id=project_id,
            job_id=job_id,
            dispute_id=dispute_id,
            candidate_claims=candidate_claims,
            source_quality_score=source_quality_score,
            status=status,
            created_at=now,
            updated_at=now,
        )
    
    def update_status(self, new_status: ReviewStatus) -> "ReviewTask":
        """Update review status and timestamp.
        
        Args:
            new_status: New review status
        
        Returns:
            New ReviewTask instance with updated status and updated_at
        """
        data = self.model_dump()
        data["status"] = new_status
        data["updated_at"] = datetime.now(timezone.utc)
        return self.__class__(**data)

