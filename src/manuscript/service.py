"""
Manuscript Service for Project Vyasa.

Handles persistence and retrieval of manuscript blocks with full version history
and citation validation (Librarian Key-Guard).
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ..shared.schema import ManuscriptBlock, PatchObject
from ..shared.logger import get_logger

logger = get_logger("manuscript", __name__)


class ManuscriptService:
    """Service for managing manuscript blocks with versioning and citation validation."""
    
    BLOCKS_COLLECTION = "manuscript_blocks"
    PATCHES_COLLECTION = "patches"
    BIBLIOGRAPHY_COLLECTION = "project_bibliography"
    
    def __init__(self, db: StandardDatabase) -> None:
        """Initialize the manuscript service.
        
        Args:
            db: ArangoDB database instance.
        """
        self.db = db
        self._ensure_collections()
    
    def _ensure_collections(self) -> None:
        """Ensure required collections exist with proper indexes."""
        # Manuscript blocks collection
        if not self.db.has_collection(self.BLOCKS_COLLECTION):
            self.db.create_collection(self.BLOCKS_COLLECTION)
            logger.info(f"Created collection: {self.BLOCKS_COLLECTION}")
        
        blocks_col = self.db.collection(self.BLOCKS_COLLECTION)
        
        # Indexes for efficient queries
        try:
            blocks_col.ensure_persistent_index(["project_id", "block_id", "version"])
            blocks_col.ensure_persistent_index(["project_id", "order_index"])
        except ArangoError:
            # Indexes may already exist
            pass
        
        # Patches collection
        if not self.db.has_collection(self.PATCHES_COLLECTION):
            self.db.create_collection(self.PATCHES_COLLECTION)
            logger.info(f"Created collection: {self.PATCHES_COLLECTION}")
        
        patches_col = self.db.collection(self.PATCHES_COLLECTION)
        
        try:
            patches_col.ensure_persistent_index(["project_id", "original_block_id", "status"])
        except ArangoError:
            pass
        
        # Bibliography collection (for citation validation)
        if not self.db.has_collection(self.BIBLIOGRAPHY_COLLECTION):
            self.db.create_collection(self.BIBLIOGRAPHY_COLLECTION)
            logger.info(f"Created collection: {self.BIBLIOGRAPHY_COLLECTION}")
        
        bib_col = self.db.collection(self.BIBLIOGRAPHY_COLLECTION)
        
        try:
            # Unique index on project_id + citation_key to prevent duplicates
            bib_col.ensure_persistent_index(["project_id", "citation_key"], unique=True)
        except ArangoError:
            pass
    
    def _validate_citations(self, project_id: str, citation_keys: List[str]) -> None:
        """Librarian Key-Guard: Validate citation keys against project bibliography.
        
        Args:
            project_id: Project identifier.
            citation_keys: List of citation keys to validate.
        
        Raises:
            ValueError: If any citation key is not found in project bibliography.
        """
        if not citation_keys:
            return
        
        if not self.db.has_collection(self.BIBLIOGRAPHY_COLLECTION):
            raise ValueError(
                f"Bibliography collection '{self.BIBLIOGRAPHY_COLLECTION}' missing. "
                "Cannot validate citation keys. Add bibliography entries first."
            )
        
        # Query existing citation keys for this project
        cursor = self.db.aql.execute(
            f"""
            FOR b IN {self.BIBLIOGRAPHY_COLLECTION}
            FILTER b.project_id == @project_id
            RETURN b.citation_key
            """,
            bind_vars={"project_id": project_id},
        )
        existing_keys = set(cursor)
        
        # Find missing keys
        missing_keys = [key for key in citation_keys if key not in existing_keys]
        
        if missing_keys:
            raise ValueError(
                f"Citation keys not found in project bibliography: {missing_keys}. "
                f"Add these keys to '{self.BIBLIOGRAPHY_COLLECTION}' collection first."
            )
        
        logger.debug(
            f"Citation validation passed",
            extra={"payload": {"project_id": project_id, "citation_count": len(citation_keys)}}
        )
    
    def _get_next_version(self, project_id: str, block_id: str) -> int:
        """Get the next version number for a block.
        
        Args:
            project_id: Project identifier.
            block_id: Block identifier.
        
        Returns:
            Next version number (1 if block doesn't exist).
        """
        cursor = self.db.aql.execute(
            f"""
            FOR b IN {self.BLOCKS_COLLECTION}
            FILTER b.project_id == @project_id AND b.block_id == @block_id
            SORT b.version DESC
            LIMIT 1
            RETURN b.version
            """,
            bind_vars={"project_id": project_id, "block_id": block_id},
        )
        versions = list(cursor)
        return (versions[0] + 1) if versions else 1
    
    def save_block(
        self,
        block: ManuscriptBlock,
        project_id: str,
        validate_citations: bool = True,
    ) -> ManuscriptBlock:
        """Save a manuscript block with versioning and citation validation.
        
        Args:
            block: ManuscriptBlock to save.
            project_id: Project identifier (overrides block.project_id if provided).
            validate_citations: Whether to validate citation keys (Librarian guard).
        
        Returns:
            Saved ManuscriptBlock with ArangoDB fields populated.
        
        Raises:
            ValueError: If citation validation fails.
            ArangoError: If database operation fails.
        """
        # Ensure project_id is set
        if not block.project_id:
            block.project_id = project_id
        elif block.project_id != project_id:
            logger.warning(
                f"Block project_id ({block.project_id}) differs from provided project_id ({project_id}). Using provided.",
                extra={"payload": {"block_id": block.block_id}}
            )
            block.project_id = project_id
        
        # Librarian Key-Guard: Validate citations
        if validate_citations and block.citation_keys:
            self._validate_citations(project_id, block.citation_keys)
        
        # Get next version
        version = self._get_next_version(project_id, block.block_id)
        block.version = version
        
        # Prepare document for ArangoDB
        now_iso = datetime.now(timezone.utc).isoformat()
        if not block.created_at:
            block.created_at = now_iso
        block.updated_at = now_iso
        
        # Generate document key
        doc_key = f"{project_id}_{block.block_id}_v{version}"
        
        # Convert to dict for ArangoDB
        doc = block.model_dump(by_alias=True, exclude={"id", "key"})
        doc["_key"] = doc_key
        
        # Insert into database
        blocks_col = self.db.collection(self.BLOCKS_COLLECTION)
        result = blocks_col.insert(doc)
        
        # Update block with ArangoDB fields
        block.id = result["_id"]
        block.key = result["_key"]
        
        logger.info(
            f"Saved manuscript block",
            extra={
                "payload": {
                    "block_id": block.block_id,
                    "project_id": project_id,
                    "version": version,
                    "citation_count": len(block.citation_keys),
                    "claim_count": len(block.claim_ids),
                }
            }
        )
        
        return block
    
    def get_block(
        self,
        project_id: str,
        block_id: str,
        version: Optional[int] = None,
    ) -> Optional[ManuscriptBlock]:
        """Get a manuscript block by ID and optional version.
        
        Args:
            project_id: Project identifier.
            block_id: Block identifier.
            version: Optional version number. If None, returns latest version.
        
        Returns:
            ManuscriptBlock if found, None otherwise.
        """
        if version is None:
            # Get latest version
            cursor = self.db.aql.execute(
                f"""
                FOR b IN {self.BLOCKS_COLLECTION}
                FILTER b.project_id == @project_id AND b.block_id == @block_id
                SORT b.version DESC
                LIMIT 1
                RETURN b
                """,
                bind_vars={"project_id": project_id, "block_id": block_id},
            )
        else:
            # Get specific version
            cursor = self.db.aql.execute(
                f"""
                FOR b IN {self.BLOCKS_COLLECTION}
                FILTER b.project_id == @project_id 
                  AND b.block_id == @block_id 
                  AND b.version == @version
                LIMIT 1
                RETURN b
                """,
                bind_vars={"project_id": project_id, "block_id": block_id, "version": version},
            )
        
        results = list(cursor)
        if not results:
            return None
        
        return ManuscriptBlock(**results[0])
    
    def list_blocks(
        self,
        project_id: str,
        order_by: str = "order_index",
    ) -> List[ManuscriptBlock]:
        """List all blocks for a project (latest versions only).
        
        Args:
            project_id: Project identifier.
            order_by: Field to sort by (default: "order_index").
        
        Returns:
            List of ManuscriptBlock objects (latest version of each block).
        """
        # Get latest version of each block
        cursor = self.db.aql.execute(
            f"""
            FOR b IN {self.BLOCKS_COLLECTION}
            FILTER b.project_id == @project_id
            SORT b.{order_by} ASC, b.version DESC
            RETURN DISTINCT b.block_id
            """,
            bind_vars={"project_id": project_id},
        )
        
        block_ids = list(cursor)
        
        # Get latest version for each block_id
        blocks = []
        for block_id in block_ids:
            block = self.get_block(project_id, block_id)
            if block:
                blocks.append(block)
        
        return blocks
    
    def save_patch(self, patch: PatchObject, project_id: str) -> PatchObject:
        """Save a patch proposal for review.
        
        Args:
            patch: PatchObject to save.
            project_id: Project identifier.
        
        Returns:
            Saved PatchObject with ArangoDB fields populated.
        """
        if not patch.project_id:
            patch.project_id = project_id
        
        now_iso = datetime.now(timezone.utc).isoformat()
        if not patch.created_at:
            patch.created_at = now_iso
        patch.updated_at = now_iso
        
        # Generate document key
        patch_id = f"patch_{patch.original_block_id}_{int(datetime.now(timezone.utc).timestamp())}"
        doc_key = f"{project_id}_{patch_id}"
        
        # Convert to dict
        doc = patch.model_dump(by_alias=True, exclude={"id", "key"})
        doc["_key"] = doc_key
        
        # Insert
        patches_col = self.db.collection(self.PATCHES_COLLECTION)
        result = patches_col.insert(doc)
        
        patch.id = result["_id"]
        patch.key = result["_key"]
        
        logger.info(
            f"Saved patch proposal",
            extra={
                "payload": {
                    "original_block_id": patch.original_block_id,
                    "project_id": project_id,
                    "status": patch.status,
                    "risk_flag": patch.risk_flag,
                }
            }
        )
        
        return patch
    
    def get_patches(
        self,
        project_id: str,
        block_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[PatchObject]:
        """Get patches for a project, optionally filtered by block or status.
        
        Args:
            project_id: Project identifier.
            block_id: Optional block ID to filter by.
            status: Optional status to filter by (Pending/Accepted/Rejected).
        
        Returns:
            List of PatchObject instances.
        """
        filters = ["b.project_id == @project_id"]
        bind_vars = {"project_id": project_id}
        
        if block_id:
            filters.append("b.original_block_id == @block_id")
            bind_vars["block_id"] = block_id
        
        if status:
            filters.append("b.status == @status")
            bind_vars["status"] = status
        
        filter_clause = " AND ".join(filters)
        
        cursor = self.db.aql.execute(
            f"""
            FOR b IN {self.PATCHES_COLLECTION}
            FILTER {filter_clause}
            SORT b.created_at DESC
            RETURN b
            """,
            bind_vars=bind_vars,
        )
        
        return [PatchObject(**doc) for doc in cursor]

