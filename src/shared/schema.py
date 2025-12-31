"""
Knowledge Graph Schema for Project Vyasa

Defines Pydantic models for the knowledge graph (Vulnerability, Mechanism, Constraint, Outcome entities).
All entities and relations are type-safe and validated.
"""

from enum import Enum
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
import re


class RelationType(str, Enum):
    """Valid relation types in the knowledge graph."""
    MITIGATES = "MITIGATES"
    ENABLES = "ENABLES"
    REQUIRES = "REQUIRES"


class EntityType(str, Enum):
    """Valid entity types in the knowledge graph."""
    VULNERABILITY = "Vulnerability"
    MECHANISM = "Mechanism"
    CONSTRAINT = "Constraint"
    OUTCOME = "Outcome"


class Vulnerability(BaseModel):
    """Vulnerability entity in the knowledge graph."""
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
    """Mechanism entity in the knowledge graph."""
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
    """Constraint entity in the knowledge graph."""
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
    """Outcome entity in the knowledge graph."""
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
    project_id: str = Field(..., description="Project ID this triple belongs to")
    doc_hash: str = Field(..., description="Source document hash (SHA256)")
    source_pointer: "SourcePointer" = Field(..., description="Required pointer to source text/evidence")
    is_expert_verified: bool = Field(default=False, description="Whether an expert has verified this triple")
    expert_notes: Optional[str] = Field(default=None, description="Optional notes from expert review")
    
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


class KnowledgeGraph(BaseModel):
    """Complete knowledge graph extraction result."""
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


class SourcePointer(BaseModel):
    """Pointer back to source text for evidence binding."""
    doc_hash: str = Field(..., description="sha256 or similar content hash of the source document")
    page: int = Field(..., ge=1, description="1-based page number")
    bbox: List[float] = Field(..., min_length=4, max_length=4, description="Normalized [x1,y1,x2,y2] (0-1000 scale)")
    snippet: str = Field(..., description="Exact text excerpt from the source")

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: List[float]) -> List[float]:
        if len(v) != 4:
            raise ValueError("bbox must have exactly 4 values [x1,y1,x2,y2]")
        for coord in v:
            if coord < 0 or coord > 1000:
                raise ValueError("bbox coordinates must be normalized to 0-1000")
        return v


class Claim(BaseModel):
    """Claim with evidence binding back to the source."""
    text: str
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source_pointer: SourcePointer
    project_id: str = Field(..., description="Project ID for this claim")
    doc_hash: str = Field(..., description="Source document hash")
    is_expert_verified: bool = False


class ProvenanceEntry(BaseModel):
    """Entry in the provenance log tracking where knowledge came from."""
    project_id: str = Field(..., description="Project ID that contributed this knowledge")
    job_id: str = Field(..., description="Job ID that contributed this knowledge")
    contributed_at: str = Field(..., description="ISO timestamp when this knowledge was contributed")
    source_pointer: SourcePointer = Field(..., description="Source pointer from the original extraction")


