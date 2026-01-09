"""
EvidencePack schema for Project Vyasa.

EvidencePack is a first-class persisted artifact that represents the bounded
evidence context (Packet A) used by Tier-B calls (Cartographer, Critic, Synthesizer).

EvidencePack is built from RetrievalBundle top-M chunks with bounded snippet count
and size to ensure deterministic, reproducible evidence context.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class EvidencePointer(BaseModel):
    """Pointer to a specific evidence chunk."""
    chunk_id: str = Field(..., description="Chunk identifier")
    file_id: Optional[str] = Field(None, description="File/document identifier (file_hash or doc_id)")
    doc_id: Optional[str] = Field(None, description="Document identifier (alias for file_id)")
    page_number: Optional[int] = Field(None, description="Page number (1-based)")
    section_label: Optional[str] = Field(None, description="Section label or heading if available")


class EvidenceSnippet(BaseModel):
    """Bounded snippet of evidence text."""
    chunk_id: str = Field(..., description="Chunk identifier this snippet comes from")
    quote_text: str = Field(..., description="Snippet text (bounded to ~300-800 tokens)")
    page_number: Optional[int] = Field(None, description="Page number (1-based)")
    token_estimate: int = Field(..., description="Estimated token count for this snippet")
    source_meta: Dict[str, Any] = Field(default_factory=dict, description="Source metadata (filename, url, doi, etc.)")


class SourceMetadata(BaseModel):
    """Metadata about the source document."""
    filename: str = Field(..., description="Source filename")
    url: Optional[str] = Field(None, description="Source URL if available")
    doi: Optional[str] = Field(None, description="DOI if available")
    ingestion_timestamp: Optional[str] = Field(None, description="ISO timestamp of ingestion")


class ModelVersions(BaseModel):
    """Model versions used for retrieval."""
    embedder_model_id: str = Field(..., description="Embedder model ID")
    reranker_model_id: str = Field(..., description="Reranker model ID (or 'none' if skipped)")


class EvidencePack(BaseModel):
    """EvidencePack: First-class persisted artifact for Tier-B calls.
    
    EvidencePack represents the bounded evidence context (Packet A) that must be
    provided to all Tier-B calls (Cartographer pass 2, Critic verify, Synthesizer).
    
    Built from RetrievalBundle top-M chunks with:
    - Bounded snippet count: 5-20 snippets
    - Bounded snippet size: ~300-800 tokens per snippet (truncated deterministically)
    - Never includes full PDF text unless explicitly requested
    """
    
    # Identifiers
    pack_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique EvidencePack identifier (UUID)")
    project_id: str = Field(..., description="Project identifier")
    ingestion_id: str = Field(..., description="Ingestion identifier (required for evidence scoping)")
    section_id: Optional[str] = Field(None, description="Blueprint section ID (if applicable)")
    query_id: Optional[str] = Field(None, description="Query identifier (if part of a query sequence)")
    
    # Timestamp
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO timestamp of pack creation")
    
    # Evidence structure
    pointers: List[EvidencePointer] = Field(
        default_factory=list,
        description="List of evidence pointers (chunk_id, file_id, page_number, section_label)"
    )
    snippets: List[EvidenceSnippet] = Field(
        default_factory=list,
        description="List of evidence snippets (bounded: 5-20 snippets, ~300-800 tokens each)"
    )
    source_meta: Dict[str, str] = Field(
        default_factory=dict,
        description="Source metadata keyed by file_id/doc_id (filename, url, doi, ingestion_timestamp)"
    )
    glossary_terms: List[str] = Field(
        default_factory=list,
        description="Optional glossary terms extracted from evidence"
    )
    
    # Model versions (for reproducibility)
    model_versions: ModelVersions = Field(..., description="Model versions used for retrieval")
    
    # Link to RetrievalBundle
    retrieval_bundle_id: str = Field(..., description="ID of the RetrievalBundle this EvidencePack was built from")
    
    @field_validator("snippets")
    @classmethod
    def validate_snippet_count(cls, v: List[EvidenceSnippet]) -> List[EvidenceSnippet]:
        """Validate snippet count is within bounds (5-20)."""
        if len(v) < 5:
            raise ValueError(f"EvidencePack must have at least 5 snippets, got {len(v)}")
        if len(v) > 20:
            raise ValueError(f"EvidencePack must have at most 20 snippets, got {len(v)}")
        return v
    
    @field_validator("snippets", mode="before")
    @classmethod
    def validate_snippet_tokens(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate snippet token estimates are within bounds (~300-800)."""
        if isinstance(v, list):
            for snippet in v:
                if isinstance(snippet, dict):
                    token_estimate = snippet.get("token_estimate", 0)
                    if token_estimate < 300:
                        # Warn but don't fail (may be short chunks)
                        pass
                    if token_estimate > 800:
                        raise ValueError(f"EvidencePack snippet token_estimate must be <= 800, got {token_estimate}")
        return v
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z"
        }
