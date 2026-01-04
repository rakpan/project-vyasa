"""
Canonical Claim and SourceAnchor schemas for Project Vyasa.

Defines the single source of truth for Claim structure used throughout:
- Cartographer output
- ArangoDB persistence
- API responses
- Manuscript bindings

The "Anchor Thread" ensures source_anchor metadata is preserved losslessly
through Qdrant → Claim → ArangoDB storage.
"""

import hashlib
import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class SourceAnchor(BaseModel):
    """Source anchor for UI context anchoring and evidence highlighting.
    
    Provides precise location information for scrolling and highlighting
    evidence spans in the Evidence pane. At least one of bbox/span/snippet
    must be present to enable anchoring.
    
    This structure is preserved through the "Anchor Thread":
    Qdrant payload → Claim → ArangoDB edge (unchanged).
    """
    doc_id: str = Field(..., description="Document hash (file_hash/SHA256)")
    page_number: int = Field(..., ge=1, description="Page number (1-based)")
    
    # Bounding box (normalized coordinates)
    bbox: Optional[Dict[str, float]] = Field(
        None,
        description="Bounding box as {x: float, y: float, w: float, h: float}"
    )
    
    # Text span (character offsets)
    span: Optional[Dict[str, int]] = Field(
        None,
        description="Text span as {start: int, end: int} (character offsets)"
    )
    
    # Snippet (fallback for highlight)
    snippet: Optional[str] = Field(
        None,
        description="Text snippet for fallback highlighting"
    )
    
    @model_validator(mode="after")
    def validate_anchor_has_location(self):
        """Ensure at least one of bbox/span/snippet exists."""
        if not self.bbox and not self.span and not self.snippet:
            raise ValueError("SourceAnchor must have at least one of: bbox, span, or snippet")
        return self
    
    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        """Validate bbox structure if present."""
        if v is None:
            return None
        required_keys = {"x", "y", "w", "h"}
        if not all(k in v for k in required_keys):
            raise ValueError(f"bbox must have keys: {required_keys}")
        if not all(isinstance(v[k], (int, float)) for k in required_keys):
            raise ValueError("bbox values must be numeric")
        return v
    
    @field_validator("span")
    @classmethod
    def validate_span(cls, v: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]:
        """Validate span structure if present."""
        if v is None:
            return None
        required_keys = {"start", "end"}
        if not all(k in v for k in required_keys):
            raise ValueError(f"span must have keys: {{start, end}}")
        if not all(isinstance(v[k], int) for k in required_keys):
            raise ValueError("span values must be integers")
        if v["start"] < 0 or v["end"] < v["start"]:
            raise ValueError("span start must be >= 0 and end must be >= start")
        return v


