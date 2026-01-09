"""
Reranker client for Project Vyasa.

Provides a simple interface to the reranker service for refining retrieval results.
"""
import logging
from typing import List, Dict, Any, Optional
import requests

from .config import get_reranker_url, RERANKER_MODEL_ID
from .logger import get_logger

logger = get_logger("shared", __name__)


def rerank_documents(
    query: str,
    documents: List[Dict[str, Any]],
    top_k: Optional[int] = None,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """
    Rerank candidate documents by relevance to a query.
    
    Args:
        query: The search query string.
        documents: List of document dictionaries. Each dict should have:
            - "text" or "content": str (document text)
            - "chunk_id": Optional[str] (chunk identifier)
            - "metadata": Optional[Dict] (additional metadata)
        top_k: Optional maximum number of results to return (default: all, sorted).
        timeout: Request timeout in seconds (default: 30).
    
    Returns:
        List of reranked documents, sorted by relevance score (descending).
        Each dict contains:
            - "text": str
            - "score": float (relevance score)
            - "rank": int (1-based rank)
            - "chunk_id": Optional[str] (if provided)
            - "metadata": Optional[Dict] (if provided)
    
    Raises:
        requests.RequestException: If the reranker service is unavailable.
        ValueError: If the response format is invalid.
    """
    reranker_url = get_reranker_url()
    
    # Prepare request payload
    payload = {
        "query": query,
        "documents": documents,
    }
    if top_k is not None:
        payload["top_k"] = top_k
    
    try:
        response = requests.post(
            f"{reranker_url}/rerank",
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        result = response.json()
        
        # Validate response structure
        if "results" not in result:
            raise ValueError(f"Invalid reranker response: missing 'results' field")
        
        return result["results"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Reranker service error: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during reranking: {e}", exc_info=True)
        raise ValueError(f"Failed to rerank documents: {e}") from e


def rerank_chunks(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: Optional[int] = None,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """
    Convenience wrapper for reranking Qdrant chunks.
    
    Args:
        query: The search query string.
        chunks: List of chunk dictionaries from Qdrant (with chunk_id, text_content, payload, score).
        top_k: Optional maximum number of results to return.
        timeout: Request timeout in seconds.
    
    Returns:
        List of reranked chunks with updated scores and ranks.
    """
    # Normalize chunks to reranker format
    documents = []
    for chunk in chunks:
        doc = {
            "text": chunk.get("text_content") or chunk.get("text", ""),
            "chunk_id": chunk.get("chunk_id"),
        }
        # Preserve payload metadata
        if "payload" in chunk:
            doc["metadata"] = chunk["payload"]
        elif "metadata" in chunk:
            doc["metadata"] = chunk["metadata"]
        documents.append(doc)
    
    # Rerank
    reranked = rerank_documents(query, documents, top_k=top_k, timeout=timeout)
    
    # Merge reranker results back with original chunk data
    result_chunks = []
    for reranked_doc in reranked:
        # Find original chunk by chunk_id or text
        original_chunk = None
        for chunk in chunks:
            if reranked_doc.get("chunk_id") == chunk.get("chunk_id"):
                original_chunk = chunk
                break
            elif reranked_doc.get("text") == (chunk.get("text_content") or chunk.get("text", "")):
                original_chunk = chunk
                break
        
        if original_chunk:
            # Merge reranker scores with original chunk
            merged = {**original_chunk}
            merged["rerank_score"] = reranked_doc["score"]
            merged["rerank_rank"] = reranked_doc["rank"]
            # Update primary score to rerank score
            merged["score"] = reranked_doc["score"]
            result_chunks.append(merged)
        else:
            # Fallback: create new chunk dict from reranker result
            result_chunks.append({
                "chunk_id": reranked_doc.get("chunk_id"),
                "text_content": reranked_doc["text"],
                "score": reranked_doc["score"],
                "rerank_score": reranked_doc["score"],
                "rerank_rank": reranked_doc["rank"],
                "payload": reranked_doc.get("metadata", {}),
            })
    
    return result_chunks
