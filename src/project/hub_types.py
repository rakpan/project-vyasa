"""
Project Hub-specific types for grouping, filtering, and summary views.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class ManifestSummary(BaseModel):
    """Lightweight manifest summary for hub display."""
    
    words: int = Field(default=0, description="Total word count")
    claims: int = Field(default=0, description="Total claim count")
    density: float = Field(default=0.0, description="Claims per 100 words")
    citations: int = Field(default=0, description="Total citation count")
    tables: int = Field(default=0, description="Total table count")
    figures: int = Field(default=0, description="Total figure count")
    flags_count_by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of flags grouped by type (e.g., {'tone': 3, 'precision': 1})"
    )


class ProjectHubSummary(BaseModel):
    """Hub-friendly project summary with status, flags, and manifest metrics."""
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Security Analysis of Web Applications",
                "tags": ["security", "web"],
                "rigor_level": "exploratory",
                "last_updated": "2024-01-15T10:30:00Z",
                "status": "Idle",
                "open_flags_count": 2,
                "manifest_summary": {
                    "words": 5000,
                    "claims": 150,
                    "density": 3.0,
                    "citations": 25,
                    "tables": 3,
                    "figures": 2,
                    "flags_count_by_type": {"tone": 1, "precision": 1}
                }
            }
        }
    )
    
    project_id: str = Field(..., description="Project UUID")
    title: str = Field(..., description="Project title")
    tags: List[str] = Field(default_factory=list, description="Project tags")
    rigor_level: str = Field(..., description="Rigor level: exploratory or conservative")
    last_updated: str = Field(..., description="Last update timestamp (ISO format)")
    status: Literal["Idle", "Processing", "AttentionNeeded"] = Field(
        ...,
        description="Derived project status based on latest job"
    )
    open_flags_count: int = Field(
        default=0,
        description="Count of open flags (failed ingests, conflicts, rejected blocks, etc.)"
    )
    manifest_summary: Optional[ManifestSummary] = Field(
        None,
        description="Manifest summary from latest successful job (optional)"
    )


class ProjectGrouping(BaseModel):
    """Grouped projects for hub display."""
    
    active_research: List[ProjectHubSummary] = Field(
        default_factory=list,
        description="Active research projects (recent activity or processing)"
    )
    archived_insights: List[ProjectHubSummary] = Field(
        default_factory=list,
        description="Archived insights (older or inactive projects)"
    )

