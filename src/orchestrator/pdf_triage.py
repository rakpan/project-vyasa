"""
PDF triage utilities for vision detection.

Lightweight triage to detect scanned/image-heavy PDFs that would benefit from vision processing.
"""

from pathlib import Path
from typing import Dict, Any, Optional

try:
    import pymupdf
except ImportError:
    pymupdf = None

from ..shared.logger import get_logger
from ..shared.config import VISION_TRIAGE_PAGES, VISION_MIN_TEXT_CHARS

logger = get_logger("orchestrator", __name__)


def triage_pdf(pdf_path: str, triage_pages: Optional[int] = None, min_text_chars: Optional[int] = None) -> Dict[str, Any]:
    """
    Perform lightweight triage on PDF to detect if it's likely scanned/image-heavy.
    
    Extracts text preview from first N pages and computes character count.
    If preview_text_chars < min_text_chars, the PDF is considered likely_scanned.
    
    Args:
        pdf_path: Path to PDF file
        triage_pages: Number of pages to preview (defaults to VISION_TRIAGE_PAGES)
        min_text_chars: Minimum text chars to consider PDF text-based (defaults to VISION_MIN_TEXT_CHARS)
    
    Returns:
        Dictionary with:
        - likely_scanned: bool
        - preview_text_chars: int
        - pages_previewed: int
    """
    if pymupdf is None:
        logger.warning("pymupdf not available, cannot perform PDF triage")
        return {
            "likely_scanned": False,
            "preview_text_chars": 0,
            "pages_previewed": 0,
        }
    
    triage_pages = triage_pages or VISION_TRIAGE_PAGES
    min_text_chars = min_text_chars or VISION_MIN_TEXT_CHARS
    
    try:
        pdf_path_obj = Path(pdf_path).expanduser().resolve()
        if not pdf_path_obj.exists():
            logger.warning(f"PDF not found for triage: {pdf_path}")
            return {
                "likely_scanned": False,
                "preview_text_chars": 0,
                "pages_previewed": 0,
            }
        
        doc = pymupdf.open(str(pdf_path_obj))
        total_pages = len(doc)
        pages_to_preview = min(triage_pages, total_pages)
        
        preview_text_parts = []
        for page_num in range(pages_to_preview):
            page_obj = doc[page_num]
            page_text = page_obj.get_text()
            if page_text:
                preview_text_parts.append(page_text)
        
        doc.close()
        
        preview_text = "".join(preview_text_parts)
        preview_text_chars = len(preview_text)
        likely_scanned = preview_text_chars < min_text_chars
        
        logger.debug(
            "PDF triage complete",
            extra={
                "payload": {
                    "pdf_path": str(pdf_path_obj),
                    "likely_scanned": likely_scanned,
                    "preview_text_chars": preview_text_chars,
                    "pages_previewed": pages_to_preview,
                    "total_pages": total_pages,
                }
            }
        )
        
        return {
            "likely_scanned": likely_scanned,
            "preview_text_chars": preview_text_chars,
            "pages_previewed": pages_to_preview,
        }
    except Exception as e:
        logger.warning(f"PDF triage failed: {e}", exc_info=True)
        return {
            "likely_scanned": False,
            "preview_text_chars": 0,
            "pages_previewed": 0,
        }