class Claim(BaseModel):
    """Canonical Claim schema used throughout Project Vyasa.
    
    This is the single source of truth for claim structure across:
    - Cartographer extraction output
    - ArangoDB edge persistence
    - API responses
    - Manuscript block bindings
    
    The claim_id is stable and deterministic (UUIDv4 or hash-based).
    source_anchor is mandatory in conservative mode and preserved through
    the "Anchor Thread" (Qdrant → Claim → ArangoDB).
    """
    
    # Stable identifier
    claim_id: str = Field(..., description="Stable claim identifier (UUIDv4 or deterministic hash)")
    
    # Triple structure
    subject: str = Field(..., description="Subject entity")
    predicate: str = Field(..., description="Predicate/relation")
    object: str = Field(..., description="Object entity")
    
    # Metadata
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")
    rq_hits: List[str] = Field(default_factory=list, description="Research question IDs this claim addresses")
    
    # Provenance
    ingestion_id: str = Field(..., description="Ingestion identifier")
    file_hash: str = Field(..., description="Source document hash (SHA256)")
    
    # Source anchor (mandatory in conservative mode)
    source_anchor: Optional[SourceAnchor] = Field(
        None,
        description="Source anchor for UI context anchoring (mandatory in conservative mode)"
    )
    
    # Additional metadata (optional)
    claim_text: Optional[str] = Field(None, description="Human-readable claim text")
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relevance to thesis/RQs")
    is_expert_verified: bool = Field(default=False, description="Whether expert has verified this claim")
    expert_notes: Optional[str] = Field(None, description="Expert review notes")
    
    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, v: str) -> str:
        """Validate claim_id format (UUIDv4 or deterministic hash)."""
        if not v or not isinstance(v, str):
            raise ValueError("claim_id must be a non-empty string")
        # Accept UUIDv4 or hex hash (64 chars for SHA256)
        if len(v) not in (36, 64):  # UUIDv4 has 36 chars, SHA256 has 64 hex chars
            # Allow other formats but warn
            pass
        return v
    
    @model_validator(mode="after")
    def validate_anchor_in_conservative_mode(self):
        """Ensure source_anchor is present in conservative mode.
        
        Note: This validation requires rigor_level context, which may not
        be available at Claim creation time. The validation should be
        performed at the node level where rigor_level is known.
        """
        # This is a placeholder - actual validation should happen at node level
        # where rigor_level is available from project_config
        return self
    
    @classmethod
    def generate_claim_id(
        cls,
        subject: str,
        predicate: str,
        obj: str,
        file_hash: str,
        page_number: int,
    ) -> str:
        """Generate deterministic claim_id from triple + source location.
        
        Uses SHA256 hash of normalized triple + source location for stable IDs.
        This ensures the same claim from the same source gets the same ID.
        
        Args:
            subject: Subject entity
            predicate: Predicate/relation
            obj: Object entity
            file_hash: Source document hash
            page_number: Page number
        
        Returns:
            Deterministic claim_id (64-char hex string)
        """
        # Normalize triple components
        normalized = f"{subject.strip().lower()}|{predicate.strip().lower()}|{obj.strip().lower()}|{file_hash}|{page_number}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    
    @classmethod
    def from_triple_dict(
        cls,
        triple: Dict[str, Any],
        ingestion_id: str,
        rigor_level: str = "exploratory",
    ) -> "Claim":
        """Create Claim from triple dictionary (Cartographer output).
        
        Extracts source_anchor from source_pointer if present and preserves
        it through the "Anchor Thread". In conservative mode, source_anchor
        is required.
        
        Args:
            triple: Triple dictionary with subject, predicate, object, source_pointer, etc.
            ingestion_id: Ingestion identifier
            rigor_level: Rigor level ("exploratory" or "conservative")
        
        Returns:
            Claim instance
        
        Raises:
            ValueError: If required fields are missing or source_anchor is missing in conservative mode
        """
        subject = triple.get("subject", "")
        predicate = triple.get("predicate", "")
        obj = triple.get("object", "")
        file_hash = triple.get("file_hash") or (triple.get("source_pointer") or {}).get("doc_hash", "")
        page_number = (triple.get("source_pointer") or {}).get("page") or (triple.get("source_anchor") or {}).get("page_number", 1)
        
        if not subject or not predicate or not obj:
            raise ValueError("Triple missing required fields: subject, predicate, object")
        if not file_hash:
            raise ValueError("Triple missing file_hash or source_pointer.doc_hash")
        
        # Generate claim_id (deterministic)
        claim_id = cls.generate_claim_id(subject, predicate, obj, file_hash, page_number)
        
        # Extract source_anchor from source_pointer or use existing source_anchor
        source_anchor = None
        if triple.get("source_anchor"):
            # Already in source_anchor format
            source_anchor = SourceAnchor(**triple["source_anchor"])
        elif triple.get("source_pointer"):
            # Convert source_pointer to source_anchor
            sp = triple["source_pointer"]
            anchor_data = {
                "doc_id": sp.get("doc_hash", file_hash),
                "page_number": sp.get("page", page_number),
            }
            # Add bbox if present (convert from [x1,y1,x2,y2] to {x,y,w,h})
            bbox = sp.get("bbox")
            if bbox and isinstance(bbox, list) and len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                anchor_data["bbox"] = {
                    "x": float(x1),
                    "y": float(y1),
                    "w": float(x2 - x1),
                    "h": float(y2 - y1),
                }
            # Add snippet if present
            snippet = sp.get("snippet")
            if snippet:
                anchor_data["snippet"] = snippet
            source_anchor = SourceAnchor(**anchor_data)
        
        # Validate source_anchor in conservative mode
        if rigor_level == "conservative" and not source_anchor:
            raise ValueError("source_anchor is required in conservative mode")
        
        return cls(
            claim_id=claim_id,
            subject=subject,
            predicate=predicate,
            object=obj,
            confidence=float(triple.get("confidence", 0.5)),
            rq_hits=triple.get("rq_hits", []),
            ingestion_id=ingestion_id,
            file_hash=file_hash,
            source_anchor=source_anchor,
            claim_text=triple.get("claim_text"),
            relevance_score=triple.get("relevance_score"),
            is_expert_verified=triple.get("is_expert_verified", False),
            expert_notes=triple.get("expert_notes"),
        )


class DocumentChunk(BaseModel):
    """A document chunk with metadata for ingestion workspace.
    
    Represents a processed chunk of text from a source document with
    metadata for retrieval and provenance tracking.
    """
    text: str = Field(..., description="Chunk text content")
    doc_hash: str = Field(..., description="Source document hash (SHA256)")
    page: Optional[int] = Field(None, description="Page number (1-based)")
    chunk_index: int = Field(..., description="Index of chunk within document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
