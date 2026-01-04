"""
DisputeContext schema for Web Augmentation workflows.

Tracks disputes/conflicts that trigger web augmentation searches,
aligning with Vyasa's evidence-binding philosophy.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class TriggerSourceType(str, Enum):
    """Source type that triggered the dispute."""
    RQ = "RQ"  # Research Question
    BLOCK = "BLOCK"  # Manuscript Block
    CLAIM = "CLAIM"  # Individual Claim


class DisputePriority(str, Enum):
    """Priority level for dispute resolution."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DisputeContext(BaseModel):
    """Context for a dispute that triggers web augmentation.
    
    Represents a disagreement, gap, or conflict that requires
    external evidence gathering via web augmentation.
    """
    
    dispute_id: str = Field(
        ...,
        description="Unique dispute identifier (UUID)"
    )
    project_id: str = Field(
        ...,
        description="Project identifier"
    )
    job_id: str = Field(
        ...,
        description="Job identifier"
    )
    trigger_source_type: TriggerSourceType = Field(
        ...,
        description="Type of source that triggered the dispute"
    )
    trigger_source_id: str = Field(
        ...,
        description="Identifier of the triggering source (RQ ID, block ID, or claim ID)"
    )
    disagreement_summary: str = Field(
        ...,
        description="Human-readable summary of the disagreement or gap"
    )
    required_evidence_type: Optional[str] = Field(
        None,
        description="Type of evidence required (e.g., 'quantitative', 'methodological', 'empirical')"
    )
    priority: DisputePriority = Field(
        default=DisputePriority.MEDIUM,
        description="Priority level for resolution"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when dispute was created"
    )
    
    @field_validator("dispute_id")
    @classmethod
    def validate_dispute_id(cls, v: str) -> str:
        """Validate dispute_id is a valid UUID."""
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError(f"dispute_id must be a valid UUID, got: {v}")
        return v
    
    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        """Ensure created_at is timezone-aware."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    
    @classmethod
    def create(
        cls,
        project_id: str,
        job_id: str,
        trigger_source_type: TriggerSourceType,
        trigger_source_id: str,
        disagreement_summary: str,
        required_evidence_type: Optional[str] = None,
        priority: DisputePriority = DisputePriority.MEDIUM,
    ) -> "DisputeContext":
        """Create a new DisputeContext with generated UUID.
        
        Args:
            project_id: Project identifier
            job_id: Job identifier
            trigger_source_type: Type of triggering source
            trigger_source_id: Identifier of triggering source
            disagreement_summary: Summary of disagreement
            required_evidence_type: Optional evidence type requirement
            priority: Priority level (default: MEDIUM)
        
        Returns:
            DisputeContext instance with generated dispute_id
        """
        return cls(
            dispute_id=str(uuid.uuid4()),
            project_id=project_id,
            job_id=job_id,
            trigger_source_type=trigger_source_type,
            trigger_source_id=trigger_source_id,
            disagreement_summary=disagreement_summary,
            required_evidence_type=required_evidence_type,
            priority=priority,
            created_at=datetime.now(timezone.utc),
        )

