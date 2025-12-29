"""
PDF processing utilities for Project Vyasa ingestion.

Uses pymupdf4llm to convert PDFs to Markdown, preserving structure, tables,
and formulas as much as possible for downstream Cortex extraction.
"""

import os
from pathlib import Path
from typing import Optional, Tuple, List
import tempfile

import pymupdf4llm

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
    pdf_path = Path(file_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    images_dir: Optional[Path] = None
    if output_image_dir:
        images_dir = Path(output_image_dir)
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
