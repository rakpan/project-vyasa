"""
PDF processing utilities for Project Vyasa ingestion.

Uses pymupdf4llm to convert PDFs to Markdown, preserving structure, tables,
and formulas as much as possible for downstream Cortex extraction.

Falls back to direct pymupdf text extraction if pymupdf4llm returns empty or
near-empty text (e.g., for PDFs with text layers that pymupdf4llm misses).
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import pymupdf4llm
from werkzeug.utils import secure_filename

# Import pymupdf for fallback extraction
try:
    import pymupdf
except ImportError:
    pymupdf = None

from ..shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

# Threshold for considering text "near-empty": less than 10 chars per page
MIN_CHARS_PER_PAGE = 10


def process_pdf(file_path: str, output_image_dir: Optional[str] = None) -> Tuple[str, Optional[Path], List[str]]:
    """
    Convert a PDF to Markdown using pymupdf4llm with fallback to direct pymupdf extraction.

    Args:
        file_path: Path to the PDF file.
        output_image_dir: Optional directory to save extracted images. If provided,
                          images will be written there and placeholders will be
                          inserted into the markdown as ![Diagram N](relative_path).

    Returns:
        A tuple of (markdown_text, images_dir_path or None, image_paths).

    Raises:
        FileNotFoundError: If PDF file doesn't exist.
        ValueError: If file is not a PDF or if PDF is image-only (no extractable text).
    """
    pdf_path = Path(file_path).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are supported")

    # Copy into a controlled temp directory to avoid path traversal/SSRF concerns
    safe_dir = Path(tempfile.mkdtemp(prefix="vyasa_pdf_safe_"))
    safe_pdf_path = safe_dir / secure_filename(pdf_path.name)
    shutil.copy2(pdf_path, safe_pdf_path)
    pdf_path = safe_pdf_path

    images_dir: Optional[Path] = None
    if output_image_dir:
        candidate = Path(output_image_dir).expanduser().resolve()
        tmp_base = Path(tempfile.gettempdir()).resolve()
        # Restrict image output to temp space to prevent writing to arbitrary paths
        if candidate == tmp_base or tmp_base in candidate.parents:
            images_dir = candidate
        else:
            images_dir = Path(tempfile.mkdtemp(prefix="vyasa_pdf_images_"))
    else:
        images_dir = Path(tempfile.mkdtemp(prefix="vyasa_pdf_images_"))
    images_dir.mkdir(parents=True, exist_ok=True)

    # Get page count for logging and validation
    page_count = 0
    try:
        if pymupdf is not None:
            doc = pymupdf.open(str(pdf_path))
            page_count = len(doc)
            doc.close()
        else:
            # Fallback: try to get page count from pymupdf4llm metadata
            # This is less reliable but better than nothing
            logger.warning("pymupdf not available, cannot get accurate page count")
    except Exception as e:
        logger.warning(f"Failed to get page count: {e}", exc_info=True)

    logger.info(
        "Processing PDF",
        extra={
            "payload": {
                "file": pdf_path.name,
                "pages_detected": page_count,
            }
        }
    )

    try:
        # Primary extraction: pymupdf4llm (preserves structure, tables, formulas)
        markdown_text = pymupdf4llm.to_markdown(
            str(pdf_path),
            write_images=bool(images_dir),
            image_path=str(images_dir) if images_dir else None,
        )
        
        primary_text_length = len(markdown_text) if markdown_text else 0
        logger.info(
            "Primary extraction (pymupdf4llm) complete",
            extra={
                "payload": {
                    "file": pdf_path.name,
                    "text_length": primary_text_length,
                    "pages_detected": page_count,
                }
            }
        )

        # Validate primary extraction: check if text is empty or near-empty
        # Threshold: less than MIN_CHARS_PER_PAGE chars per page, or absolute minimum of 100 chars
        min_expected_length = max(100, page_count * MIN_CHARS_PER_PAGE) if page_count > 0 else 100
        use_fallback = False
        
        if not markdown_text or not markdown_text.strip():
            logger.warning(
                "Primary extraction returned empty text, using fallback",
                extra={
                    "payload": {
                        "file": pdf_path.name,
                        "extraction_method": "pymupdf4llm",
                        "text_length": primary_text_length,
                    }
                }
            )
            use_fallback = True
        elif primary_text_length < min_expected_length:
            logger.warning(
                "Primary extraction returned near-empty text, using fallback",
                extra={
                    "payload": {
                        "file": pdf_path.name,
                        "extraction_method": "pymupdf4llm",
                        "text_length": primary_text_length,
                        "min_expected_length": min_expected_length,
                        "pages_detected": page_count,
                    }
                }
            )
            use_fallback = True

        # Fallback extraction: direct pymupdf page-by-page text extraction
        if use_fallback:
            if pymupdf is None:
                logger.error(
                    "Fallback extraction required but pymupdf not available",
                    extra={"payload": {"file": pdf_path.name}}
                )
                raise ValueError(
                    "PDF text extraction failed: pymupdf4llm returned empty text and pymupdf is not available for fallback"
                )
            
            logger.info(
                "Starting fallback extraction (direct pymupdf)",
                extra={"payload": {"file": pdf_path.name}}
            )
            
            doc = pymupdf.open(str(pdf_path))
            fallback_text_parts: List[str] = []
            
            for page_num in range(len(doc)):
                page_obj = doc[page_num]
                page_text = page_obj.get_text()
                if page_text and page_text.strip():
                    fallback_text_parts.append(f"## Page {page_num + 1}\n\n{page_text.strip()}")
            
            doc.close()
            
            fallback_text = "\n\n".join(fallback_text_parts)
            fallback_text_length = len(fallback_text) if fallback_text else 0
            
            logger.info(
                "Fallback extraction complete",
                extra={
                    "payload": {
                        "file": pdf_path.name,
                        "text_length": fallback_text_length,
                        "pages_extracted": len(fallback_text_parts),
                        "pages_detected": page_count,
                    }
                }
            )
            
            # Validate fallback extraction
            if not fallback_text or not fallback_text.strip():
                logger.error(
                    "Fallback extraction also returned empty text - PDF may be image-only",
                    extra={
                        "payload": {
                            "file": pdf_path.name,
                            "pages_detected": page_count,
                            "primary_length": primary_text_length,
                            "fallback_length": fallback_text_length,
                        }
                    }
                )
                raise ValueError(
                    f"PDF appears to be image-only or unreadable: no extractable text found "
                    f"(primary extraction: {primary_text_length} chars, fallback: {fallback_text_length} chars, "
                    f"pages: {page_count})"
                )
            
            markdown_text = fallback_text

        # Add image placeholders if images were extracted
        placeholders = []
        image_paths: List[str] = []
        if images_dir and images_dir.exists():
            for idx, image_path in enumerate(images_dir.glob("*")):
                if image_path.is_file():
                    placeholders.append(f"![Diagram {idx + 1}]({image_path.name})")
                    image_paths.append(str(image_path))
            if placeholders:
                markdown_text += "\n\n" + "\n".join(placeholders)

        final_text_length = len(markdown_text) if markdown_text else 0
        
        # Final validation: ensure we have non-empty text
        if not markdown_text or not markdown_text.strip():
            logger.error(
                "Final extracted text is empty after all extraction methods",
                extra={
                    "payload": {
                        "file": pdf_path.name,
                        "pages_detected": page_count,
                        "used_fallback": use_fallback,
                    }
                }
            )
            raise ValueError(
                f"PDF text extraction failed: no extractable text found (pages: {page_count}). "
                "PDF may be image-only or corrupted."
            )

        logger.info(
            "PDF conversion complete",
            extra={
                "payload": {
                    "file": pdf_path.name,
                    "final_text_length": final_text_length,
                    "used_fallback": use_fallback,
                    "extraction_method": "fallback" if use_fallback else "primary",
                    "pages_detected": page_count,
                }
            }
        )
        
        return markdown_text, images_dir, image_paths
        
    except ValueError:
        # Re-raise ValueError (our custom errors for image-only PDFs)
        raise
    except Exception as e:
        logger.error(
            "Failed to process PDF",
            extra={
                "payload": {
                    "file": pdf_path.name,
                    "pages_detected": page_count,
                }
            },
            exc_info=True,
        )
        raise
