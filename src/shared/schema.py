"""
PACT Ontology Schema for Project Vyasa

Defines Pydantic models for the PACT (Vulnerability, Mechanism, Constraint, Outcome) ontology.
All entities and relations are type-safe and validated.
"""

from enum import Enum
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict
import re


class RelationType(str, Enum):
    """Valid relation types in the PACT ontology."""
    MITIGATES = "MITIGATES"
    ENABLES = "ENABLES"
    REQUIRES = "REQUIRES"


class EntityType(str, Enum):
    """Valid entity types in the PACT ontology."""
    VULNERABILITY = "Vulnerability"
    MECHANISM = "Mechanism"
    CONSTRAINT = "Constraint"
    OUTCOME = "Outcome"


class Vulnerability(BaseModel):
    """Vulnerability entity in the PACT ontology."""
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "SQL Injection",
                "description": "Allows attackers to execute arbitrary SQL commands",
                "severity": "high",
                "category": "Injection"
            }
        }
    )
    
    id: Optional[str] = Field(None, alias="_id", description="ArangoDB document ID")
    key: Optional[str] = Field(None, alias="_key", description="ArangoDB document key")
    name: str = Field(..., description="Name of the vulnerability")
    description: str = Field(..., description="Detailed description of the vulnerability")
    severity: Optional[str] = Field(None, description="Severity level (e.g., 'high', 'medium', 'low')")
    category: Optional[str] = Field(None, description="Category or type of vulnerability")
    source: Optional[str] = Field(None, description="Source document or reference")


class Mechanism(BaseModel):
    """Mechanism entity in the PACT ontology."""
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Input Validation",
                "description": "Validates and sanitizes user inputs",
                "mechanism_type": "Defensive"
            }
        }
    )
    
    id: Optional[str] = Field(None, alias="_id", description="ArangoDB document ID")
    key: Optional[str] = Field(None, alias="_key", description="ArangoDB document key")
    name: str = Field(..., description="Name of the mechanism")
    description: str = Field(..., description="Detailed description of the mechanism")
    mechanism_type: Optional[str] = Field(None, description="Type of mechanism")
    source: Optional[str] = Field(None, description="Source document or reference")


class Constraint(BaseModel):
    """Constraint entity in the PACT ontology."""
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Resource Limit",
                "description": "Maximum memory allocation per process",
                "constraint_type": "Resource"
            }
        }
    )
    
    id: Optional[str] = Field(None, alias="_id", description="ArangoDB document ID")
    key: Optional[str] = Field(None, alias="_key", description="ArangoDB document key")
    name: str = Field(..., description="Name of the constraint")
    description: str = Field(..., description="Detailed description of the constraint")
    constraint_type: Optional[str] = Field(None, description="Type of constraint")
    source: Optional[str] = Field(None, description="Source document or reference")


class Outcome(BaseModel):
    """Outcome entity in the PACT ontology."""
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "System Compromise",
                "description": "Unauthorized access to system resources",
                "outcome_type": "negative"
            }
        }
    )
    
    id: Optional[str] = Field(None, alias="_id", description="ArangoDB document ID")
    key: Optional[str] = Field(None, alias="_key", description="ArangoDB document key")
    name: str = Field(..., description="Name of the outcome")
    description: str = Field(..., description="Detailed description of the outcome")
    outcome_type: Optional[str] = Field(None, description="Type of outcome (e.g., 'positive', 'negative')")
    source: Optional[str] = Field(None, description="Source document or reference")


# Union type for all entities
Entity = Vulnerability | Mechanism | Constraint | Outcome


