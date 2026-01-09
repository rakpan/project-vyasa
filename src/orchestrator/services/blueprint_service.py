"""
Manuscript Blueprint Service for Project Vyasa.

Handles persistence and retrieval of Manuscript Blueprints.
The Blueprint Engine governs manuscript synthesis by defining sections,
linked RQs, evidence clusters, depth intent, and visual anchors.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ..schemas.blueprint import (
    ManuscriptBlueprint,
    BlueprintSection,
    JournalSlot,
    DepthIntent,
    VisualAnchor,
)
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

MANUSCRIPT_BLUEPRINTS_COLLECTION = "manuscript_blueprints"


class BlueprintService:
    """Service for managing Manuscript Blueprints."""
    
    def __init__(self, db: StandardDatabase) -> None:
        """Initialize the blueprint service.
        
        Args:
            db: ArangoDB database instance.
        """
        self.db = db
        self._ensure_collections()
    
    def _ensure_collections(self) -> None:
        """Ensure required collections exist with proper indexes."""
        if not self.db.has_collection(MANUSCRIPT_BLUEPRINTS_COLLECTION):
            self.db.create_collection(MANUSCRIPT_BLUEPRINTS_COLLECTION)
            logger.info(f"Created collection: {MANUSCRIPT_BLUEPRINTS_COLLECTION}")
        
        coll = self.db.collection(MANUSCRIPT_BLUEPRINTS_COLLECTION)
        
        # Indexes for efficient queries
        try:
            coll.ensure_persistent_index(["blueprint_id"], unique=True)
            coll.ensure_persistent_index(["project_id"])
            coll.ensure_persistent_index(["version"])
            # Composite index for latest version queries
            coll.ensure_persistent_index(["project_id", "version"])
        except ArangoError:
            # Indexes may already exist
            pass
    
    def _validate_blueprint(self, blueprint: ManuscriptBlueprint) -> None:
        """Validate blueprint structure.
        
        Args:
            blueprint: ManuscriptBlueprint to validate.
        
        Raises:
            ValueError: If validation fails.
        """
        # Validate sections minimal fields
        for section in blueprint.sections:
            if not section.heading or not section.heading.strip():
                raise ValueError("Section heading must be non-empty.")
            
            if section.journal_slot not in [slot.value for slot in JournalSlot]:
                raise ValueError(f"Invalid journal_slot: {section.journal_slot}. Must be one of: {[slot.value for slot in JournalSlot]}")
            
            if section.depth_intent not in [intent.value for intent in DepthIntent]:
                raise ValueError(f"Invalid depth_intent: {section.depth_intent}. Must be one of: {[intent.value for intent in DepthIntent]}")
            
            # Validate section_id uniqueness within blueprint
            section_ids = [s.section_id for s in blueprint.sections]
            if len(section_ids) != len(set(section_ids)):
                raise ValueError("Section IDs must be unique within blueprint.")
    
    def save_blueprint(
        self,
        blueprint: ManuscriptBlueprint,
    ) -> ManuscriptBlueprint:
        """Save a Manuscript Blueprint with versioning.
        
        Args:
            blueprint: ManuscriptBlueprint to save.
        
        Returns:
            Saved ManuscriptBlueprint with ArangoDB fields populated.
        
        Raises:
            ValueError: If validation fails.
            ArangoError: If database operation fails.
        """
        # Validate blueprint structure
        self._validate_blueprint(blueprint)
        
        # Get latest version for this project
        latest_version = self._get_latest_version(blueprint.project_id)
        
        # If blueprint already exists, increment version
        if latest_version and latest_version > 0:
            blueprint.version = latest_version + 1
        else:
            blueprint.version = 1
        
        # Ensure timestamps are set
        now_iso = datetime.now(timezone.utc).isoformat()
        if not blueprint.created_at:
            blueprint.created_at = now_iso
        blueprint.updated_at = now_iso
        
        # Generate document key
        doc_key = blueprint.blueprint_id
        
        # Convert to dict for ArangoDB
        doc = blueprint.model_dump(exclude={"id", "key"})
        doc["_key"] = doc_key
        
        # Insert into database
        coll = self.db.collection(MANUSCRIPT_BLUEPRINTS_COLLECTION)
        result = coll.insert(doc)
        
        logger.info(
            f"Saved Manuscript Blueprint",
            extra={
                "payload": {
                    "blueprint_id": blueprint.blueprint_id,
                    "project_id": blueprint.project_id,
                    "version": blueprint.version,
                    "sections_count": len(blueprint.sections),
                }
            }
        )
        
        return blueprint
    
    def get_blueprint(
        self,
        project_id: str,
        version: Optional[int] = None,
    ) -> Optional[ManuscriptBlueprint]:
        """Get a Manuscript Blueprint for a project.
        
        Args:
            project_id: Project identifier.
            version: Optional version number. If None, returns latest version.
        
        Returns:
            ManuscriptBlueprint if found, None otherwise.
        """
        if version is None:
            # Get latest version
            cursor = self.db.aql.execute(
                f"""
                FOR b IN {MANUSCRIPT_BLUEPRINTS_COLLECTION}
                FILTER b.project_id == @project_id
                SORT b.version DESC
                LIMIT 1
                RETURN b
                """,
                bind_vars={"project_id": project_id},
            )
        else:
            # Get specific version
            cursor = self.db.aql.execute(
                f"""
                FOR b IN {MANUSCRIPT_BLUEPRINTS_COLLECTION}
                FILTER b.project_id == @project_id AND b.version == @version
                LIMIT 1
                RETURN b
                """,
                bind_vars={"project_id": project_id, "version": version},
            )
        
        results = list(cursor)
        if not results:
            return None
        
        return ManuscriptBlueprint(**results[0])
    
    def _get_latest_version(
        self,
        project_id: str,
    ) -> int:
        """Get the latest version number for a project's blueprint.
        
        Args:
            project_id: Project identifier.
        
        Returns:
            Latest version number (0 if no blueprint exists).
        """
        cursor = self.db.aql.execute(
            f"""
            FOR b IN {MANUSCRIPT_BLUEPRINTS_COLLECTION}
            FILTER b.project_id == @project_id
            SORT b.version DESC
            LIMIT 1
            RETURN b.version
            """,
            bind_vars={"project_id": project_id},
        )
        
        versions = list(cursor)
        return versions[0] if versions else 0
    
    def list_blueprints(
        self,
        project_id: str,
    ) -> List[ManuscriptBlueprint]:
        """List all blueprint versions for a project.
        
        Args:
            project_id: Project identifier.
        
        Returns:
            List of ManuscriptBlueprint objects (sorted by version descending).
        """
        cursor = self.db.aql.execute(
            f"""
            FOR b IN {MANUSCRIPT_BLUEPRINTS_COLLECTION}
            FILTER b.project_id == @project_id
            SORT b.version DESC
            RETURN b
            """,
            bind_vars={"project_id": project_id},
        )
        
        return [ManuscriptBlueprint(**doc) for doc in cursor]
