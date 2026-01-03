"""
Deterministic First Glance computation for PDF documents.

This module provides functions to extract stable, repeatable metrics from PDFs
without relying on LLM outputs or non-deterministic heuristics.
"""

from typing import Dict, Any, Union
from pathlib import Path
import hashlib

from ..shared.logger import get_logger

logger = get_logger("orchestrator", __name__)


def compute_first_glance(pdf_input: Union[bytes, str, Path]) -> Dict[str, Any]:
    """Compute deterministic first glance metrics from a PDF.
    
    This function extracts stable metrics from PDF structure (pages, images, tables)
    without relying on LLM outputs or text parsing. The same PDF will always
    produce the same metrics.
    
    Args:
        pdf_input: PDF file as bytes, file path (str), or Path object.
    
    Returns:
        Dictionary with:
        - pages_count: int (number of pages)
        - text_density: float (characters per page, average)
        - tables_detected: int (heuristic count based on PDF structure)
        - figures_detected: int (count of images/figures in PDF)
    
    Raises:
        FileNotFoundError: If pdf_input is a path and file doesn't exist.
        ValueError: If pdf_input is invalid or PDF cannot be parsed.
    """
    try:
        import pymupdf
    except ImportError:
        logger.error("pymupdf not available for first glance computation")
        raise ValueError("pymupdf is required for first glance computation")
    
    # Handle different input types
    pdf_path: Optional[Path] = None
    pdf_bytes: Optional[bytes] = None
    
    if isinstance(pdf_input, bytes):
        pdf_bytes = pdf_input
    elif isinstance(pdf_input, (str, Path)):
        pdf_path = Path(pdf_input)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        pdf_bytes = pdf_path.read_bytes()
    else:
        raise ValueError(f"Invalid pdf_input type: {type(pdf_input)}")
    
    if not pdf_bytes:
        raise ValueError("Could not read PDF bytes")
    
    try:
        # Open PDF from bytes
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        
        # Extract pages_count (deterministic)
        pages_count = len(doc)
        
        # Extract text density (characters per page, average)
        total_chars = 0
        for page_num in range(pages_count):
            page = doc[page_num]
            text = page.get_text()
            total_chars += len(text)
        
        text_density = round(total_chars / pages_count, 2) if pages_count > 0 else 0.0
        
        # Count figures (images) - deterministic from PDF structure
        figures_detected = 0
        for page_num in range(pages_count):
            page = doc[page_num]
            # Get images on this page
            image_list = page.get_images()
            figures_detected += len(image_list)
        
        # Count tables - heuristic but deterministic
        # Strategy: Look for rectangular structures with multiple text blocks
        # that form a grid-like pattern (deterministic pattern matching)
        tables_detected = 0
        for page_num in range(pages_count):
            page = doc[page_num]
            
            # Get text blocks with their bounding boxes
            blocks = page.get_text("dict")["blocks"]
            
            # Look for table-like patterns:
            # - Multiple blocks aligned in rows/columns
            # - Blocks with similar y-coordinates (rows) or x-coordinates (columns)
            # - At least 3 blocks forming a grid
            
            text_blocks = [
                b for b in blocks
                if b.get("type") == 0  # Text block
            ]
            
            if len(text_blocks) < 3:
                continue
            
            # Group blocks by approximate y-coordinate (rows)
            # Tolerance: blocks within 5 pixels are considered same row
            rows: Dict[int, list] = {}
            for block in text_blocks:
                bbox = block.get("bbox", [0, 0, 0, 0])
                y_center = (bbox[1] + bbox[3]) / 2
                # Round to nearest 5 pixels for grouping
                row_key = int(y_center / 5) * 5
                if row_key not in rows:
                    rows[row_key] = []
                rows[row_key].append(block)
            
            # If we have at least 2 rows with at least 2 blocks each, likely a table
            rows_with_multiple_blocks = [
                row_blocks for row_blocks in rows.values()
                if len(row_blocks) >= 2
            ]
            
            if len(rows_with_multiple_blocks) >= 2:
                # Check if blocks are aligned in columns (x-coordinates similar)
                # Count distinct x-positions across rows
                x_positions = set()
                for row_blocks in rows_with_multiple_blocks:
                    for block in row_blocks:
                        bbox = block.get("bbox", [0, 0, 0, 0])
                        x_center = (bbox[0] + bbox[2]) / 2
                        x_positions.add(int(x_center / 10) * 10)  # Round to nearest 10 pixels
                
                # If we have multiple distinct x-positions, likely columns
                if len(x_positions) >= 2:
                    tables_detected += 1
        
        doc.close()
        
        return {
            "pages": pages_count,
            "text_density": text_density,
            "tables_detected": tables_detected,
            "figures_detected": figures_detected,
        }
        
    except Exception as e:
        logger.error(f"Failed to compute first glance: {e}", exc_info=True)
        raise ValueError(f"Failed to parse PDF for first glance: {e}") from e


def compute_first_glance_from_path(pdf_path: Union[str, Path]) -> Dict[str, Any]:
    """Convenience wrapper for compute_first_glance with file path.
    
    Args:
        pdf_path: Path to PDF file.
    
    Returns:
        First glance metrics dictionary.
    """
    return compute_first_glance(pdf_path)

