"""
EvidencePack Service for Project Vyasa.

Handles persistence of EvidencePack artifacts in ArangoDB.
EvidencePack is a first-class artifact that must be provided to all Tier-B calls.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ..schemas.evidence_pack import EvidencePack
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

EVIDENCE_PACKS_COLLECTION = "evidence_packs"


class EvidencePackService:
    """Service for managing EvidencePack artifacts."""
    
    def __init__(self, db: StandardDatabase) -> None:
        """Initialize the evidence pack service.
        
        Args:
            db: ArangoDB database instance.
        """
        self.db = db
        self._ensure_collections()
    
    def _ensure_collections(self) -> None:
        """Ensure required collections exist with proper indexes."""
        if not self.db.has_collection(EVIDENCE_PACKS_COLLECTION):
            self.db.create_collection(EVIDENCE_PACKS_COLLECTION)
            logger.info(f"Created collection: {EVIDENCE_PACKS_COLLECTION}")
        
        coll = self.db.collection(EVIDENCE_PACKS_COLLECTION)
        
        # Indexes for efficient queries
        try:
            coll.ensure_persistent_index(["pack_id"], unique=True)
            coll.ensure_persistent_index(["project_id"])
            coll.ensure_persistent_index(["ingestion_id"])
            coll.ensure_persistent_index(["section_id"])
            coll.ensure_persistent_index(["query_id"])
            coll.ensure_persistent_index(["retrieval_bundle_id"])
            # Composite indexes for common queries
            coll.ensure_persistent_index(["project_id", "ingestion_id"])
            coll.ensure_persistent_index(["project_id", "section_id"])
            coll.ensure_persistent_index(["project_id", "created_at"])
            coll.ensure_persistent_index(["retrieval_bundle_id"], unique=False)  # Multiple packs per bundle possible
        except ArangoError:
            # Indexes may already exist
            pass
    
    def save_pack(
        self,
        pack: EvidencePack,
    ) -> EvidencePack:
        """Save an EvidencePack.
        
        Args:
            pack: EvidencePack to save.
        
        Returns:
            Saved EvidencePack with ArangoDB fields populated.
        
        Raises:
            ArangoError: If database operation fails.
        """
        # Ensure timestamp is set
        if not pack.created_at:
            pack.created_at = datetime.now(timezone.utc).isoformat()
        
        # Generate document key
        doc_key = pack.pack_id
        
        # Convert to dict for ArangoDB
        doc = pack.model_dump(exclude={"id", "key"})
        doc["_key"] = doc_key
        
        # Insert into database
        coll = self.db.collection(EVIDENCE_PACKS_COLLECTION)
        result = coll.insert(doc)
        
        logger.debug(
            f"Saved EvidencePack",
            extra={
                "payload": {
                    "pack_id": pack.pack_id,
                    "project_id": pack.project_id,
                    "ingestion_id": pack.ingestion_id,
                    "section_id": pack.section_id,
                    "retrieval_bundle_id": pack.retrieval_bundle_id,
                    "snippet_count": len(pack.snippets),
                    "pointer_count": len(pack.pointers),
                }
            }
        )
        
        return pack
    
    def get_pack(
        self,
        pack_id: str,
    ) -> Optional[EvidencePack]:
        """Get an EvidencePack by ID.
        
        Args:
            pack_id: EvidencePack identifier.
        
        Returns:
            EvidencePack if found, None otherwise.
        """
        try:
            coll = self.db.collection(EVIDENCE_PACKS_COLLECTION)
            doc = coll.get(pack_id)
            
            if not doc:
                return None
            
            # Remove ArangoDB metadata
            doc.pop("_key", None)
            doc.pop("_id", None)
            doc.pop("_rev", None)
            
            return EvidencePack(**doc)
        except ArangoError as e:
            logger.warning(f"Failed to get EvidencePack {pack_id}: {e}", exc_info=True)
            return None
    
    def get_pack_by_bundle_id(
        self,
        retrieval_bundle_id: str,
    ) -> Optional[EvidencePack]:
        """Get an EvidencePack by RetrievalBundle ID.
        
        Args:
            retrieval_bundle_id: RetrievalBundle identifier.
        
        Returns:
            EvidencePack if found, None otherwise.
        """
        try:
            coll = self.db.collection(EVIDENCE_PACKS_COLLECTION)
            # Query by retrieval_bundle_id
            query = f"""
            FOR pack IN {EVIDENCE_PACKS_COLLECTION}
            FILTER pack.retrieval_bundle_id == @bundle_id
            SORT pack.created_at DESC
            LIMIT 1
            RETURN pack
            """
            cursor = self.db.aql.execute(query, bind_vars={"bundle_id": retrieval_bundle_id})
            results = list(cursor)
            
            if not results:
                return None
            
            doc = results[0]
            # Remove ArangoDB metadata
            doc.pop("_key", None)
            doc.pop("_id", None)
            doc.pop("_rev", None)
            
            return EvidencePack(**doc)
        except ArangoError as e:
            logger.warning(f"Failed to get EvidencePack by bundle_id {retrieval_bundle_id}: {e}", exc_info=True)
            return None
    
    def list_packs(
        self,
        project_id: str,
        ingestion_id: Optional[str] = None,
        section_id: Optional[str] = None,
    ) -> List[EvidencePack]:
        """List EvidencePacks for a project.
        
        Args:
            project_id: Project identifier.
            ingestion_id: Optional ingestion identifier filter.
            section_id: Optional section identifier filter.
        
        Returns:
            List of EvidencePacks matching the filters.
        """
        try:
            coll = self.db.collection(EVIDENCE_PACKS_COLLECTION)
            
            # Build query filters
            filters = {"project_id": project_id}
            if ingestion_id:
                filters["ingestion_id"] = ingestion_id
            if section_id:
                filters["section_id"] = section_id
            
            # Query
            query = f"""
            FOR pack IN {EVIDENCE_PACKS_COLLECTION}
            FILTER pack.project_id == @project_id
            """
            bind_vars = {"project_id": project_id}
            
            if ingestion_id:
                query += " AND pack.ingestion_id == @ingestion_id"
                bind_vars["ingestion_id"] = ingestion_id
            if section_id:
                query += " AND pack.section_id == @section_id"
                bind_vars["section_id"] = section_id
            
            query += " SORT pack.created_at DESC RETURN pack"
            
            cursor = self.db.aql.execute(query, bind_vars=bind_vars)
            results = list(cursor)
            
            packs = []
            for doc in results:
                # Remove ArangoDB metadata
                doc.pop("_key", None)
                doc.pop("_id", None)
                doc.pop("_rev", None)
                
                try:
                    packs.append(EvidencePack(**doc))
                except Exception as e:
                    logger.warning(f"Failed to parse EvidencePack from doc: {e}", exc_info=True)
                    continue
            
            return packs
        except ArangoError as e:
            logger.warning(f"Failed to list EvidencePacks: {e}", exc_info=True)
            return []