class CanonicalKnowledge(BaseModel):
    """Canonical knowledge entry in the global repository.
    
    This represents expert-vetted, merged knowledge that has been synthesized
    from multiple projects and jobs. Every entry tracks its provenance.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "entity_id": "plc_security",
                "entity_name": "Programmable Logic Controller Security",
                "entity_type": "Vulnerability",
                "description": "Security vulnerabilities in PLC systems",
                "source_pointers": [
                    {
                        "doc_hash": "sha256:...",
                        "page": 1,
                        "bbox": [100, 200, 300, 400],
                        "snippet": "PLC systems are vulnerable to..."
                    }
                ],
                "provenance_log": [
                    {
                        "project_id": "proj-123",
                        "job_id": "job-456",
                        "contributed_at": "2024-01-15T10:30:00Z",
                        "source_pointer": {...}
                    }
                ],
                "conflict_flags": [],
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z"
            }
        }
    )
    
    id: Optional[str] = Field(None, alias="_id", description="ArangoDB document ID")
    key: Optional[str] = Field(None, alias="_key", description="ArangoDB document key")
    
    # Entity/Relationship identification
    entity_id: str = Field(..., description="Unique identifier for this entity/relationship")
    entity_name: str = Field(..., description="Canonical name of the entity/relationship")
    entity_type: EntityType = Field(..., description="Type of entity (Vulnerability, Mechanism, etc.)")
    
    # For relationships (triples)
    subject: Optional[str] = Field(None, description="Subject entity (for relationships)")
    predicate: Optional[RelationType] = Field(None, description="Predicate (for relationships)")
    object: Optional[str] = Field(None, description="Object entity (for relationships)")
    
    # Content
    description: Optional[str] = Field(None, description="Description or summary of the knowledge")
    source_pointers: List[SourcePointer] = Field(default_factory=list, description="All source pointers from contributing projects")
    
    # Provenance tracking
    provenance_log: List[ProvenanceEntry] = Field(default_factory=list, description="List of projects/jobs that contributed")
    
    # Conflict management
    conflict_flags: List[str] = Field(default_factory=list, description="Flags for contradictions requiring systemic review")
    
    # Metadata
    created_at: str = Field(..., description="ISO timestamp when first created")
    updated_at: str = Field(..., description="ISO timestamp when last updated")
    expert_notes: Optional[str] = Field(None, description="Optional expert review notes")


class ManuscriptBlock(BaseModel):
    """A block-level document section with traceability to claims and citations.
    
    Every block must bind to specific Claim_IDs and Citation_Keys for full traceability.
    Blocks are versioned for auditability - each update creates a new version.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "block_id": "intro_001",
                "section_title": "Introduction",
                "content": "# Introduction\n\nThis paper presents...",
                "order_index": 0,
                "claim_ids": ["claim_123", "claim_456"],
                "citation_keys": ["smith2023", "jones2024"],
                "project_id": "project-uuid",
                "version": 1,
            }
        }
    )
    
    id: Optional[str] = Field(None, alias="_id", description="ArangoDB document ID")
    key: Optional[str] = Field(None, alias="_key", description="ArangoDB document key")
    block_id: str = Field(..., description="Unique block identifier within project")
    section_title: str = Field(..., description="Section title (e.g., 'Introduction', 'Methodology')")
    content: str = Field(..., description="Block content in Markdown format")
    order_index: int = Field(default=0, description="Order index for section sequencing")
    claim_ids: List[str] = Field(default_factory=list, description="Linked triple/claim IDs from knowledge graph")
    citation_keys: List[str] = Field(default_factory=list, description="BibTeX citation keys referenced in this block")
    project_id: Optional[str] = Field(None, description="Project identifier this block belongs to")
    version: int = Field(default=1, ge=1, description="Version number for auditability")
    created_at: Optional[str] = Field(None, description="ISO timestamp when block was created")
    updated_at: Optional[str] = Field(None, description="ISO timestamp when block was last updated")
    is_expert_verified: bool = Field(default=False, description="Whether an expert has verified this block")
    expert_notes: Optional[str] = Field(None, description="Optional notes from expert review")


