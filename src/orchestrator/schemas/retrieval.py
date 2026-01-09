"""
RetrievalBundle schema for Project Vyasa.

Tracks the retrieval pipeline: Embed → Rerank → Evidence Packet
Persists retrieval artifacts for reproducibility and audit.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class RetrievalBundle(BaseModel):
    """RetrievalBundle: Reproducible evidence selection artifact.
    
    Tracks the full retrieval pipeline:
    1. Query construction (from blueprint section + RQs)
    2. Embed recall (top-K chunks from Qdrant)
    3. Rerank refinement (top-M chunks from reranker)
    4. Evidence Packet A (Primary Sources)
    
    Stored per query/section for reproducibility and audit.
    """
    
    # Identifiers (keyed by: project_id, ingestion_id, section_id, query_id)
    bundle_id: str = Field(..., description="Unique bundle identifier (UUID)")
    query_id: Optional[str] = Field(None, description="Query identifier (if part of a query sequence)")
    project_id: str = Field(..., description="Project identifier")
    ingestion_id: str = Field(..., description="Ingestion identifier (required for evidence scoping)")
    section_id: Optional[str] = Field(None, description="Blueprint section ID (if applicable)")
    
    # Query metadata
    query_text: str = Field(..., description="The search query used")
    query_source: str = Field(..., description="Source of query (e.g., 'blueprint_section', 'manual', 'rq_scoped')")
    linked_rqs: List[str] = Field(default_factory=list, description="Research question IDs linked to this query")
    
    # Retrieval pipeline results
    candidate_chunks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top-K chunks from Qdrant (before reranking)"
    )
    reranked_chunks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top-M chunks after reranking (Evidence Packet A)"
    )
    
    # Scores and metadata
    embed_scores: Optional[List[float]] = Field(None, description="Embedding scores for candidate_chunks")
    rerank_scores: Optional[List[float]] = Field(None, description="Reranker scores for reranked_chunks")
    
    # Model versions (for reproducibility)
    embedder_model_id: str = Field(..., description="Embedder model ID (e.g., 'nvidia/nv-embedqa-e5-v5')")
    reranker_model_id: str = Field(..., description="Reranker model ID (e.g., 'nvidia/llama-3.2-nv-rerankqa-1b-v2')")
    
    # Pipeline parameters
    top_k_embed: int = Field(..., description="Number of chunks retrieved from Qdrant (K)")
    top_k_rerank: int = Field(..., description="Number of chunks returned after reranking (M)")
    
    # Timestamps
    created_at: str = Field(..., description="ISO timestamp of bundle creation")
    version: int = Field(default=1, description="Bundle version (for updates)")
    
    # Provenance markers
    rerank_skipped: bool = Field(default=False, description="True if reranker was skipped (fallback to embed-only)")
    rerank_error: Optional[str] = Field(None, description="Error message if reranker failed (optional)")
    
    @classmethod
    def create(
        cls,
        query_text: str,
        project_id: str,
        ingestion_id: str,
        candidate_chunks: List[Dict[str, Any]],
        reranked_chunks: List[Dict[str, Any]],
        embedder_model_id: str,
        reranker_model_id: str,
        top_k_embed: int,
        top_k_rerank: int,
        query_source: str = "manual",
        linked_rqs: Optional[List[str]] = None,
        section_id: Optional[str] = None,
        query_id: Optional[str] = None,
        rerank_skipped: bool = False,
        rerank_error: Optional[str] = None,
    ) -> "RetrievalBundle":
        """Factory method to create a RetrievalBundle."""
        import uuid
        from datetime import datetime, timezone
        
        bundle_id = str(uuid.uuid4())
        
        # Extract scores if available
        embed_scores = [chunk.get("score") for chunk in candidate_chunks if "score" in chunk]
        rerank_scores = [chunk.get("rerank_score") or chunk.get("score") for chunk in reranked_chunks if "score" in chunk or "rerank_score" in chunk]
        
        return cls(
            bundle_id=bundle_id,
            query_id=query_id,
            project_id=project_id,
            ingestion_id=ingestion_id,
            section_id=section_id,
            query_text=query_text,
            query_source=query_source,
            linked_rqs=linked_rqs or [],
            candidate_chunks=candidate_chunks,
            reranked_chunks=reranked_chunks,
            embed_scores=embed_scores if embed_scores else None,
            rerank_scores=rerank_scores if rerank_scores else None,
            embedder_model_id=embedder_model_id,
            reranker_model_id=reranker_model_id,
            top_k_embed=top_k_embed,
            top_k_rerank=top_k_rerank,
            created_at=datetime.now(timezone.utc).isoformat(),
            version=1,
            rerank_skipped=rerank_skipped,
            rerank_error=rerank_error,
        )
