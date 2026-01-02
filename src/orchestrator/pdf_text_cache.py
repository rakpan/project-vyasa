"""
PDF Text Cache Service for Project Vyasa.

Stores and retrieves PDF text layers by doc_hash and page number.
This enables real evidence verification in the Critic node.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional, Dict

try:
    import pymupdf
except ImportError:
    pymupdf = None

from ..shared.logger import get_logger
from ..shared.config import get_memory_url, get_arango_password, ARANGODB_DB, ARANGODB_USER

logger = get_logger("orchestrator", __name__)

# Cache directory for PDF text layers
CACHE_DIR = Path("/tmp/vyasa_pdf_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _get_cache_key(doc_hash: str, page: int) -> str:
    """Generate cache key for doc_hash + page."""
    key_str = f"{doc_hash}:{page}"
    return hashlib.sha256(key_str.encode()).hexdigest()


def store_page_text(doc_hash: str, page: int, text: str, pdf_path: Optional[str] = None) -> None:
    """
    Store page text in cache (file system + ArangoDB).
    
    Args:
        doc_hash: SHA256 hash of the PDF document
        page: 1-based page number
        text: Extracted text from the page
        pdf_path: Optional path to PDF file for fallback retrieval
    """
    try:
        # Store in file cache
        cache_key = _get_cache_key(doc_hash, page)
        cache_file = CACHE_DIR / f"{cache_key}.txt"
        cache_file.write_text(text, encoding="utf-8")
        
        # Store in ArangoDB for persistence
        try:
            from arango import ArangoClient
            client = ArangoClient(hosts=get_memory_url())
            db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
            
            if not db.has_collection("pdf_text_cache"):
                db.create_collection("pdf_text_cache")
            
            cache_col = db.collection("pdf_text_cache")
            cache_col.insert({
                "_key": cache_key,
                "doc_hash": doc_hash,
                "page": page,
                "text": text,
                "pdf_path": pdf_path,
            }, overwrite=True)
        except Exception as e:
            logger.warning(f"Failed to store page text in ArangoDB: {e}", exc_info=True)
            # Continue with file cache only
        
        logger.debug(f"Stored page text", extra={"payload": {"doc_hash": doc_hash[:16], "page": page}})
    except Exception as e:
        logger.error(f"Failed to store page text: {e}", exc_info=True)
        raise


def load_page_text(doc_hash: str, page: int, pdf_path: Optional[str] = None) -> str:
    """
    Load page text from cache or extract from PDF.
    
    Args:
        doc_hash: SHA256 hash of the PDF document
        page: 1-based page number (1-indexed)
        pdf_path: Optional path to PDF file for extraction if cache miss
    
    Returns:
        Text content of the page
    
    Raises:
        ValueError: If page text cannot be retrieved and pdf_path is not provided
    """
    cache_key = _get_cache_key(doc_hash, page)
    
    # Try file cache first
    cache_file = CACHE_DIR / f"{cache_key}.txt"
    if cache_file.exists():
        try:
            text = cache_file.read_text(encoding="utf-8")
            logger.debug(f"Loaded page text from file cache", extra={"payload": {"doc_hash": doc_hash[:16], "page": page}})
            return text
        except Exception as e:
            logger.warning(f"Failed to read file cache: {e}", exc_info=True)
    
    # Try ArangoDB cache
    try:
        from arango import ArangoClient
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
        
        if db.has_collection("pdf_text_cache"):
            cache_col = db.collection("pdf_text_cache")
            doc = cache_col.get(cache_key)
            if doc and doc.get("text"):
                text = doc["text"]
                # Also write to file cache for faster access
                try:
                    cache_file.write_text(text, encoding="utf-8")
                except Exception:
                    pass
                logger.debug(f"Loaded page text from ArangoDB cache", extra={"payload": {"doc_hash": doc_hash[:16], "page": page}})
                return text
    except Exception as e:
        logger.warning(f"Failed to load from ArangoDB cache: {e}", exc_info=True)
    
    # Fallback: Extract from PDF if path provided
    if pdf_path and Path(pdf_path).exists():
        if pymupdf is None:
            raise ValueError("pymupdf not available for PDF text extraction")
        try:
            doc = pymupdf.open(pdf_path)
            if 1 <= page <= len(doc):
                page_obj = doc[page - 1]  # pymupdf uses 0-indexed
                text = page_obj.get_text()
                doc.close()
                
                # Store in cache for future use
                store_page_text(doc_hash, page, text, pdf_path)
                logger.info(f"Extracted and cached page text from PDF", extra={"payload": {"doc_hash": doc_hash[:16], "page": page}})
                return text
            else:
                raise ValueError(f"Page {page} out of range (document has {len(doc)} pages)")
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}", exc_info=True)
            raise ValueError(f"Cannot retrieve page text: {e}") from e
    
    # No cache and no PDF path
    raise ValueError(
        f"Page text not found in cache for doc_hash={doc_hash[:16]}... page={page}. "
        "Provide pdf_path to extract from source PDF."
    )
