"""
Retrieval Service for Section Synthesis Loop.

Handles retrieval + rerank integration for section synthesis:
1. Embed query → Qdrant search (top-K)
2. Rerank candidates → top-M (if enabled)
3. Persist RetrievalBundle
4. Return reranked chunks with RetrievalBundle ID
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from ...shared.config import (
    RERANKER_ENABLED,
    RERANKER_REQUIRED,
    RETRIEVAL_TOP_K,
    RERANK_TOP_M,
    RERANKER_URL,
    RERANKER_MODEL_ID,
    EMBEDDER_MODEL_ID,
    get_arango_password,
    ARANGODB_DB,
    ARANGODB_USER,
    get_memory_url,
)
from arango import ArangoClient
from arango.database import StandardDatabase
from ...shared.logger import get_logger
from ..storage.qdrant import QdrantStorage
from ..services.retrieval_bundle_service import RetrievalBundleService
from ..schemas.retrieval import RetrievalBundle

logger = get_logger("orchestrator", __name__)


class RetrievalService:
    """Service for retrieval + rerank integration in section synthesis loop."""
    
    def __init__(self, db: Optional[StandardDatabase] = None) -> None:
        """Initialize retrieval service.
        
        Args:
            db: ArangoDB database instance (optional, for RetrievalBundle persistence).
                If None, will try to initialize from config.
        """
        self.qdrant_storage = QdrantStorage()
        
        # Initialize bundle service if DB available
        if db:
            self.bundle_service = RetrievalBundleService(db)
        else:
            try:
                client = ArangoClient(hosts=get_memory_url())
                db_instance = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
                self.bundle_service = RetrievalBundleService(db_instance)
            except Exception as e:
                logger.warning(f"Failed to initialize RetrievalBundleService: {e}", exc_info=True)
                self.bundle_service = None
    
    def retrieve_for_section(
        self,
        query_text: str,
        project_id: str,
        ingestion_id: Optional[str] = None,
        section_id: Optional[str] = None,
        top_k: Optional[int] = None,
        top_m: Optional[int] = None,
        use_reranker: Optional[bool] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Retrieve chunks for section synthesis with optional reranking.
        
        Flow:
        1. Embed query → Qdrant search (top-K)
        2. Rerank candidates → top-M (if enabled)
        3. Persist RetrievalBundle (if bundle_service available)
        4. Return reranked chunks + RetrievalBundle ID
        
        Args:
            query_text: Search query text.
            project_id: Project identifier (required for security).
            ingestion_id: Optional ingestion identifier (for filtering).
            section_id: Optional blueprint section ID (for provenance).
            top_k: Number of chunks to retrieve from Qdrant (default: RETRIEVAL_TOP_K=64).
            top_m: Number of chunks to return after reranking (default: RERANK_TOP_M=24).
            use_reranker: Whether to use reranker (default: RERANKER_ENABLED).
        
        Returns:
            Tuple of (reranked_chunks, bundle_id):
            - reranked_chunks: List of reranked chunks with scores
            - bundle_id: RetrievalBundle ID if persisted, None otherwise
        
        Raises:
            ValueError: If reranker is required but unavailable.
        """
        # Use config defaults if not provided
        top_k = top_k or RETRIEVAL_TOP_K
        top_m = top_m or RERANK_TOP_M
        
        # Determine reranker usage:
        # - If explicitly set (True/False), use that
        # - If None, use global default from config
        if use_reranker is None:
            use_reranker = RERANKER_ENABLED
        
        # If reranker is disabled globally, never use it (even if caller requested it)
        if use_reranker and not RERANKER_ENABLED:
            logger.warning(
                "Reranker requested but RERANKER_ENABLED=false, falling back to embed-only",
                extra={"payload": {"project_id": project_id, "section_id": section_id}}
            )
            use_reranker = False
        
        # Step 1: Embed retrieval (top-K)
        # We disable reranking in qdrant_storage since we handle it ourselves
        # This ensures we get top-K candidates sorted by embedding score
        candidate_chunks = self.qdrant_storage.retrieve_chunks_by_query(
            query_text=query_text,
            project_id=project_id,
            ingestion_id=ingestion_id,
            limit=top_k,  # Retrieve top-K initially (no reranking in qdrant_storage)
            top_k_embed=top_k,
            top_k_rerank=None,  # Not used since use_reranker=False
            use_reranker=False,  # We'll handle reranking ourselves in this service
        )
        
        if not candidate_chunks:
            logger.warning(
                f"No chunks retrieved for query: {query_text[:100]}",
                extra={"payload": {"project_id": project_id, "ingestion_id": ingestion_id}}
            )
            return [], None
        
        # Step 2: Rerank (if enabled)
        reranked_chunks = candidate_chunks
        rerank_skipped = True
        rerank_error = None
        
        if use_reranker:
            try:
                reranked_chunks = self._rerank_chunks(query_text, candidate_chunks, top_m)
                rerank_skipped = False
                logger.info(
                    f"Reranked {len(candidate_chunks)} candidates → {len(reranked_chunks)} results",
                    extra={
                        "payload": {
                            "project_id": project_id,
                            "section_id": section_id,
                            "top_k": top_k,
                            "top_m": top_m,
                        }
                    }
                )
            except Exception as e:
                error_msg = str(e)
                rerank_error = error_msg
                
                if RERANKER_REQUIRED:
                    # Fail if reranker is required
                    logger.error(
                        f"Reranker is required but unavailable: {error_msg}",
                        extra={"payload": {"project_id": project_id, "section_id": section_id}},
                        exc_info=True
                    )
                    raise ValueError(f"Reranker is required but unavailable: {error_msg}") from e
                else:
                    # Fallback to embed-only if optional
                    logger.warning(
                        f"Reranker failed, falling back to embed-only: {error_msg}",
                        extra={"payload": {"project_id": project_id, "section_id": section_id}},
                        exc_info=True
                    )
                    # Sort by embedding score (descending) before taking top-M
                    sorted_chunks = sorted(candidate_chunks, key=lambda x: x.get("score", 0.0), reverse=True)
                    reranked_chunks = sorted_chunks[:top_m]  # Use top-M by embedding score
        else:
            # Reranker disabled: use top-M by embedding score
            sorted_chunks = sorted(candidate_chunks, key=lambda x: x.get("score", 0.0), reverse=True)
            reranked_chunks = sorted_chunks[:top_m]
        
        # Step 3: Persist RetrievalBundle (if bundle_service available)
        bundle_id = None
        if self.bundle_service:
            try:
                retrieval_bundle = RetrievalBundle.create(
                    query_text=query_text,
                    project_id=project_id,
                    candidate_chunks=candidate_chunks,
                    reranked_chunks=reranked_chunks,
                    embedder_model_id=EMBEDDER_MODEL_ID,
                    reranker_model_id=RERANKER_MODEL_ID if use_reranker and not rerank_skipped else "none",
                    top_k_embed=top_k,
                    top_k_rerank=top_m,
                    query_source="blueprint_section",
                    section_id=section_id,
                    rerank_skipped=rerank_skipped,
                    rerank_error=rerank_error,
                )
                
                self.bundle_service.save_bundle(retrieval_bundle)
                bundle_id = retrieval_bundle.bundle_id
                
                logger.debug(
                    f"Persisted RetrievalBundle: {bundle_id}",
                    extra={
                        "payload": {
                            "bundle_id": bundle_id,
                            "project_id": project_id,
                            "section_id": section_id,
                            "top_k": top_k,
                            "top_m": top_m,
                            "rerank_skipped": rerank_skipped,
                        }
                    }
                )
            except Exception as e:
                # Bundle persistence is non-fatal
                logger.warning(
                    f"Failed to persist RetrievalBundle: {e}",
                    extra={"payload": {"project_id": project_id, "section_id": section_id}},
                    exc_info=True
                )
        
        return reranked_chunks, bundle_id
    
    def _rerank_chunks(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_m: int,
    ) -> List[Dict[str, Any]]:
        """Rerank chunks using OpenAI-style reranker endpoint.
        
        Args:
            query: Search query text.
            chunks: List of candidate chunks from Qdrant.
            top_m: Number of results to return after reranking.
        
        Returns:
            List of reranked chunks, sorted by score (descending).
        
        Raises:
            requests.RequestException: If reranker service is unavailable.
            ValueError: If response format is invalid.
        """
        import requests
        
        # Normalize chunks to OpenAI-style format
        documents = []
        for chunk in chunks:
            doc = {
                "id": chunk.get("chunk_id"),
                "text": chunk.get("text_content") or chunk.get("text", ""),
            }
            # Preserve metadata
            if "payload" in chunk:
                doc["metadata"] = chunk["payload"]
            elif "metadata" in chunk:
                doc["metadata"] = chunk["metadata"]
            documents.append(doc)
        
        # Use reranker URL from config (already resolved at module level)
        reranker_url = RERANKER_URL
        
        # Call OpenAI-style /v1/ranking endpoint (or fallback to /rerank)
        # Try /v1/ranking first, then fallback to /rerank for backward compatibility
        payload = {
            "model": RERANKER_MODEL_ID,
            "query": query,
            "documents": documents,
            "top_k": top_m,
        }
        
        try:
            # Try OpenAI-style endpoint first
            response = requests.post(
                f"{reranker_url}/v1/ranking",
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.RequestException:
            # Fallback to existing /rerank endpoint
            logger.debug("OpenAI-style /v1/ranking not available, using /rerank endpoint")
            # For /rerank, documents should be list of strings or list of dicts with "text"
            fallback_documents = []
            for doc in documents:
                if isinstance(doc, dict):
                    fallback_documents.append({
                        "text": doc.get("text", ""),
                        "id": doc.get("id"),
                        "chunk_id": doc.get("id"),  # Preserve chunk_id for mapping
                        "metadata": doc.get("metadata", {}),
                    })
                else:
                    fallback_documents.append(str(doc))
            
            fallback_payload = {
                "query": query,
                "documents": fallback_documents,
                "top_k": top_m,
            }
            response = requests.post(
                f"{reranker_url}/rerank",
                json=fallback_payload,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
        
        # Parse response (handle both formats)
        if "results" in result:
            # Existing /rerank format
            reranked_results = result["results"]
        elif "data" in result and isinstance(result["data"], list):
            # OpenAI-style format
            reranked_results = result["data"]
        else:
            raise ValueError(f"Invalid reranker response format: missing 'results' or 'data' field")
        
        # Map reranked results back to chunks
        reranked_chunks = []
        chunk_map = {chunk.get("chunk_id"): chunk for chunk in chunks}
        
        for idx, reranked_item in enumerate(reranked_results):
            # Handle both formats (/v1/ranking uses "id", /rerank uses "chunk_id")
            chunk_id = reranked_item.get("id") or reranked_item.get("chunk_id")
            score = reranked_item.get("score", 0.0)
            rank = reranked_item.get("rank", idx + 1)
            
            # Find original chunk by chunk_id
            original_chunk = chunk_map.get(chunk_id) if chunk_id else None
            
            if original_chunk:
                # Merge reranker scores with original chunk
                merged = {**original_chunk}
                merged["rerank_score"] = float(score)
                merged["rerank_rank"] = int(rank)
                merged["score"] = float(score)  # Update primary score to rerank score
                reranked_chunks.append(merged)
            else:
                # Fallback: try to find by text match or create new chunk dict
                text = reranked_item.get("text", "")
                for chunk in chunks:
                    if (chunk.get("text_content") == text or 
                        chunk.get("text") == text):
                        original_chunk = chunk
                        break
                
                if original_chunk:
                    merged = {**original_chunk}
                    merged["rerank_score"] = float(score)
                    merged["rerank_rank"] = int(rank)
                    merged["score"] = float(score)
                    reranked_chunks.append(merged)
                else:
                    # Last resort: create new chunk dict from reranker result
                    reranked_chunks.append({
                        "chunk_id": chunk_id or f"reranked_{idx}",
                        "text_content": text,
                        "score": float(score),
                        "rerank_score": float(score),
                        "rerank_rank": int(rank),
                        "payload": reranked_item.get("metadata", {}),
                    })
        
        return reranked_chunks
