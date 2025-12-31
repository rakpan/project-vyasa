"""
PDF processing utilities for Project Vyasa ingestion.

Uses pymupdf4llm to convert PDFs to Markdown, preserving structure, tables,
and formulas as much as possible for downstream Cortex extraction.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import pymupdf4llm
from werkzeug.utils import secure_filename

from ..shared.logger import get_logger

logger = get_logger("orchestrator", __name__)


def process_pdf(file_path: str, output_image_dir: Optional[str] = None) -> Tuple[str, Optional[Path], List[str]]:
    """
    Convert a PDF to Markdown using pymupdf4llm.

    Args:
        file_path: Path to the PDF file.
        output_image_dir: Optional directory to save extracted images. If provided,
                          images will be written there and placeholders will be
                          inserted into the markdown as ![Diagram N](relative_path).

    Returns:
        A tuple of (markdown_text, images_dir_path or None, image_paths).
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

    try:
        logger.info(f"Processing PDF: {pdf_path.name}")
        markdown_text = pymupdf4llm.to_markdown(
            str(pdf_path),
            write_images=bool(images_dir),
            image_path=str(images_dir) if images_dir else None,
        )

        placeholders = []
        image_paths: List[str] = []
        if images_dir and images_dir.exists():
            for idx, image_path in enumerate(images_dir.glob("*")):
                if image_path.is_file():
                    placeholders.append(f"![Diagram {idx + 1}]({image_path.name})")
                    image_paths.append(str(image_path))
            if placeholders:
                markdown_text += "\n\n" + "\n".join(placeholders)
        logger.info("PDF conversion complete", extra={"payload": {"file": pdf_path.name}})
        return markdown_text, images_dir, image_paths
    except Exception:
        logger.error(
            "Failed to process PDF",
            extra={"payload": {"file": pdf_path.name}},
            exc_info=True,
        )
        raise
