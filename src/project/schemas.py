"""
Project Kernel Domain Models for Project Vyasa.

Defines Pydantic models for project configuration, intent, and scope.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
import uuid


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
    title: str = Field(..., min_length=1, description="Project title")
    thesis: str = Field(..., min_length=1, description="The core argument or hypothesis")
    research_questions: List[str] = Field(default_factory=list, description="List of research questions")
    anti_scope: Optional[List[str]] = Field(None, description="Explicitly out-of-scope topics")
    target_journal: Optional[str] = Field(None, description="Target journal or venue for publication")
    seed_files: List[str] = Field(default_factory=list, description="List of seed document filenames")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Project creation timestamp")
    
    def model_dump_for_db(self) -> dict:
        """Convert to dictionary suitable for ArangoDB storage.
        
        Converts datetime to ISO string and excludes None values.
        
        Returns:
            Dictionary ready for ArangoDB insertion.
        """
        data = self.model_dump(exclude_none=True)
        # Convert datetime to ISO string
        if isinstance(data.get("created_at"), datetime):
            data["created_at"] = data["created_at"].isoformat()
        return data


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
    
    title: str = Field(..., min_length=1, description="Project title")
    thesis: str = Field(..., min_length=1, description="The core argument or hypothesis")
    research_questions: List[str] = Field(default_factory=list, description="List of research questions")
    anti_scope: Optional[List[str]] = Field(None, description="Explicitly out-of-scope topics")
    target_journal: Optional[str] = Field(None, description="Target journal or venue for publication")
    seed_files: List[str] = Field(default_factory=list, description="List of seed document filenames")
    
    def to_config(self) -> ProjectConfig:
        """Convert to ProjectConfig with generated ID and timestamp.
        
        Returns:
            ProjectConfig instance with id and created_at populated.
        """
        return ProjectConfig(
            id=str(uuid.uuid4()),
            title=self.title,
            thesis=self.thesis,
            research_questions=self.research_questions,
            anti_scope=self.anti_scope,
            target_journal=self.target_journal,
            seed_files=self.seed_files,
            created_at=datetime.utcnow()
        )


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
    created_at: datetime = Field(..., description="Project creation timestamp")
    
    @classmethod
    def from_config(cls, config: ProjectConfig) -> "ProjectSummary":
        """Create a ProjectSummary from a ProjectConfig.
        
        Args:
            config: Full ProjectConfig instance.
            
        Returns:
            ProjectSummary with only id, title, and created_at.
        """
        return cls(
            id=config.id,
            title=config.title,
            created_at=config.created_at
        )

