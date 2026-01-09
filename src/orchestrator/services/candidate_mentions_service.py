"""
CandidateMentions Service for Project Vyasa.

Handles persistence of CandidateMentions artifacts (Tier-A output).
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ..schemas.candidate_mentions import CandidateMentions
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

CANDIDATE_MENTIONS_COLLECTION = "candidate_mentions"


class CandidateMentionsService:
    """Service for managing CandidateMentions artifacts (Tier-A output)."""
    
    def __init__(self, db: StandardDatabase) -> None:
        """Initialize the candidate mentions service.
        
        Args:
            db: ArangoDB database instance.
        """
        self.db = db
        self._ensure_collections()
    
    def _ensure_collections(self) -> None:
        """Ensure required collections exist with proper indexes."""
        if not self.db.has_collection(CANDIDATE_MENTIONS_COLLECTION):
            self.db.create_collection(CANDIDATE_MENTIONS_COLLECTION)
            logger.info(f"Created collection: {CANDIDATE_MENTIONS_COLLECTION}")
        
        coll = self.db.collection(CANDIDATE_MENTIONS_COLLECTION)
        
        # Indexes for efficient queries
        try:
            coll.ensure_persistent_index(["mentions_id"], unique=True)
            coll.ensure_persistent_index(["project_id"])
            coll.ensure_persistent_index(["ingestion_id"])
            # Composite indexes for common queries
            coll.ensure_persistent_index(["project_id", "ingestion_id"])
            coll.ensure_persistent_index(["project_id", "created_at"])
        except ArangoError:
            # Indexes may already exist
            pass
    
    def save_mentions(
        self,
        mentions: CandidateMentions,
    ) -> CandidateMentions:
        """Save a CandidateMentions collection.
        
        Args:
            mentions: CandidateMentions to save.
        
        Returns:
            Saved CandidateMentions with ArangoDB fields populated.
        
        Raises:
            ArangoError: If database operation fails.
        """
        # Ensure timestamp is set
        if not mentions.created_at:
            mentions.created_at = datetime.now(timezone.utc).isoformat()
        
        # Generate document key
        doc_key = mentions.mentions_id
        
        # Convert to dict for ArangoDB
        doc = mentions.model_dump(exclude={"id", "key"})
        doc["_key"] = doc_key
        
        # Insert into database
        coll = self.db.collection(CANDIDATE_MENTIONS_COLLECTION)
        result = coll.insert(doc)
        
        logger.debug(
            f"Saved CandidateMentions",
            extra={
                "payload": {
                    "mentions_id": mentions.mentions_id,
                    "project_id": mentions.project_id,
                    "ingestion_id": mentions.ingestion_id,
                    "total_mentions": mentions.total_mentions,
                    "entity_types": list(set(m.entity_type for m in mentions.mentions)),
                }
            }
        )
        
        return mentions
    
    def get_mentions(
        self,
        mentions_id: str,
    ) -> Optional[CandidateMentions]:
        """Get CandidateMentions by ID.
        
        Args:
            mentions_id: CandidateMentions identifier.
        
        Returns:
            CandidateMentions if found, None otherwise.
        """
        try:
            coll = self.db.collection(CANDIDATE_MENTIONS_COLLECTION)
            doc = coll.get(mentions_id)
            
            if not doc:
                return None
            
            # Remove ArangoDB metadata
            doc.pop("_key", None)
            doc.pop("_id", None)
            doc.pop("_rev", None)
            
            return CandidateMentions(**doc)
        except ArangoError as e:
            logger.warning(f"Failed to get CandidateMentions {mentions_id}: {e}", exc_info=True)
            return None
    
    def get_mentions_by_ingestion(
        self,
        project_id: str,
        ingestion_id: str,
    ) -> Optional[CandidateMentions]:
        """Get CandidateMentions for a specific ingestion.
        
        Args:
            project_id: Project identifier.
            ingestion_id: Ingestion identifier.
        
        Returns:
            CandidateMentions if found, None otherwise.
        """
        try:
            coll = self.db.collection(CANDIDATE_MENTIONS_COLLECTION)
            # Query by project_id and ingestion_id
            query = f"""
            FOR mentions IN {CANDIDATE_MENTIONS_COLLECTION}
            FILTER mentions.project_id == @project_id AND mentions.ingestion_id == @ingestion_id
            SORT mentions.created_at DESC
            LIMIT 1
            RETURN mentions
            """
            cursor = self.db.aql.execute(query, bind_vars={"project_id": project_id, "ingestion_id": ingestion_id})
            results = list(cursor)
            
            if not results:
                return None
            
            doc = results[0]
            # Remove ArangoDB metadata
            doc.pop("_key", None)
            doc.pop("_id", None)
            doc.pop("_rev", None)
            
            return CandidateMentions(**doc)
        except ArangoError as e:
            logger.warning(f"Failed to get CandidateMentions for ingestion {ingestion_id}: {e}", exc_info=True)
            return None
    
    def get_mentions_by_entity_type(
        self,
        project_id: str,
        ingestion_id: str,
        entity_type: str,
    ) -> List[Dict[str, Any]]:
        """Get candidate mentions filtered by entity type.
        
        Args:
            project_id: Project identifier.
            ingestion_id: Ingestion identifier.
            entity_type: Entity type to filter by.
        
        Returns:
            List of CandidateMention dictionaries matching the entity type.
        """
        try:
            mentions_collection = self.get_mentions_by_ingestion(project_id, ingestion_id)
            if not mentions_collection:
                return []
            
            # Filter by entity_type
            filtered = [
                m.model_dump()
                for m in mentions_collection.mentions
                if m.entity_type == entity_type
            ]
            
            return filtered
        except Exception as e:
            logger.warning(f"Failed to get mentions by entity type: {e}", exc_info=True)
            return []
