"""
Ingestion Store for tracking file ingestion state and metadata.

Tracks ingestion records separately from jobs to support:
- Duplicate detection
- First glance summaries
- Status polling
- Retry operations
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

logger = logging.getLogger(__name__)

INGESTION_COLLECTION = "ingestions"


class IngestionStatus:
    """Ingestion pipeline states."""
    QUEUED = "Queued"
    EXTRACTING = "Extracting"
    MAPPING = "Mapping"
    VERIFYING = "Verifying"
    INDEXED = "Indexed"  # Qdrant indexing completed
    COMPLETED = "Completed"
    FAILED = "Failed"


class IngestionRecord:
    """Ingestion record with metadata."""
    
    def __init__(
        self,
        ingestion_id: str,
        project_id: str,
        filename: str,
        file_hash: str,
        status: str = IngestionStatus.QUEUED,
        job_id: Optional[str] = None,
        error_message: Optional[str] = None,
        progress_pct: float = 0.0,
        first_glance: Optional[Dict[str, Any]] = None,
        confidence_badge: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        self.ingestion_id = ingestion_id
        self.project_id = project_id
        self.filename = filename
        self.file_hash = file_hash
        self.status = status
        self.job_id = job_id
        self.error_message = error_message
        self.progress_pct = progress_pct
        self.first_glance = first_glance or {}
        self.confidence_badge = confidence_badge
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.updated_at = updated_at or datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/API."""
        return {
            "_key": self.ingestion_id,
            "ingestion_id": self.ingestion_id,
            "project_id": self.project_id,
            "filename": self.filename,
            "file_hash": self.file_hash,
            "status": self.status,
            "job_id": self.job_id,
            "error_message": self.error_message,
            "progress_pct": self.progress_pct,
            "first_glance": self.first_glance,
            "confidence_badge": self.confidence_badge,
            "qdrant_indexed": getattr(self, "qdrant_indexed", False),
            "chunk_count": getattr(self, "chunk_count", None),
            "indexed_at": getattr(self, "indexed_at", None),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, doc: Dict[str, Any]) -> "IngestionRecord":
        """Create from ArangoDB document."""
        return cls(
            ingestion_id=doc.get("ingestion_id") or doc.get("_key", ""),
            project_id=doc.get("project_id", ""),
            filename=doc.get("filename", ""),
            file_hash=doc.get("file_hash", ""),
            status=doc.get("status", IngestionStatus.QUEUED),
            job_id=doc.get("job_id"),
            error_message=doc.get("error_message"),
            progress_pct=doc.get("progress_pct", 0.0),
            first_glance=doc.get("first_glance", {}),
            confidence_badge=doc.get("confidence_badge"),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )
        # Set optional fields
        record.qdrant_indexed = doc.get("qdrant_indexed", False)
        record.chunk_count = doc.get("chunk_count")
        record.indexed_at = doc.get("indexed_at")
        return record


