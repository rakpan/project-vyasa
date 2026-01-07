"""
Local File Store - Landing Zone for Persistent File Storage

Implements the "Land, Log, then Process" pattern:
- Files are saved to persistent disk before processing
- Enables retry logic even after server restarts
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# Base directory for uploads (relative to project root or absolute)
UPLOADS_BASE_DIR = Path(os.getenv("VYASA_UPLOADS_DIR", "./data/uploads")).expanduser().resolve()


class LocalFileStore:
    """Persistent file storage for uploaded PDFs.
    
    Files are organized by project_id and stored with UUID filenames
    to prevent collisions and enable secure access.
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize LocalFileStore.
        
        Args:
            base_dir: Base directory for uploads. Defaults to UPLOADS_BASE_DIR.
        """
        self.base_dir = base_dir or UPLOADS_BASE_DIR
        self._ensure_base_dir()
    
    def _ensure_base_dir(self) -> None:
        """Ensure base directory exists, create if missing."""
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured uploads directory exists: {self.base_dir}")
        except OSError as e:
            logger.error(f"Failed to create uploads directory {self.base_dir}: {e}", exc_info=True)
            raise RuntimeError(f"Cannot create uploads directory: {e}") from e
    
    def save_upload(self, file: FileStorage, project_id: str) -> str:
        """Save uploaded file to persistent storage.
        
        Args:
            file: Flask FileStorage object from request.files
            project_id: Project identifier for organizing files
        
        Returns:
            Absolute file path to saved file
        
        Raises:
            ValueError: If file is invalid
            OSError: If file cannot be written
        """
        if not file or not file.filename:
            raise ValueError("Invalid file: filename is required")
        
        # Validate file extension
        if not file.filename.lower().endswith(".pdf"):
            raise ValueError(f"Invalid file type: only PDF files are allowed, got {file.filename}")
        
        # Create project-specific directory
        project_dir = self.base_dir / project_id
        try:
            project_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create project directory {project_dir}: {e}", exc_info=True)
            raise RuntimeError(f"Cannot create project directory: {e}") from e
        
        # Generate secure filename: {uuid}.pdf
        file_uuid = str(uuid.uuid4())
        safe_filename = secure_filename(file.filename)
        # Use UUID as base name, preserve extension
        file_extension = Path(safe_filename).suffix or ".pdf"
        stored_filename = f"{file_uuid}{file_extension}"
        
        file_path = project_dir / stored_filename
        
        try:
            # Save file to disk
            file.save(str(file_path))
            logger.info(
                f"Saved upload to landing zone",
                extra={
                    "payload": {
                        "project_id": project_id,
                        "original_filename": file.filename,
                        "stored_path": str(file_path),
                        "file_size": file_path.stat().st_size if file_path.exists() else 0,
                    }
                }
            )
            return str(file_path.resolve())
        except OSError as e:
            logger.error(
                f"Failed to save file to {file_path}: {e}",
                exc_info=True,
                extra={"payload": {"project_id": project_id, "filename": file.filename}}
            )
            raise RuntimeError(f"Cannot save file: {e}") from e
    
    def get_file_path(self, project_id: str, file_uuid: str) -> Optional[Path]:
        """Get file path by project_id and UUID.
        
        Args:
            project_id: Project identifier
            file_uuid: UUID portion of filename
        
        Returns:
            Path to file if exists, None otherwise
        """
        project_dir = self.base_dir / project_id
        # Try common extensions
        for ext in [".pdf", ".PDF"]:
            candidate = project_dir / f"{file_uuid}{ext}"
            if candidate.exists():
                return candidate.resolve()
        return None
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file from storage.
        
        Args:
            file_path: Absolute path to file
        
        Returns:
            True if deleted, False if not found or error
        """
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                path.unlink()
                logger.info(f"Deleted file from landing zone: {file_path}")
                return True
            return False
        except OSError as e:
            logger.warning(f"Failed to delete file {file_path}: {e}", exc_info=True)
            return False

