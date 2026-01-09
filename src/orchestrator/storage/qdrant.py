"""
Qdrant storage module for PDF chunk ingestion with anchor payload contract.

Ensures every chunk stored in Qdrant includes the payload fields required
for context anchors and lineage tracking:
- file_hash
- ingestion_id
- page_number
- bbox (or span)
- chunk text length

This enables the "Anchor Thread" where Qdrant payload → Claim → ArangoDB
preserves anchor metadata losslessly.
"""

import hashlib
import logging
import os
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None  # type: ignore
    Filter = None  # type: ignore
    FieldCondition = None  # type: ignore
    MatchValue = None  # type: ignore

from ...shared.logger import get_logger
from ...shared.config import EMBEDDING_DIMENSION
from ...vector.client import get_qdrant_client, ensure_collection_dimension

logger = get_logger("orchestrator", __name__)

# Default collection name for document chunks
DEFAULT_COLLECTION = "document_chunks"


class QdrantStorage:
    """Qdrant storage for PDF chunks with payload contract enforcement."""
    
    def __init__(self, collection_name: str = DEFAULT_COLLECTION, client: Optional[QdrantClient] = None):
        """Initialize Qdrant storage.
        
        Args:
            collection_name: Qdrant collection name.
            client: Optional QdrantClient instance (for testing).
        """
        if not QDRANT_AVAILABLE:
            raise RuntimeError("qdrant-client package is not installed")
        
        self.collection_name = collection_name
        self.client = client or get_qdrant_client()
        self._ensure_collection()
        # Validate dimension BEFORE allowing any ingestion operations
        try:
            ensure_collection_dimension(self.client, self.collection_name, EMBEDDING_DIMENSION)
        except ValueError as e:
            logger.critical(
                f"Qdrant collection dimension mismatch for {self.collection_name}: {e}",
                extra={"payload": {"collection_name": self.collection_name, "expected_dim": EMBEDDING_DIMENSION}}
            )
            raise
    
    def _ensure_collection(self) -> None:
        """Ensure collection exists with proper configuration."""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIMENSION,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
                # Validate dimension after creation
                ensure_collection_dimension(self.client, self.collection_name, EMBEDDING_DIMENSION)
        except Exception as e:
            logger.error(f"Failed to ensure Qdrant collection: {e}", exc_info=True)
            raise
    
    def ingest_document_chunks(
        self,
        pdf_path: str,
        file_hash: str,
        ingestion_id: str,
        project_id: str,
        rigor_level: str = "exploratory",
        embeddings: Optional[List[List[float]]] = None,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """Ingest PDF chunks into Qdrant with required payload fields.
        
        Splits PDF into chunks with deterministic metadata and stores them
        in Qdrant with payload that MUST include:
        - file_hash
        - ingestion_id
        - page_number
        - bbox (or span)
        - chunk_text_length
        
        Args:
            pdf_path: Path to PDF file.
            file_hash: SHA256 hash of PDF file.
            ingestion_id: Ingestion identifier.
            project_id: Project identifier.
            rigor_level: Rigor level ("exploratory" or "conservative").
            embeddings: Optional pre-computed embeddings (if None, will need to be generated).
        
        Returns:
            Tuple of (chunk_count, chunk_metadata_list).
            chunk_metadata_list contains dicts with:
            - chunk_id: str
            - page_number: int
            - bbox: Optional[Dict] or span: Optional[Dict]
            - text_length: int
        
        Raises:
            ValueError: If required payload fields are missing (in conservative mode).
            FileNotFoundError: If PDF file doesn't exist.
        """
        try:
            import pymupdf
        except ImportError:
            raise RuntimeError("pymupdf is required for PDF chunking")
        
        pdf_path_obj = self._resolve_pdf_path(pdf_path)
        
        # Open PDF and extract chunks with metadata
        doc = pymupdf.open(str(pdf_path_obj))
        chunks: List[Dict[str, Any]] = []
        chunk_points: List[PointStruct] = []
        
        try:
            for page_num in range(1, len(doc) + 1):
                page = doc[page_num - 1]
                page_text = page.get_text()
                
                # Split page into chunks (deterministic: fixed size)
                # Use 512 characters per chunk with 50 char overlap
                chunk_size = 512
                overlap = 50
                
                page_chunks = self._split_text_into_chunks(page_text, chunk_size, overlap)
                
                for chunk_idx, chunk_text in enumerate(page_chunks):
                    # Generate deterministic chunk ID
                    chunk_id = self._generate_chunk_id(file_hash, page_num, chunk_idx)
                    
                    # Extract bbox for this chunk (approximate from text position)
                    # For now, use page-level bbox (can be refined later)
                    bbox = self._extract_chunk_bbox(page, chunk_idx, len(page_chunks))
                    
                    # Build payload (MUST include required fields)
                    payload = {
                        "file_hash": file_hash,
                        "ingestion_id": ingestion_id,
                        "project_id": project_id,
                        "page_number": page_num,
                        "chunk_index": chunk_idx,
                        "chunk_text_length": len(chunk_text),
                        "text_content": chunk_text,  # Store text content for retrieval
                    }
                    
                    # Add bbox if available
                    if bbox:
                        payload["bbox"] = bbox
                    
                    # Validate payload in conservative mode
                    if rigor_level == "conservative":
                        if not payload.get("file_hash"):
                            raise ValueError("Payload missing required field: file_hash")
                        if not payload.get("ingestion_id"):
                            raise ValueError("Payload missing required field: ingestion_id")
                        if payload.get("page_number") is None:
                            raise ValueError("Payload missing required field: page_number")
                        if not payload.get("bbox") and not payload.get("span"):
                            # In conservative mode, require at least bbox or span
                            raise ValueError(
                                f"Chunk {chunk_id} missing required field: bbox or span (conservative mode)"
                            )
                    
                    chunks.append({
                        "chunk_id": chunk_id,
                        "text": chunk_text,
                        "payload": payload,
                        "page_number": page_num,
                        "bbox": bbox,
                    })
            
            # If embeddings provided, use them; otherwise generate placeholder
            # (In production, embeddings would be generated by embedder service)
            if embeddings is None:
                # Generate zero vectors as placeholder (will be replaced by embedder)
                embeddings = [[0.0] * EMBEDDING_DIMENSION for _ in chunks]
            
            if len(embeddings) != len(chunks):
                raise ValueError(f"Embeddings count ({len(embeddings)}) does not match chunks count ({len(chunks)})")
            
            # Create PointStruct objects for Qdrant
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                point = PointStruct(
                    id=chunk["chunk_id"],
                    vector=embedding,
                    payload=chunk["payload"],
                )
                chunk_points.append(point)
            
            # Upsert to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=chunk_points,
            )
            
            logger.info(
                f"Ingested {len(chunks)} chunks into Qdrant",
                extra={
                    "payload": {
                        "file_hash": file_hash[:16],
                        "ingestion_id": ingestion_id,
                        "chunk_count": len(chunks),
                    }
                }
            )
            
            # Return chunk metadata
            chunk_metadata = [
                {
                    "chunk_id": chunk["chunk_id"],
                    "page_number": chunk["page_number"],
                    "bbox": chunk.get("bbox"),
                    "text_length": chunk["payload"]["chunk_text_length"],
                }
                for chunk in chunks
            ]
            
            return len(chunks), chunk_metadata
            
        finally:
            doc.close()

    @staticmethod
    def _resolve_pdf_path(pdf_path: str) -> Path:
        """Resolve a PDF path against allowed roots and validate it."""
        if not pdf_path:
            raise FileNotFoundError("PDF path not provided")
        if "\x00" in pdf_path:
            raise FileNotFoundError("PDF path not allowed")

        from .local_file_store import UPLOADS_BASE_DIR
        allowed_roots = [Path(tempfile.gettempdir()).resolve(), UPLOADS_BASE_DIR.resolve()]

        candidate = Path(pdf_path).expanduser()
        resolved: Optional[Path] = None

        def _is_under_root(path: Path, root: Path) -> bool:
            try:
                return path.is_relative_to(root)
            except AttributeError:
                try:
                    return Path(os.path.commonpath([path, root])) == root
                except (ValueError, OSError):
                    return False

        if candidate.is_absolute():
            try:
                abs_path = candidate.resolve()
            except (ValueError, OSError):
                raise FileNotFoundError("PDF path not allowed")
            if any(_is_under_root(abs_path, root) for root in allowed_roots):
                resolved = abs_path
        else:
            for root in allowed_roots:
                try_path = (root / candidate).resolve()
                if _is_under_root(try_path, root):
                    resolved = try_path
                    break

        if not resolved or not resolved.is_file():
            raise FileNotFoundError("PDF not found")

        return resolved
    
    def _split_text_into_chunks(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Split text into chunks deterministically.
        
        Args:
            text: Text to split.
            chunk_size: Size of each chunk (characters).
            overlap: Overlap between chunks (characters).
        
        Returns:
            List of text chunks.
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            
            # Move start position with overlap
            start = end - overlap
            if start >= len(text):
                break
        
        return chunks
    
    def _generate_chunk_id(self, file_hash: str, page_number: int, chunk_index: int) -> str:
        """Generate deterministic chunk ID.
        
        Args:
            file_hash: File hash.
            page_number: Page number (1-based).
            chunk_index: Chunk index within page.
        
        Returns:
            Deterministic chunk ID (SHA256 hex digest).
        """
        normalized = f"{file_hash}|{page_number}|{chunk_index}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    
    def _extract_chunk_bbox(
        self,
        page: Any,  # pymupdf.Page
        chunk_index: int,
        total_chunks: int,
    ) -> Optional[Dict[str, float]]:
        """Extract bounding box for a chunk (approximate).
        
        Args:
            page: pymupdf Page object.
            chunk_index: Index of chunk within page.
            total_chunks: Total number of chunks on this page.
        
        Returns:
            Bounding box dict with {x, y, w, h} or None if unavailable.
        """
        try:
            # Get page dimensions
            page_rect = page.rect
            
            # Approximate chunk position based on index
            # Divide page vertically by chunk count
            chunk_height = page_rect.height / total_chunks if total_chunks > 0 else page_rect.height
            y_start = chunk_index * chunk_height
            y_end = min((chunk_index + 1) * chunk_height, page_rect.height)
            
            return {
                "x": 0.0,
                "y": float(y_start),
                "w": float(page_rect.width),
                "h": float(y_end - y_start),
            }
        except Exception as e:
            logger.warning(f"Failed to extract chunk bbox: {e}", exc_info=True)
            return None
    
    def get_chunk_count(
        self,
        project_id: Optional[str] = None,
        file_hash: Optional[str] = None,
        ingestion_id: Optional[str] = None,
    ) -> int:
        """Get chunk count for a project, file, or ingestion.
        
        Args:
            project_id: Project ID to filter by (REQUIRED for security).
            file_hash: Optional file hash to filter by.
            ingestion_id: Optional ingestion ID to filter by.
        
        Returns:
            Number of chunks matching filters.
        """
        if not QDRANT_AVAILABLE:
            return 0
        
        try:
            # Build filter conditions - project_id is REQUIRED
            filter_conditions = []
            
            if project_id:
                filter_conditions.append(
                    FieldCondition(key="project_id", match=MatchValue(value=project_id))
                )
            else:
                # Security: If no project_id provided, return 0 to prevent global queries
                logger.warning("get_chunk_count called without project_id - returning 0 for security")
                return 0
            
            if file_hash:
                filter_conditions.append(
                    FieldCondition(key="file_hash", match=MatchValue(value=file_hash))
                )
            
            if ingestion_id:
                filter_conditions.append(
                    FieldCondition(key="ingestion_id", match=MatchValue(value=ingestion_id))
                )
            
            # Create Filter object
            query_filter = Filter(must=filter_conditions) if filter_conditions else None
            
            # Count points
            count_result = self.client.count(
                collection_name=self.collection_name,
                count_filter=query_filter,
            )
            
            return count_result.count if hasattr(count_result, "count") else 0
        except Exception as e:
            logger.warning(f"Failed to get chunk count: {e}", exc_info=True)
            return 0
    
    def is_indexed(self, project_id: str, ingestion_id: str) -> bool:
        """Check if ingestion is indexed in Qdrant.
        
        Args:
            project_id: Project ID (REQUIRED for security).
            ingestion_id: Ingestion identifier.
        
        Returns:
            True if chunks exist for this ingestion_id in the project.
        """
        try:
            count = self.get_chunk_count(project_id=project_id, ingestion_id=ingestion_id)
            return count > 0
        except Exception:
            return False
    
    def retrieve_chunks_by_query(
        self,
        query_text: str,
        project_id: str,  # REQUIRED - must not be None
        ingestion_id: Optional[str] = None,
        file_hashes: Optional[List[str]] = None,  # Optional list of file_hashes to filter by
        limit: int = 5,
        query_vector: Optional[List[float]] = None,
        top_k_embed: Optional[int] = None,  # Number of chunks to retrieve from Qdrant (before reranking)
        top_k_rerank: Optional[int] = None,  # Number of chunks to return after reranking (default: limit)
        use_reranker: Optional[bool] = None,  # Whether to use reranker (None = use global default from config)
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks from Qdrant using semantic search, optionally reranked.
        
        Flow: Embed query → Qdrant search (top-K) → Rerank (top-M) → Return
        
        Security: ALWAYS filters by project_id to prevent global retrieval.
        Can optionally filter by ingestion_id or a list of file_hashes.
        
        Args:
            query_text: Text query for semantic search (used to generate embedding if query_vector not provided).
            project_id: Project ID to filter by (REQUIRED for security).
            ingestion_id: Optional ingestion ID to filter by.
            file_hashes: Optional list of file hashes to filter by (alternative to ingestion_id).
            limit: Maximum number of chunks to return (default 5). Used as top_k_rerank if not specified.
            query_vector: Optional pre-computed embedding vector. If None, will need to be generated.
            top_k_embed: Number of chunks to retrieve from Qdrant before reranking (default: 64 if reranker enabled, else limit).
            top_k_rerank: Number of chunks to return after reranking (default: limit).
            use_reranker: Whether to use reranker service.
                - None: Use global default from RERANKER_ENABLED config
                - True: Use reranker (if enabled in config)
                - False: Never use reranker
        
        Returns:
            List of dictionaries, each representing a retrieved chunk with:
            - chunk_id: str
            - text_content: str (from payload)
            - payload: Dict with file_hash, ingestion_id, page_number, bbox, etc.
            - score: float (relevance score, rerank_score if reranker used)
            - rerank_score: Optional[float] (reranker score if reranker used)
            - rerank_rank: Optional[int] (reranker rank if reranker used)
        """
        if not QDRANT_AVAILABLE:
            logger.warning("Qdrant client not available. Returning empty list for retrieval.")
            return []
        
        try:
            # If query_vector not provided, generate embedding
            if query_vector is None:
                # Try to get embedding from embedder service
                try:
                    from ...shared.config import get_embedder_url
                    import requests
                    
                    embedder_url = get_embedder_url()
                    if embedder_url:
                        response = requests.post(
                            f"{embedder_url}/embed",
                            json={"texts": [query_text]},
                            timeout=10
                        )
                        response.raise_for_status()
                        embeddings_data = response.json()
                        query_vector = embeddings_data.get("embeddings", [None])[0]
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for query: {e}", exc_info=True)
                    # Fallback: use zero vector (will return random results)
                    query_vector = [0.0] * EMBEDDING_DIMENSION
            
            if query_vector is None:
                logger.warning("No query vector available, using zero vector")
                query_vector = [0.0] * EMBEDDING_DIMENSION
            
            # Build filter for project_id (REQUIRED) and optional ingestion_id/file_hashes
            # Security: ALWAYS filter by project_id to prevent global retrieval
            if not project_id:
                logger.error("retrieve_chunks_by_query called without project_id - refusing global query")
                return []
            
            filter_conditions = [
                FieldCondition(key="project_id", match=MatchValue(value=project_id))
            ]
            
            if ingestion_id:
                filter_conditions.append(
                    FieldCondition(key="ingestion_id", match=MatchValue(value=ingestion_id))
                )
            
            # If file_hashes provided, filter by them (alternative to ingestion_id)
            if file_hashes and isinstance(file_hashes, list) and len(file_hashes) > 0:
                # Use "should" for OR condition (match any of the file_hashes)
                from qdrant_client.models import Should
                file_hash_conditions = [
                    FieldCondition(key="file_hash", match=MatchValue(value=fh))
                    for fh in file_hashes
                ]
                # Wrap in a "should" condition (at least one must match)
                filter_conditions.append(
                    Should(conditions=file_hash_conditions, min_count=1)
                )
            
            # Create Filter object - project_id is ALWAYS required
            query_filter = Filter(must=filter_conditions) if filter_conditions else None
            
            # Import reranker config (needed for both None check and global disable check)
            from ...shared.config import RERANKER_ENABLED
            
            # Determine reranker usage:
            # - Default: False (do NOT rerank by default - callers must opt-in)
            # - Only use reranker if explicitly requested AND globally enabled
            if use_reranker is None:
                use_reranker = False  # Default: no reranking (callers must opt-in)
            
            # If reranker is disabled globally, never use it (even if caller requested it)
            if use_reranker and not RERANKER_ENABLED:
                logger.debug(
                    "Reranker requested but RERANKER_ENABLED=false, falling back to embed-only",
                    extra={"payload": {"project_id": project_id, "ingestion_id": ingestion_id}}
                )
                use_reranker = False
            
            # Determine retrieval limits
            # Only expand top-K when reranking is actually enabled and will be used
            # This prevents unnecessary expansion when reranker is disabled
            if use_reranker:
                embed_limit = top_k_embed if top_k_embed is not None else 64  # Default: retrieve 64, rerank to limit
                rerank_limit = top_k_rerank if top_k_rerank is not None else limit
            else:
                # No reranking: use caller's limit directly, no expansion
                embed_limit = limit
                rerank_limit = limit
            
            # Search Qdrant
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=embed_limit,
                with_payload=True,
            )
            
            # Format results
            chunks = []
            for hit in search_result:
                payload = hit.payload or {}
                chunk = {
                    "chunk_id": str(hit.id),
                    "text_content": payload.get("text_content", ""),
                    "payload": payload,
                    "score": hit.score,
                    "file_hash": payload.get("file_hash"),
                    "ingestion_id": payload.get("ingestion_id"),
                    "page_number": payload.get("page_number"),
                    "bbox": payload.get("bbox"),
                    "chunk_index": payload.get("chunk_index"),
                }
                chunks.append(chunk)
            
            # Rerank if enabled and we have chunks
            if use_reranker and chunks:
                try:
                    from ...shared.reranker_client import rerank_chunks
                    reranked_chunks = rerank_chunks(
                        query=query_text,
                        chunks=chunks,
                        top_k=rerank_limit,
                        timeout=30
                    )
                    chunks = reranked_chunks
                    logger.debug(
                        f"Reranked {len(chunks)} chunks (from {embed_limit} candidates)",
                        extra={
                            "query": query_text[:100],
                            "embed_limit": embed_limit,
                            "rerank_limit": rerank_limit,
                            "returned": len(chunks),
                        }
                    )
                except Exception as e:
                    # Degraded behavior: if reranker fails, check if it's required
                    from ...shared.config import RERANKER_REQUIRED
                    if RERANKER_REQUIRED:
                        logger.error(
                            f"Reranker is required but failed: {e}",
                            exc_info=True
                        )
                        raise ValueError(f"Reranker is required but unavailable: {e}") from e
                    else:
                        logger.warning(
                            f"Reranker failed, falling back to embed-only: {e}",
                            exc_info=True
                        )
                        # Fallback: return top-M by embedding score
                        chunks = chunks[:rerank_limit]
            else:
                # No reranking: return top-M by embedding score
                chunks = chunks[:rerank_limit]
            
            logger.debug(
                f"Retrieved {len(chunks)} chunks from Qdrant",
                extra={
                    "payload": {
                        "project_id": project_id,
                        "ingestion_id": ingestion_id,
                        "query_length": len(query_text),
                        "use_reranker": use_reranker,
                        "embed_limit": embed_limit,
                        "rerank_limit": rerank_limit,
                    }
                }
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to retrieve chunks from Qdrant: {e}", exc_info=True)
            return []
    
    def get_chunks_by_ids(
        self,
        chunk_ids: List[str],
        project_id: str,
    ) -> List[Dict[str, Any]]:
        """Retrieve chunks by their IDs from Qdrant.
        
        Args:
            chunk_ids: List of chunk IDs to retrieve.
            project_id: Project ID (REQUIRED for security - validates chunks belong to project).
        
        Returns:
            List of dictionaries, each representing a chunk with:
            - chunk_id: str
            - text_content: str (from payload or text field)
            - page_number: int (from payload)
            - file_hash: str (from payload)
            - ingestion_id: str (from payload)
            - chunk_index: int (from payload)
            - bbox: Optional[Dict] (from payload)
        """
        if not QDRANT_AVAILABLE:
            logger.warning("Qdrant not available, cannot retrieve chunks by IDs")
            return []
        
        if not chunk_ids:
            return []
        
        try:
            # Convert chunk IDs to appropriate format (Qdrant expects int or str)
            # Chunk IDs are SHA256 hashes (hex strings), so we can use them directly
            point_ids = chunk_ids
            
            # Retrieve points by IDs
            retrieved_points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=point_ids,
                with_payload=True,
            )
            
            # Format results and validate project_id
            chunks = []
            for point in retrieved_points:
                payload = point.payload or {}
                
                # Security: Validate project_id matches
                chunk_project_id = payload.get("project_id")
                if chunk_project_id != project_id:
                    logger.warning(
                        f"Chunk {point.id} belongs to project {chunk_project_id}, not {project_id} - skipping",
                        extra={"payload": {"chunk_id": str(point.id), "chunk_project_id": chunk_project_id, "requested_project_id": project_id}}
                    )
                    continue
                
                # Extract text content (may be in payload.text_content or payload.text)
                text_content = payload.get("text_content") or payload.get("text", "")
                
                # Build chunk metadata
                chunk = {
                    "chunk_id": str(point.id),
                    "text_content": text_content,
                    "page_number": payload.get("page_number"),
                    "file_hash": payload.get("file_hash"),
                    "ingestion_id": payload.get("ingestion_id"),
                    "chunk_index": payload.get("chunk_index"),
                    "bbox": payload.get("bbox"),
                }
                chunks.append(chunk)
            
            logger.debug(
                f"Retrieved {len(chunks)} chunks by IDs from Qdrant",
                extra={"payload": {"requested_count": len(chunk_ids), "retrieved_count": len(chunks), "project_id": project_id}}
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to retrieve chunks by IDs from Qdrant: {e}", exc_info=True)
            return []
