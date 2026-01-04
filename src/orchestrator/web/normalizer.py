"""
Evidence Normalizer for Project Vyasa.

Maps Firecrawl scrape results and PDF chunks to NormalizedEvidenceUnit,
providing a unified interface for Worker extraction regardless of source type.
"""

import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from ..schemas.evidence import NormalizedEvidenceUnit, ProvenanceType
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)


class EvidenceNormalizer:
    """Normalizes evidence from different sources to NormalizedEvidenceUnit.
    
    Provides deterministic mapping from Firecrawl results and PDF chunks
    to a unified evidence format that Worker extraction can process uniformly.
    """
    
    @staticmethod
    def normalize_web(firecrawl_item: Dict[str, Any]) -> NormalizedEvidenceUnit:
        """Normalize a Firecrawl scrape result to NormalizedEvidenceUnit.
        
        Args:
            firecrawl_item: Firecrawl scrape result dictionary with:
                - url: Original URL (required)
                - domain: Extracted domain
                - title: Page title (optional)
                - markdown: Scraped content in markdown format (required)
                - retrieved_at: ISO timestamp (optional)
                - error: Error message if scraping failed (optional)
        
        Returns:
            NormalizedEvidenceUnit with:
                - content: markdown content
                - provenance_type: WEB
                - provenance_metadata: includes url, domain, title, headers if present
                - content_hash: SHA256 hash of content
        
        Raises:
            ValueError: If firecrawl_item is missing required fields or has an error
        """
        # Check for errors
        if firecrawl_item.get("error"):
            raise ValueError(f"Firecrawl item has error: {firecrawl_item.get('error')}")
        
        # Extract required fields
        url = firecrawl_item.get("url")
        if not url:
            raise ValueError("firecrawl_item must include 'url'")
        
        markdown = firecrawl_item.get("markdown", "")
        if not markdown:
            logger.warning(f"Firecrawl item for {url} has empty markdown content")
        
        # Extract optional fields
        domain = firecrawl_item.get("domain")
        title = firecrawl_item.get("title")
        retrieved_at_str = firecrawl_item.get("retrieved_at")
        
        # Parse retrieved_at if provided
        retrieval_timestamp: Optional[datetime] = None
        if retrieved_at_str:
            try:
                # Try parsing ISO format
                if isinstance(retrieved_at_str, str):
                    if "T" in retrieved_at_str:
                        # ISO format with T separator
                        retrieval_timestamp = datetime.fromisoformat(
                            retrieved_at_str.replace("Z", "+00:00")
                        )
                    else:
                        # Fallback: try parsing as timestamp
                        retrieval_timestamp = datetime.fromtimestamp(
                            float(retrieved_at_str), tz=timezone.utc
                        )
                elif isinstance(retrieved_at_str, (int, float)):
                    retrieval_timestamp = datetime.fromtimestamp(
                        float(retrieved_at_str), tz=timezone.utc
                    )
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse retrieved_at '{retrieved_at_str}': {e}")
                retrieval_timestamp = None
        
        # Build provenance metadata
        provenance_metadata: Dict[str, Any] = {
            "url": url,
        }
        
        if domain:
            provenance_metadata["domain"] = domain
        
        if title:
            provenance_metadata["title"] = title
        
        # Include headers if present in firecrawl_item
        if "headers" in firecrawl_item:
            provenance_metadata["headers"] = firecrawl_item["headers"]
        
        # Create NormalizedEvidenceUnit
        return NormalizedEvidenceUnit.create(
            content=markdown,
            provenance_type=ProvenanceType.WEB,
            provenance_metadata=provenance_metadata,
            retrieval_timestamp=retrieval_timestamp,
        )
    
    @staticmethod
    def normalize_pdf(pdf_chunk: Dict[str, Any]) -> NormalizedEvidenceUnit:
        """Normalize a PDF chunk to NormalizedEvidenceUnit.
        
        Args:
            pdf_chunk: PDF chunk dictionary with:
                - text: Extracted text content (required)
                - doc_hash: Document hash (required)
                - doc_id: Document ID (optional, used if doc_hash not present)
                - page_number: Page number (optional)
                - bbox: Bounding box [x0, y0, x1, y1] (optional)
                - span: Text span information (optional)
        
        Returns:
            NormalizedEvidenceUnit with:
                - content: extracted text chunk
                - provenance_type: PDF
                - provenance_metadata: includes doc_hash, page_number, bbox/span if present
                - content_hash: SHA256 hash of content
        
        Raises:
            ValueError: If pdf_chunk is missing required fields
        """
        # Extract required fields
        text = pdf_chunk.get("text") or pdf_chunk.get("content", "")
        if not text:
            raise ValueError("pdf_chunk must include 'text' or 'content'")
        
        # Extract doc_hash (required for PDF)
        doc_hash = pdf_chunk.get("doc_hash") or pdf_chunk.get("doc_id")
        if not doc_hash:
            raise ValueError("pdf_chunk must include 'doc_hash' or 'doc_id'")
        
        # Extract optional fields
        page_number = pdf_chunk.get("page_number") or pdf_chunk.get("page")
        bbox = pdf_chunk.get("bbox")
        span = pdf_chunk.get("span")
        
        # Parse retrieval timestamp if provided
        retrieval_timestamp: Optional[datetime] = None
        retrieved_at = pdf_chunk.get("retrieved_at") or pdf_chunk.get("timestamp")
        if retrieved_at:
            try:
                if isinstance(retrieved_at, str):
                    if "T" in retrieved_at:
                        retrieval_timestamp = datetime.fromisoformat(
                            retrieved_at.replace("Z", "+00:00")
                        )
                    else:
                        retrieval_timestamp = datetime.fromtimestamp(
                            float(retrieved_at), tz=timezone.utc
                        )
                elif isinstance(retrieved_at, (int, float)):
                    retrieval_timestamp = datetime.fromtimestamp(
                        float(retrieved_at), tz=timezone.utc
                    )
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse retrieved_at '{retrieved_at}': {e}")
                retrieval_timestamp = None
        
        # Build provenance metadata
        provenance_metadata: Dict[str, Any] = {
            "doc_hash": doc_hash,
        }
        
        if page_number is not None:
            provenance_metadata["page_number"] = page_number
        
        if bbox is not None:
            # Validate bbox format (should be list of 4 numbers)
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                provenance_metadata["bbox"] = list(bbox)
            else:
                logger.warning(f"Invalid bbox format in pdf_chunk: {bbox}")
        
        if span is not None:
            provenance_metadata["span"] = span
        
        # Include doc_id if different from doc_hash
        if pdf_chunk.get("doc_id") and pdf_chunk.get("doc_id") != doc_hash:
            provenance_metadata["doc_id"] = pdf_chunk.get("doc_id")
        
        # Create NormalizedEvidenceUnit
        return NormalizedEvidenceUnit.create(
            content=text,
            provenance_type=ProvenanceType.PDF,
            provenance_metadata=provenance_metadata,
            retrieval_timestamp=retrieval_timestamp,
        )

