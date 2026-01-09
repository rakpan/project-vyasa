"""
Analytical Notes Service for Project Vyasa.

Handles persistence and retrieval of Analytical Notes (Perspectives).
Analytical Notes are user-authored perspectives, analogies, glossaries, and framing ideas.
They are NEVER directly citeable as evidence. They influence style and pedagogy only.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ..schemas.analytical_notes import AnalyticalNote, NoteState
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

ANALYTICAL_NOTES_COLLECTION = "analytical_notes"


class AnalyticalNotesService:
    """Service for managing Analytical Notes with state transitions."""
    
    def __init__(self, db: StandardDatabase) -> None:
        """Initialize the analytical notes service.
        
        Args:
            db: ArangoDB database instance.
        """
        self.db = db
        self._ensure_collections()
    
    def _ensure_collections(self) -> None:
        """Ensure required collections exist with proper indexes."""
        if not self.db.has_collection(ANALYTICAL_NOTES_COLLECTION):
            self.db.create_collection(ANALYTICAL_NOTES_COLLECTION)
            logger.info(f"Created collection: {ANALYTICAL_NOTES_COLLECTION}")
        
        coll = self.db.collection(ANALYTICAL_NOTES_COLLECTION)
        
        # Indexes for efficient queries
        try:
            coll.ensure_persistent_index(["note_id"], unique=True)
            coll.ensure_persistent_index(["project_id"])
            coll.ensure_persistent_index(["state"])
            coll.ensure_persistent_index(["linked_rq"])
            coll.ensure_persistent_index(["tags"])
            coll.ensure_persistent_index(["created_at"])
        except ArangoError:
            # Indexes may already exist
            pass
    
    def create_note(
        self,
        note: AnalyticalNote,
    ) -> AnalyticalNote:
        """Create a new Analytical Note.
        
        Args:
            note: AnalyticalNote to create.
        
        Returns:
            Created AnalyticalNote with ArangoDB fields populated.
        
        Raises:
            ValueError: If validation fails (empty text, invalid state).
            ArangoError: If database operation fails.
        """
        # Validate note state enum
        if note.state not in [NoteState.DRAFT, NoteState.MANUSCRIPT]:
            raise ValueError(f"Invalid note state: {note.state}. Must be 'Draft' or 'Manuscript'.")
        
        # Validate: Manuscript state requires promotion_reason
        if note.state == NoteState.MANUSCRIPT and not note.promotion_reason:
            raise ValueError("Manuscript state requires promotion_reason.")
        
        # Ensure timestamps are set
        now_iso = datetime.now(timezone.utc).isoformat()
        if not note.created_at:
            note.created_at = now_iso
        if not note.updated_at:
            note.updated_at = now_iso
        
        # Generate document key
        doc_key = note.note_id
        
        # Convert to dict for ArangoDB
        doc = note.model_dump(exclude={"id", "key"})
        doc["_key"] = doc_key
        
        # Insert into database
        coll = self.db.collection(ANALYTICAL_NOTES_COLLECTION)
        result = coll.insert(doc)
        
        logger.info(
            f"Created Analytical Note",
            extra={
                "payload": {
                    "note_id": note.note_id,
                    "project_id": note.project_id,
                    "state": note.state,
                    "linked_rq": note.linked_rq,
                    "tags_count": len(note.tags),
                }
            }
        )
        
        return note
    
    def get_note(
        self,
        note_id: str,
    ) -> Optional[AnalyticalNote]:
        """Get an Analytical Note by ID.
        
        Args:
            note_id: Note identifier.
        
        Returns:
            AnalyticalNote if found, None otherwise.
        """
        coll = self.db.collection(ANALYTICAL_NOTES_COLLECTION)
        doc = coll.get(note_id)
        
        if not doc:
            return None
        
        return AnalyticalNote(**doc)
    
    def list_notes(
        self,
        project_id: str,
        state: Optional[NoteState] = None,
        linked_rq: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[AnalyticalNote]:
        """List Analytical Notes for a project with optional filters.
        
        Args:
            project_id: Project identifier.
            state: Optional state filter (Draft or Manuscript).
            linked_rq: Optional linked research question ID filter.
            tags: Optional tags filter (notes matching any tag).
            limit: Optional limit on number of results.
        
        Returns:
            List of AnalyticalNote objects.
        """
        filters = ["note.project_id == @project_id"]
        bind_vars = {"project_id": project_id}
        
        if state:
            filters.append("note.state == @state")
            bind_vars["state"] = state.value if isinstance(state, NoteState) else state
        
        if linked_rq:
            filters.append("note.linked_rq == @linked_rq")
            bind_vars["linked_rq"] = linked_rq
        
        if tags:
            # Match notes that have any of the specified tags
            filters.append("LENGTH(INTERSECTION(note.tags, @tags)) > 0")
            bind_vars["tags"] = tags
        
        filter_clause = " AND ".join(filters)
        
        query = f"""
        FOR note IN {ANALYTICAL_NOTES_COLLECTION}
        FILTER {filter_clause}
        SORT note.created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        query += " RETURN note"
        
        cursor = self.db.aql.execute(query, bind_vars=bind_vars)
        
        return [AnalyticalNote(**doc) for doc in cursor]
    
    def update_note(
        self,
        note_id: str,
        updates: Dict[str, Any],
    ) -> Optional[AnalyticalNote]:
        """Update an Analytical Note.
        
        Args:
            note_id: Note identifier.
            updates: Dictionary of fields to update.
        
        Returns:
            Updated AnalyticalNote if found, None otherwise.
        
        Raises:
            ValueError: If validation fails (invalid state, Manuscript without promotion_reason).
        """
        # Get existing note
        note = self.get_note(note_id)
        if not note:
            return None
        
        # Validate state enum if provided
        if "state" in updates:
            state_value = updates["state"]
            if isinstance(state_value, NoteState):
                state_value = state_value.value
            if state_value not in [NoteState.DRAFT.value, NoteState.MANUSCRIPT.value]:
                raise ValueError(f"Invalid note state: {state_value}. Must be 'Draft' or 'Manuscript'.")
            
            # Validate: Manuscript state requires promotion_reason
            if state_value == NoteState.MANUSCRIPT.value:
                # Check if promotion_reason is provided in updates or already exists
                if not updates.get("promotion_reason") and not note.promotion_reason:
                    raise ValueError("Manuscript state requires promotion_reason.")
        
        # Update fields
        for key, value in updates.items():
            if key in ["created_at", "note_id", "project_id"]:
                # Immutable fields - skip
                continue
            setattr(note, key, value)
        
        # Update timestamp
        note.updated_at = datetime.now(timezone.utc).isoformat()
        
        # Convert to dict for ArangoDB
        doc = note.model_dump(exclude={"id", "key"})
        
        # Update in database
        coll = self.db.collection(ANALYTICAL_NOTES_COLLECTION)
        coll.update({"_key": note_id}, doc)
        
        logger.info(
            f"Updated Analytical Note",
            extra={
                "payload": {
                    "note_id": note_id,
                    "project_id": note.project_id,
                    "updated_fields": list(updates.keys()),
                }
            }
        )
        
        return note
    
    def delete_note(
        self,
        note_id: str,
    ) -> bool:
        """Delete an Analytical Note.
        
        Args:
            note_id: Note identifier.
        
        Returns:
            True if deleted, False if not found.
        """
        coll = self.db.collection(ANALYTICAL_NOTES_COLLECTION)
        result = coll.delete(note_id, silent=True)
        
        if result:
            logger.info(
                f"Deleted Analytical Note",
                extra={"payload": {"note_id": note_id}}
            )
            return True
        
        return False
