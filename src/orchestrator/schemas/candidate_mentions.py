"""
CandidateMentions schema for Project Vyasa.

CandidateMentions are Tier-A artifacts (cheap recall) that identify potential
entity mentions in documents before expensive Tier-B triple extraction.

Pass 1 (Tier A) outputs CandidateMentions, never triples.
Pass 2 (Tier B) consumes CandidateMentions to build EvidencePacks and extract triples.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CandidateMention(BaseModel):
    """A single candidate entity mention found in a document."""
    mention_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique mention identifier")
    entity_type: str = Field(..., description="Entity type (e.g., 'Vulnerability', 'Mechanism', 'Constraint', 'Outcome')")
    mention_text: str = Field(..., description="The actual text mention")
    chunk_id: str = Field(..., description="Chunk ID where this mention was found")
    page_number: Optional[int] = Field(None, description="Page number (1-based)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    section_label: Optional[str] = Field(None, description="Section label or heading if available")
    detection_method: str = Field(..., description="How this mention was detected (e.g., 'keyword', 'regex', 'embedding', 'toc_guided')")
    context_snippet: Optional[str] = Field(None, description="Surrounding context text for the mention")


class CandidateMentions(BaseModel):
    """Collection of candidate mentions for a project/ingestion.
    
    This is a Tier-A artifact (cheap recall) that identifies potential entity
    mentions before expensive Tier-B triple extraction.
    """
    # Identifiers
    mentions_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique collection identifier")
    project_id: str = Field(..., description="Project identifier")
    ingestion_id: str = Field(..., description="Ingestion identifier (required for evidence scoping)")
    
    # Timestamp
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO timestamp of creation")
    
    # Mentions grouped by entity_type
    mentions: List[CandidateMention] = Field(
        default_factory=list,
        description="List of candidate mentions (grouped by entity_type in Pass 2)"
    )
    
    # Metadata
    detection_methods_used: List[str] = Field(
        default_factory=list,
        description="List of detection methods used (e.g., ['keyword', 'regex', 'embedding', 'toc_guided'])"
    )
    total_mentions: int = Field(..., description="Total number of mentions in this collection")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z"
        }
    
    @classmethod
    def create(
        cls,
        project_id: str,
        ingestion_id: str,
        mentions: List[CandidateMention],
        detection_methods_used: Optional[List[str]] = None,
    ) -> "CandidateMentions":
        """Factory method to create a CandidateMentions collection."""
        return cls(
            project_id=project_id,
            ingestion_id=ingestion_id,
            mentions=mentions,
            detection_methods_used=detection_methods_used or [],
            total_mentions=len(mentions),
        )
