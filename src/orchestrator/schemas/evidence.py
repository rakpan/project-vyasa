"""
NormalizedEvidenceUnit schema for Web Augmentation workflows.

Represents evidence from web or PDF sources in a unified format,
supporting Vyasa's evidence-binding philosophy.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator, computed_field


class ProvenanceType(str, Enum):
    """Source provenance type for evidence."""
    WEB = "WEB"
    PDF = "PDF"


class NormalizedEvidenceUnit(BaseModel):
    """Normalized evidence unit from web or PDF sources.
    
    Provides a unified representation of evidence regardless of source,
    with content hashing for deduplication and provenance tracking.
    """
    
    id: str = Field(
        ...,
        description="Unique evidence identifier (UUID)"
    )
    content: str = Field(
        ...,
        description="Evidence content text"
    )
    content_hash: str = Field(
        ...,
        description="SHA256 hash of content for deduplication"
    )
    provenance_type: ProvenanceType = Field(
        ...,
        description="Source provenance type (WEB or PDF)"
    )
    provenance_metadata: Dict[str, Any] = Field(
        ...,
        description="Provenance metadata (must include URL for WEB, doc_hash for PDF)"
    )
    retrieval_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when evidence was retrieved"
    )
    
    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate id is a valid UUID."""
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError(f"id must be a valid UUID, got: {v}")
        return v
    
    @field_validator("content_hash")
    @classmethod
    def validate_content_hash(cls, v: str) -> str:
        """Validate content_hash is a 64-character hex string (SHA256)."""
        if not isinstance(v, str) or len(v) != 64:
            raise ValueError(f"content_hash must be a 64-character hex string (SHA256), got: {v}")
        try:
            int(v, 16)  # Validate hex
        except ValueError:
            raise ValueError(f"content_hash must be a valid hex string, got: {v}")
        return v
    
    @field_validator("provenance_metadata")
    @classmethod
    def validate_provenance_metadata(cls, v: Dict[str, Any], info) -> Dict[str, Any]:
        """Validate provenance_metadata includes required fields based on provenance_type."""
        provenance_type = info.data.get("provenance_type") if hasattr(info, "data") else None
        if provenance_type == ProvenanceType.WEB:
            if "url" not in v:
                raise ValueError("provenance_metadata must include 'url' for WEB provenance_type")
        elif provenance_type == ProvenanceType.PDF:
            if "doc_hash" not in v:
                raise ValueError("provenance_metadata must include 'doc_hash' for PDF provenance_type")
        return v
    
    @field_validator("retrieval_timestamp")
    @classmethod
    def validate_retrieval_timestamp(cls, v: datetime) -> datetime:
        """Ensure retrieval_timestamp is timezone-aware."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    
    @classmethod
    def compute_content_hash(cls, content: str) -> str:
        """Compute SHA256 hash of content.
        
        Args:
            content: Content text to hash
        
        Returns:
            64-character hex string (SHA256 hash)
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    
    @classmethod
    def create(
        cls,
        content: str,
        provenance_type: ProvenanceType,
        provenance_metadata: Dict[str, Any],
        retrieval_timestamp: Optional[datetime] = None,
    ) -> "NormalizedEvidenceUnit":
        """Create a new NormalizedEvidenceUnit with computed hash.
        
        Args:
            content: Evidence content text
            provenance_type: Source provenance type
            provenance_metadata: Provenance metadata (must include URL for WEB, doc_hash for PDF)
            retrieval_timestamp: Optional retrieval timestamp (defaults to now)
        
        Returns:
            NormalizedEvidenceUnit instance with generated id and computed content_hash
        """
        content_hash = cls.compute_content_hash(content)
        return cls(
            id=str(uuid.uuid4()),
            content=content,
            content_hash=content_hash,
            provenance_type=provenance_type,
            provenance_metadata=provenance_metadata,
            retrieval_timestamp=retrieval_timestamp or datetime.now(timezone.utc),
        )