class IngestionStore:
    """Store for ingestion records."""
    
    def __init__(self, db: StandardDatabase):
        """Initialize ingestion store.
        
        Args:
            db: ArangoDB database instance.
        """
        if db is None:
            raise ValueError("Database instance is required")
        self.db = db
        self.ensure_schema()
    
    def ensure_schema(self) -> None:
        """Ensure ingestion collection exists with indexes."""
        try:
            if not self.db.has_collection(INGESTION_COLLECTION):
                self.db.create_collection(INGESTION_COLLECTION)
                logger.info(f"Created collection '{INGESTION_COLLECTION}'")
            
            collection = self.db.collection(INGESTION_COLLECTION)
            # Index on file_hash for duplicate detection
            collection.ensure_persistent_index(["file_hash"])
            # Index on project_id for project queries
            collection.ensure_persistent_index(["project_id"])
            # Index on job_id for job lookups
            collection.ensure_persistent_index(["job_id"])
            logger.debug(f"Ensured indexes in '{INGESTION_COLLECTION}'")
        except ArangoError as e:
            logger.error(f"Failed to ensure schema for '{INGESTION_COLLECTION}': {e}", exc_info=True)
            raise RuntimeError(f"Schema setup failed: {e}") from e
    
    def create_ingestion(
        self,
        project_id: str,
        filename: str,
        file_hash: str,
        job_id: Optional[str] = None,
        allow_empty_hash: bool = False,
        first_glance: Optional[Dict[str, Any]] = None,
    ) -> IngestionRecord:
        """Create a new ingestion record (atomic).
        
        Args:
            project_id: Project identifier.
            filename: Original filename.
            file_hash: SHA256 hash of file content.
            job_id: Optional job ID if workflow already started.
            allow_empty_hash: If True, allows empty hash (for non-file workflows).
            first_glance: Optional first glance summary (computed deterministically from PDF).
        
        Returns:
            IngestionRecord with generated ingestion_id.
        
        Raises:
            ValueError: If file_hash is missing or empty (unless allow_empty_hash=True).
        """
        # Atomic validation: fail fast if file_hash is missing (unless explicitly allowed)
        if not allow_empty_hash and (not file_hash or not file_hash.strip()):
            raise ValueError("file_hash is required and cannot be empty for file uploads")
        
        ingestion_id = str(uuid.uuid4())
        record = IngestionRecord(
            ingestion_id=ingestion_id,
            project_id=project_id,
            filename=filename,
            file_hash=file_hash,
            status=IngestionStatus.QUEUED,
            job_id=job_id,
            first_glance=first_glance,
        )
        
        try:
            collection = self.db.collection(INGESTION_COLLECTION)
            collection.insert(record.to_dict())
            logger.info(f"Created ingestion record {ingestion_id} for project {project_id}")
            return record
        except ArangoError as e:
            logger.error(f"Failed to create ingestion record: {e}", exc_info=True)
            raise RuntimeError(f"Failed to create ingestion record: {e}") from e
    
    def get_ingestion(self, ingestion_id: str) -> Optional[IngestionRecord]:
        """Get ingestion record by ID.
        
        Args:
            ingestion_id: Ingestion identifier.
        
        Returns:
            IngestionRecord or None if not found.
        """
        try:
            collection = self.db.collection(INGESTION_COLLECTION)
            doc = collection.get(ingestion_id)
            if doc:
                return IngestionRecord.from_dict(doc)
            return None
        except ArangoError as e:
            logger.error(f"Failed to get ingestion {ingestion_id}: {e}", exc_info=True)
            return None
    
    def update_ingestion(
        self,
        ingestion_id: str,
        status: Optional[str] = None,
        job_id: Optional[str] = None,
        error_message: Optional[str] = None,
        progress_pct: Optional[float] = None,
        first_glance: Optional[Dict[str, Any]] = None,
        confidence_badge: Optional[str] = None,
        chunk_count: Optional[int] = None,
        indexed_at: Optional[str] = None,
    ) -> bool:
        """Update ingestion record.
        
        Args:
            ingestion_id: Ingestion identifier.
            status: New status.
            job_id: Job ID if available.
            error_message: Error message if failed.
            progress_pct: Progress percentage (0-100).
            first_glance: First glance summary dict.
            confidence_badge: Confidence badge (High/Medium/Low).
        
        Returns:
            True if updated, False if not found.
        """
        try:
            collection = self.db.collection(INGESTION_COLLECTION)
            doc = collection.get(ingestion_id)
            if not doc:
                return False
            
            updates: Dict[str, Any] = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            
            if status is not None:
                updates["status"] = status
            if job_id is not None:
                updates["job_id"] = job_id
            if error_message is not None:
                updates["error_message"] = error_message
            if progress_pct is not None:
                updates["progress_pct"] = progress_pct
            if first_glance is not None:
                updates["first_glance"] = first_glance
            if confidence_badge is not None:
                updates["confidence_badge"] = confidence_badge
            if chunk_count is not None:
                updates["chunk_count"] = chunk_count
            if indexed_at is not None:
                updates["indexed_at"] = indexed_at
            
            collection.update(ingestion_id, updates)
            logger.debug(f"Updated ingestion {ingestion_id}")
            return True
        except ArangoError as e:
            logger.error(f"Failed to update ingestion {ingestion_id}: {e}", exc_info=True)
            return False
    
    def find_duplicates(
        self,
        file_hash: str,
        exclude_project_id: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Find duplicate files by hash.
        
        Args:
            file_hash: SHA256 hash to search for.
            exclude_project_id: Optional project ID to exclude from results.
        
        Returns:
            List of {project_id, title} dicts for projects containing this file.
        """
        try:
            query = """
            FOR ing IN @@col
            FILTER ing.file_hash == @file_hash
            FOR proj IN projects
            FILTER proj._key == ing.project_id
            RETURN {
                project_id: proj._key,
                title: proj.title
            }
            """
            
            bind_vars = {
                "@col": INGESTION_COLLECTION,
                "file_hash": file_hash,
            }
            
            if exclude_project_id:
                query = query.replace(
                    "FILTER proj._key == ing.project_id",
                    "FILTER proj._key == ing.project_id AND proj._key != @exclude_project_id"
                )
                bind_vars["exclude_project_id"] = exclude_project_id
            
            cursor = self.db.aql.execute(query, bind_vars=bind_vars)
            results = list(cursor)
            return results
        except ArangoError as e:
            logger.error(f"Failed to find duplicates for hash {file_hash[:16]}...: {e}", exc_info=True)
            return []
    
    def find_by_hash(
        self,
        file_hash: str,
        project_id: Optional[str] = None,
    ) -> List[IngestionRecord]:
        """Find ingestion records by file hash.
        
        Args:
            file_hash: SHA256 hash to search for.
            project_id: Optional project ID to filter by.
        
        Returns:
            List of IngestionRecord objects.
        """
        try:
            query = """
            FOR ing IN @@col
            FILTER ing.file_hash == @file_hash
            """
            
            bind_vars = {
                "@col": INGESTION_COLLECTION,
                "file_hash": file_hash,
            }
            
            if project_id:
                query += " FILTER ing.project_id == @project_id"
                bind_vars["project_id"] = project_id
            
            query += " RETURN ing"
            
            cursor = self.db.aql.execute(query, bind_vars=bind_vars)
            results = list(cursor)
            return [IngestionRecord.from_dict(doc) for doc in results]
        except ArangoError as e:
            logger.error(f"Failed to find by hash {file_hash[:16]}...: {e}", exc_info=True)
            return []
    
    def get_by_job_id(self, job_id: str) -> Optional[IngestionRecord]:
        """Get ingestion record by job ID.
        
        Args:
            job_id: Job identifier.
        
        Returns:
            IngestionRecord or None if not found.
        """
        try:
            query = """
            FOR ing IN @@col
            FILTER ing.job_id == @job_id
            LIMIT 1
            RETURN ing
            """
            
            cursor = self.db.aql.execute(
                query,
                bind_vars={
                    "@col": INGESTION_COLLECTION,
                    "job_id": job_id,
                }
            )
            results = list(cursor)
            if results:
                return IngestionRecord.from_dict(results[0])
            return None
        except ArangoError as e:
            logger.error(f"Failed to get ingestion by job_id {job_id}: {e}", exc_info=True)
            return None

