"""
Manuscript Blueprint schema for Project Vyasa.

The Blueprint Engine governs manuscript synthesis by defining sections,
linked RQs, evidence clusters, depth intent, and visual anchors.
"""
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field


class JournalSlot(str, Enum):
    """Journal section slots."""
    INTRODUCTION = "introduction"
    METHODS = "methods"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"
    ABSTRACT = "abstract"
    BACKGROUND = "background"
    RELATED_WORK = "related_work"


class DepthIntent(str, Enum):
    """Depth intent for section synthesis."""
    HOOK = "hook"  # Attention-grabbing opening
    PROOF = "proof"  # Detailed evidence and citations
    SO_WHAT = "so_what"  # Interpretation and implications


class VisualAnchor(BaseModel):
    """Visual anchor specification for tables/figures."""
    anchor_id: str = Field(..., description="Unique anchor identifier")
    anchor_type: str = Field(..., description="Type: 'table', 'figure', 'equation'")
    placeholder_text: str = Field(..., description="Placeholder text for manual completion")
    candidate_evidence_cluster_ids: List[str] = Field(
        default_factory=list,
        description="Evidence cluster IDs that could fill this anchor"
    )
    auto_generate: bool = Field(default=False, description="Whether to auto-generate from evidence")


class BlueprintSection(BaseModel):
    """A section in the manuscript blueprint."""
    section_id: str = Field(..., description="Unique section identifier")
    heading: str = Field(..., description="Section heading")
    journal_slot: JournalSlot = Field(..., description="Journal section slot")
    linked_rqs: List[str] = Field(default_factory=list, description="Research question IDs linked to this section")
    evidence_cluster_ids: List[str] = Field(
        default_factory=list,
        description="Evidence cluster IDs for this section"
    )
    depth_intent: DepthIntent = Field(default=DepthIntent.PROOF, description="Depth intent for synthesis")
    visual_anchors: List[VisualAnchor] = Field(
        default_factory=list,
        description="Visual anchors (tables/figures) for this section"
    )
    conclusion_rules: Optional[str] = Field(None, description="Rules for section conclusion")


class ManuscriptBlueprint(BaseModel):
    """Manuscript Blueprint: Governor for section-driven synthesis.
    
    The blueprint defines the structure and constraints for manuscript generation.
    Each section is synthesized using:
    - Evidence Packet A (Primary Sources from reranked retrieval)
    - Perspective Packet B (Analytical Notes, style influence only)
    - Blueprint metadata (depth_intent, visual_anchors, etc.)
    """
    
    # Identifiers
    blueprint_id: str = Field(..., description="Unique blueprint identifier (UUID)")
    project_id: str = Field(..., description="Project identifier")
    
    # Structure
    sections: List[BlueprintSection] = Field(default_factory=list, description="Blueprint sections")
    
    # Metadata
    target_journal: Optional[str] = Field(None, description="Target journal profile")
    created_at: str = Field(..., description="ISO timestamp of blueprint creation")
    updated_at: str = Field(..., description="ISO timestamp of last update")
    version: int = Field(default=1, description="Blueprint version")
    
    @classmethod
    def create(
        cls,
        project_id: str,
        sections: Optional[List[BlueprintSection]] = None,
        target_journal: Optional[str] = None,
    ) -> "ManuscriptBlueprint":
        """Factory method to create a Manuscript Blueprint."""
        import uuid
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc).isoformat()
        
        return cls(
            blueprint_id=str(uuid.uuid4()),
            project_id=project_id,
            sections=sections or [],
            target_journal=target_journal,
            created_at=now,
            updated_at=now,
            version=1,
        )
