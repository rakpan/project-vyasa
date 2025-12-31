"""
Project Kernel Domain Models for Project Vyasa.

Defines Pydantic models for project configuration, intent, and scope.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ProjectCreate(BaseModel):
    """Payload for creating a new project (no ID or created_at)."""
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "title": "Security Analysis of Web Applications",
                "thesis": "Modern web applications are vulnerable to injection attacks...",
                "research_questions": [
                    "What are the most common injection vulnerabilities?",
                    "How effective are input validation mechanisms?"
                ],
                "anti_scope": ["Mobile applications", "Hardware security"],
                "target_journal": "IEEE Security & Privacy",
                "seed_files": ["paper1.pdf"]
            }
        }
    )
    
    title: str = Field(..., description="Project title")
    thesis: str = Field(..., description="The core argument or hypothesis")
    research_questions: List[str] = Field(default_factory=list, description="List of research questions")
    anti_scope: Optional[List[str]] = Field(None, description="Explicitly out-of-scope topics")
    target_journal: Optional[str] = Field(None, description="Target journal or venue for publication")
    seed_files: Optional[List[str]] = Field(default_factory=list, description="List of seed document filenames")


class ProjectConfig(BaseModel):
    """Complete project configuration with all metadata."""
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Security Analysis of Web Applications",
                "thesis": "Modern web applications are vulnerable to injection attacks...",
                "research_questions": [
                    "What are the most common injection vulnerabilities?",
                    "How effective are input validation mechanisms?"
                ],
                "anti_scope": ["Mobile applications", "Hardware security"],
                "target_journal": "IEEE Security & Privacy",
                "seed_files": ["paper1.pdf", "paper2.pdf"],
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    )
    
    id: str = Field(..., description="Unique project identifier (UUID)")
    title: str = Field(..., description="Project title")
    thesis: str = Field(..., description="The core argument or hypothesis")
    research_questions: List[str] = Field(default_factory=list, description="List of research questions")
    anti_scope: Optional[List[str]] = Field(None, description="Explicitly out-of-scope topics")
    target_journal: Optional[str] = Field(None, description="Target journal or venue for publication")
    seed_files: List[str] = Field(default_factory=list, description="List of seed document filenames")
    rigor_level: str = Field(default="exploratory", description="Rigor level for tone/precision policies")
    created_at: str = Field(..., description="Project creation timestamp (ISO format)")


class ProjectSummary(BaseModel):
    """Lightweight project summary for list views."""
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Security Analysis of Web Applications",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    )
    
    id: str = Field(..., description="Unique project identifier (UUID)")
    title: str = Field(..., description="Project title")
    created_at: str = Field(..., description="Project creation timestamp (ISO format)")