class PatchObject(BaseModel):
    """Proposed edits for a manuscript block (redline review model).
    
    Patches are proposed by AI agents and must be accepted/rejected by humans.
    This enables block-level replace/insert/delete operations with full audit trail.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "original_block_id": "intro_001",
                "proposed_content": "# Introduction\n\n[Revised content...]",
                "rationale": "Clarify the research question based on expert feedback",
                "risk_flag": "Low",
                "status": "Pending",
                "project_id": "project-uuid",
            }
        }
    )
    
    id: Optional[str] = Field(None, alias="_id", description="ArangoDB document ID")
    key: Optional[str] = Field(None, alias="_key", description="ArangoDB document key")
    original_block_id: str = Field(..., description="ID of the block being edited")
    proposed_content: str = Field(..., description="Proposed new content (Markdown)")
    rationale: str = Field(..., description="Reason for this edit proposal")
    risk_flag: Literal["High", "Med", "Low"] = Field(default="Med", description="Risk assessment level")
    status: Literal["Pending", "Accepted", "Rejected"] = Field(default="Pending", description="Review status")
    project_id: Optional[str] = Field(None, description="Project identifier")
    created_at: Optional[str] = Field(None, description="ISO timestamp when patch was created")
    updated_at: Optional[str] = Field(None, description="ISO timestamp when patch was last updated")
    reviewed_by: Optional[str] = Field(None, description="User ID who reviewed this patch")
    review_notes: Optional[str] = Field(None, description="Optional review comments")


class RoleProfile(BaseModel):
    """Dynamic role configuration stored in the knowledge graph."""
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "The Cartographer",
                "description": "Extracts structured entities and relations from text",
                "system_prompt": "You are a knowledge graph extractor...",
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
    capability_type: Optional[str] = Field(None, description="Routing hint (e.g., extraction, logic, synthesis)")
    model_precision: Optional[str] = Field(None, description="Preferred model precision (e.g., FP8, FP4)")
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


# ============================================
# Out-of-Band (OOB) Research Ingestion Schemas
# ============================================

class ExternalReference(BaseModel):
    """External reference from out-of-band research sources (e.g., Perplexity, web scraping).
    
    This represents raw content that has been ingested but not yet processed into the
    canonical knowledge graph. All OOB content must go through extraction and review
    before promotion to canonical_knowledge.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "reference_id": "ref-abc123",
                "project_id": "proj-xyz789",
                "content_raw": "SQL injection vulnerabilities allow attackers...",
                "source_name": "Perplexity",
                "source_url": "https://example.com/article",
                "extracted_at": "2024-01-15T10:30:00Z",
                "tags": ["OOB", "security"],
                "status": "INGESTED"
            }
        }
    )
    
    id: Optional[str] = Field(None, alias="_id", description="ArangoDB document ID")
    key: Optional[str] = Field(None, alias="_key", description="ArangoDB document key")
    
    reference_id: str = Field(..., description="Unique identifier for this external reference")
    project_id: str = Field(..., description="Project ID this reference belongs to")
    content_raw: str = Field(..., description="Raw content text from the external source")
    source_name: str = Field(..., description="Name of the source (e.g., 'Perplexity', 'Web Scrape', 'Manual Paste')")
    source_url: Optional[str] = Field(None, description="URL of the source if available")
    extracted_at: datetime = Field(..., description="Timestamp when this reference was extracted/ingested")
    tags: List[str] = Field(default_factory=lambda: ["OOB"], description="Tags for categorization (default includes 'OOB')")
    status: Literal["INGESTED", "EXTRACTING", "EXTRACTED", "NEEDS_REVIEW", "PROMOTED", "REJECTED"] = Field(
        default="INGESTED",
        description="Current status in the OOB ingestion pipeline"
    )


class CandidateFact(BaseModel):
    """Candidate fact extracted from external references.
    
    These are facts that have been extracted from OOB sources but are NOT yet
    part of the canonical knowledge graph. They require review and promotion
    before being merged into canonical_knowledge.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "fact_id": "fact-xyz789",
                "reference_id": "ref-abc123",
                "project_id": "proj-xyz789",
                "subject": "SQL Injection",
                "predicate": "ENABLES",
                "object": "Database Compromise",
                "confidence": 0.92,
                "priority_boost": 1.0,
                "source_type": "human_injected",
                "promotion_state": "candidate",
                "created_at": "2024-01-15T10:35:00Z"
            }
        }
    )
    
    id: Optional[str] = Field(None, alias="_id", description="ArangoDB document ID")
    key: Optional[str] = Field(None, alias="_key", description="ArangoDB document key")
    
    fact_id: str = Field(..., description="Unique identifier for this candidate fact")
    reference_id: str = Field(..., description="External reference ID this fact was extracted from")
    project_id: str = Field(..., description="Project ID this fact belongs to")
    subject: str = Field(..., description="Subject entity of the fact (triple subject)")
    predicate: str = Field(..., description="Predicate/relation type of the fact (triple predicate)")
    object: str = Field(..., description="Object entity of the fact (triple object)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    priority_boost: float = Field(default=1.0, ge=0.0, description="Priority boost multiplier (default 1.0)")
    source_type: Literal["human_injected"] = Field(..., description="Source type indicator")
    promotion_state: Literal["candidate", "canonical"] = Field(
        default="candidate",
        description="Promotion state: 'candidate' (default) or 'canonical' (after promotion)"
    )
    created_at: datetime = Field(..., description="Timestamp when this candidate fact was created")
