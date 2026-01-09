"""
Retrieval Bundle Service for Project Vyasa.

Handles internal persistence of RetrievalBundle artifacts.
RetrievalBundle tracks the full retrieval pipeline for reproducibility and audit.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ..schemas.retrieval import RetrievalBundle
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

RETRIEVAL_BUNDLES_COLLECTION = "retrieval_bundles"


class RetrievalBundleService:
    """Service for managing RetrievalBundle artifacts (internal use)."""
    
    def __init__(self, db: StandardDatabase) -> None:
        """Initialize the retrieval bundle service.
        
        Args:
            db: ArangoDB database instance.
        """
        self.db = db
        self._ensure_collections()
    
    def _ensure_collections(self) -> None:
        """Ensure required collections exist with proper indexes."""
        if not self.db.has_collection(RETRIEVAL_BUNDLES_COLLECTION):
            self.db.create_collection(RETRIEVAL_BUNDLES_COLLECTION)
            logger.info(f"Created collection: {RETRIEVAL_BUNDLES_COLLECTION}")
        
        coll = self.db.collection(RETRIEVAL_BUNDLES_COLLECTION)
        
        # Indexes for efficient queries (keyed by: project_id, ingestion_id, section_id, query_id)
        try:
            coll.ensure_persistent_index(["bundle_id"], unique=True)
            coll.ensure_persistent_index(["project_id"])
            coll.ensure_persistent_index(["ingestion_id"])
            coll.ensure_persistent_index(["section_id"])
            coll.ensure_persistent_index(["query_id"])
            # Composite indexes for common queries
            coll.ensure_persistent_index(["project_id", "ingestion_id"])
            coll.ensure_persistent_index(["project_id", "ingestion_id", "section_id"])
            coll.ensure_persistent_index(["project_id", "section_id"])
            coll.ensure_persistent_index(["project_id", "created_at"])
        except ArangoError:
            # Indexes may already exist
            pass
    
    def save_bundle(
        self,
        bundle: RetrievalBundle,
    ) -> RetrievalBundle:
        """Save a RetrievalBundle.
        
        Args:
            bundle: RetrievalBundle to save.
        
        Returns:
            Saved RetrievalBundle with ArangoDB fields populated.
        
        Raises:
            ArangoError: If database operation fails.
        """
        # Ensure timestamp is set
        if not bundle.created_at:
            bundle.created_at = datetime.now(timezone.utc).isoformat()
        
        # Generate document key
        doc_key = bundle.bundle_id
        
        # Convert to dict for ArangoDB
        doc = bundle.model_dump(exclude={"id", "key"})
        doc["_key"] = doc_key
        
        # Insert into database
        coll = self.db.collection(RETRIEVAL_BUNDLES_COLLECTION)
        result = coll.insert(doc)
        
        logger.debug(
            f"Saved RetrievalBundle",
            extra={
                "payload": {
                    "bundle_id": bundle.bundle_id,
                    "project_id": bundle.project_id,
                    "section_id": bundle.section_id,
                    "query_id": bundle.query_id,
                    "top_k_embed": bundle.top_k_embed,
                    "top_k_rerank": bundle.top_k_rerank,
                    "rerank_skipped": getattr(bundle, "rerank_skipped", False),
                }
            }
        )
        
        return bundle
    
    def get_bundle(
        self,
        bundle_id: str,
    ) -> Optional[RetrievalBundle]:
        """Get a RetrievalBundle by ID.
        
        Args:
            bundle_id: Bundle identifier.
        
        Returns:
            RetrievalBundle if found, None otherwise.
        """
        coll = self.db.collection(RETRIEVAL_BUNDLES_COLLECTION)
        doc = coll.get(bundle_id)
        
        if not doc:
            return None
        
        return RetrievalBundle(**doc)
    
    def list_bundles(
        self,
        project_id: str,
        section_id: Optional[str] = None,
        query_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[RetrievalBundle]:
        """List RetrievalBundles for a project with optional filters.
        
        Args:
            project_id: Project identifier.
            section_id: Optional section identifier filter.
            query_id: Optional query identifier filter.
            limit: Optional limit on number of results.
        
        Returns:
            List of RetrievalBundle objects (sorted by created_at descending).
        """
        filters = ["bundle.project_id == @project_id"]
        bind_vars = {"project_id": project_id}
        
        if section_id:
            filters.append("bundle.section_id == @section_id")
            bind_vars["section_id"] = section_id
        
        if query_id:
            filters.append("bundle.query_id == @query_id")
            bind_vars["query_id"] = query_id
        
        filter_clause = " AND ".join(filters)
        
        query = f"""
        FOR bundle IN {RETRIEVAL_BUNDLES_COLLECTION}
        FILTER {filter_clause}
        SORT bundle.created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        query += " RETURN bundle"
        
        cursor = self.db.aql.execute(query, bind_vars=bind_vars)
        
        return [RetrievalBundle(**doc) for doc in cursor]
    
    def get_bundles_for_section(
        self,
        project_id: str,
        section_id: str,
    ) -> List[RetrievalBundle]:
        """Get all RetrievalBundles for a specific section.
        
        Args:
            project_id: Project identifier.
            section_id: Section identifier.
        
        Returns:
            List of RetrievalBundle objects (sorted by created_at descending).
        """
        return self.list_bundles(
            project_id=project_id,
            section_id=section_id,
        )