class GraphTriple(BaseModel):
    """Represents a triple (subject, predicate, object) in the knowledge graph."""
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "subject": "Input Validation",
                "predicate": "MITIGATES",
                "object": "SQL Injection",
                "subject_type": "Mechanism",
                "object_type": "Vulnerability",
                "confidence": 0.95
            }
        }
    )
    subject: str = Field(..., description="Subject entity name or ID")
    predicate: RelationType = Field(..., description="Relation type")
    object: str = Field(..., description="Object entity name or ID")
    subject_type: EntityType = Field(..., description="Type of the subject entity")
    object_type: EntityType = Field(..., description="Type of the object entity")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")
    source: Optional[str] = Field(None, description="Source document or reference")
    
    @field_validator('predicate')
    @classmethod
    def validate_predicate(cls, v):
        """Ensure predicate is a valid RelationType."""
        if isinstance(v, str):
            try:
                return RelationType(v)
            except ValueError:
                raise ValueError(f"Invalid relation type: {v}. Must be one of {[r.value for r in RelationType]}")
        return v
    
    @field_validator('subject_type', 'object_type')
    @classmethod
    def validate_entity_type(cls, v):
        """Ensure entity type is valid."""
        if isinstance(v, str):
            try:
                return EntityType(v)
            except ValueError:
                raise ValueError(f"Invalid entity type: {v}. Must be one of {[e.value for e in EntityType]}")
        return v


class PACTGraph(BaseModel):
    """Complete PACT graph extraction result."""
    vulnerabilities: List[Vulnerability] = Field(default_factory=list, description="List of vulnerabilities")
    mechanisms: List[Mechanism] = Field(default_factory=list, description="List of mechanisms")
    constraints: List[Constraint] = Field(default_factory=list, description="List of constraints")
    outcomes: List[Outcome] = Field(default_factory=list, description="List of outcomes")
    triples: List[GraphTriple] = Field(default_factory=list, description="List of graph triples")
    source: Optional[str] = Field(None, description="Source document identifier")
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "vulnerabilities": [],
                "mechanisms": [],
                "constraints": [],
                "outcomes": [],
                "triples": []
            }
        }
    )


class RoleProfile(BaseModel):
    """Dynamic role configuration stored in the knowledge graph."""
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "The Cartographer",
                "description": "Extracts structured entities and relations from text",
                "system_prompt": "You are a PACT ontology extractor...",
                "version": 1,
                "allowed_tools": ["extract", "validate"],
                "focus_entities": ["Vulnerability", "Mechanism", "Constraint", "Outcome"],
                "is_enabled": True
            }
        }
    )
    
    id: Optional[str] = Field(None, alias="_id", description="ArangoDB document ID")
    key: Optional[str] = Field(None, alias="_key", description="ArangoDB document key")
    name: str = Field(..., description="Role name (e.g., 'The Cartographer', 'The Librarian')")
    description: str = Field(..., description="Human-readable description of the role's purpose")
    system_prompt: str = Field(..., description="The actual instruction block/prompt for this role")
    version: int = Field(default=1, description="Version number for role evolution")
    allowed_tools: List[str] = Field(default_factory=list, description="List of tool names this role can use")
    focus_entities: List[str] = Field(default_factory=list, description="Entity types this role focuses on")
    is_enabled: bool = Field(default=True, description="Whether this role is enabled")
    created_at: Optional[str] = Field(None, description="ISO timestamp when role was created")
    updated_at: Optional[str] = Field(None, description="ISO timestamp when role was last updated")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is non-empty and trimmed."""
        if not v or not v.strip():
            raise ValueError("Role name must be non-empty")
        return v.strip()
    
    @field_validator('system_prompt')
    @classmethod
    def validate_system_prompt(cls, v: str) -> str:
        """Validate system_prompt is non-empty."""
        if not v or not v.strip():
            raise ValueError("System prompt must be non-empty")
        return v.strip()
    
    @field_validator('version')
    @classmethod
    def validate_version(cls, v: int) -> int:
        """Validate version is >= 1."""
        if v < 1:
            raise ValueError("Version must be >= 1")
        return v
    
    def role_key(self) -> str:
        """
        Generate a stable database key for this role.
        
        Returns:
            Key in format: "{slug(name)}_v{version}"
        """
        # Slug: replace spaces with underscores, remove unsafe chars, lowercase
        slug = re.sub(r'[^a-zA-Z0-9_-]', '', self.name.lower().replace(' ', '_'))
        return f"{slug}_v{self.version}"
