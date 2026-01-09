"""
Analytical Notes (Perspectives) schema for Project Vyasa.

Analytical Notes are user-authored perspectives, analogies, glossaries, and framing ideas.
They are NEVER directly citeable as evidence. They influence style and pedagogy only.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field


class NoteState(str, Enum):
    """State of an Analytical Note."""
    DRAFT = "Draft"
    MANUSCRIPT = "Manuscript"  # After cross-examination by Critic


class AnalyticalNote(BaseModel):
    """Analytical Note (Perspective): User-authored framing, never citeable.
    
    Analytical Notes are stored separately from Primary Sources (Evidence).
    They may influence style, analogies, and pedagogy, but all factual claims
    must come from Primary Sources (Evidence Packet A).
    
    Promotion: Draft Note → Manuscript Note (after Critic cross-examination).
    """
    
    # Identifiers
    note_id: str = Field(..., description="Unique note identifier (UUID)")
    project_id: str = Field(..., description="Project identifier")
    
    # Content
    text: str = Field(..., description="Note text content")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    
    # State and promotion
    state: NoteState = Field(default=NoteState.DRAFT, description="Note state (Draft or Manuscript)")
    
    # Linking
    linked_rq: Optional[str] = Field(None, description="Linked research question ID")
    source_ref: Optional[str] = Field(None, description="External source reference (not citeable)")
    
    # Metadata
    created_at: str = Field(..., description="ISO timestamp of note creation")
    updated_at: str = Field(..., description="ISO timestamp of last update")
    created_by: Optional[str] = Field(None, description="User identifier (if available)")
    
    # Critic cross-examination results
    critic_flags: List[str] = Field(default_factory=list, description="Flags from Critic cross-examination")
    promotion_reason: Optional[str] = Field(None, description="Reason for promotion (if Manuscript)")
    promoted_by_section_id: Optional[str] = Field(None, description="Section ID that triggered promotion")
    supporting_chunk_ids: List[str] = Field(default_factory=list, description="Chunk IDs from Packet A that support promotion")
    
    @classmethod
    def create(
        cls,
        text: str,
        project_id: str,
        tags: Optional[List[str]] = None,
        linked_rq: Optional[str] = None,
        source_ref: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> "AnalyticalNote":
        """Factory method to create an Analytical Note."""
        import uuid
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc).isoformat()
        
        return cls(
            note_id=str(uuid.uuid4()),
            project_id=project_id,
            text=text,
            tags=tags or [],
            state=NoteState.DRAFT,
            linked_rq=linked_rq,
            source_ref=source_ref,
            created_at=now,
            updated_at=now,
            created_by=created_by,
        )
