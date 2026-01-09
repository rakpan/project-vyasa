"""
Analytical Notes API for Project Vyasa.

Handles CRUD operations for Analytical Notes (Perspectives).
Analytical Notes are user-authored perspectives, analogies, glossaries, and framing ideas.
They are NEVER directly citeable as evidence. They influence style and pedagogy only.
"""

from typing import List, Optional, Dict, Any
from flask import Blueprint, request, jsonify
from pydantic import ValidationError

from ..schemas.analytical_notes import AnalyticalNote, NoteState
from ..services.analytical_notes_service import AnalyticalNotesService
from ...shared.config import get_memory_url, get_arango_password, ARANGODB_DB, ARANGODB_USER
from ...shared.logger import get_logger
from arango import ArangoClient
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

logger = get_logger("orchestrator", __name__)

# Flask Blueprint for notes routes
notes_bp = Blueprint("notes", __name__, url_prefix="/api")


def _get_db() -> Optional[StandardDatabase]:
    """Get ArangoDB database connection.
    
    Returns:
        StandardDatabase instance or None if connection fails.
    """
    try:
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
        return db
    except Exception as e:
        logger.error(f"Failed to connect to ArangoDB: {e}", exc_info=True)
        return None


def _get_notes_service() -> Optional[AnalyticalNotesService]:
    """Get AnalyticalNotesService instance.
    
    Returns:
        AnalyticalNotesService instance or None if DB unavailable.
    """
    db = _get_db()
    if not db:
        return None
    return AnalyticalNotesService(db)


@notes_bp.route("/projects/<project_id>/notes", methods=["GET"])
def list_notes(project_id: str):
    """List Analytical Notes for a project.
    
    Query parameters:
        state: Optional state filter (Draft or Manuscript)
        linked_rq: Optional linked research question ID filter
        tags: Optional comma-separated tags filter
        limit: Optional limit on number of results
    
    Returns:
        JSON array of AnalyticalNote objects.
    """
    service = _get_notes_service()
    if not service:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        # Parse query parameters
        state_str = request.args.get("state")
        state = None
        if state_str:
            try:
                state = NoteState(state_str)
            except ValueError:
                return jsonify({"error": f"Invalid state: {state_str}. Must be 'Draft' or 'Manuscript'."}), 400
        
        linked_rq = request.args.get("linked_rq")
        tags_str = request.args.get("tags")
        tags = tags_str.split(",") if tags_str else None
        
        limit_str = request.args.get("limit")
        limit = int(limit_str) if limit_str else None
        
        # List notes
        notes = service.list_notes(
            project_id=project_id,
            state=state,
            linked_rq=linked_rq,
            tags=tags,
            limit=limit,
        )
        
        return jsonify([note.model_dump() for note in notes]), 200
    
    except Exception as e:
        logger.error(f"Failed to list notes: {e}", exc_info=True)
        return jsonify({"error": "Failed to list notes"}), 500


@notes_bp.route("/projects/<project_id>/notes", methods=["POST"])
def create_note(project_id: str):
    """Create a new Analytical Note.
    
    Request body (JSON):
        {
            "text": str (required),
            "tags": List[str] (optional, default: []),
            "linked_rq": str (optional),
            "source_ref": str (optional),
            "created_by": str (optional),
            "state": str (optional, default: "Draft")
        }
    
    Returns:
        Created AnalyticalNote object.
    """
    service = _get_notes_service()
    if not service:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        payload = request.json or {}
        
        # Validate required fields
        text = payload.get("text", "").strip()
        if not text:
            return jsonify({"error": "Note text is required and cannot be empty"}), 400
        
        # Create note
        note = AnalyticalNote.create(
            text=text,
            project_id=project_id,
            tags=payload.get("tags", []),
            linked_rq=payload.get("linked_rq"),
            source_ref=payload.get("source_ref"),
            created_by=payload.get("created_by"),
        )
        
        # Override state if provided (with validation)
        if "state" in payload:
            state_str = payload["state"]
            try:
                note.state = NoteState(state_str)
            except ValueError:
                return jsonify({"error": f"Invalid state: {state_str}. Must be 'Draft' or 'Manuscript'."}), 400
        
        # Validate: Manuscript state requires promotion_reason
        if note.state == NoteState.MANUSCRIPT and not payload.get("promotion_reason"):
            return jsonify({"error": "Manuscript state requires promotion_reason."}), 400
        
        if payload.get("promotion_reason"):
            note.promotion_reason = payload["promotion_reason"]
        
        # Save note
        note = service.create_note(note)
        
        return jsonify(note.model_dump()), 201
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create note: {e}", exc_info=True)
        return jsonify({"error": "Failed to create note"}), 500


@notes_bp.route("/notes/<note_id>", methods=["GET"])
def get_note(note_id: str):
    """Get an Analytical Note by ID.
    
    Returns:
        AnalyticalNote object or 404 if not found.
    """
    service = _get_notes_service()
    if not service:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        note = service.get_note(note_id)
        if not note:
            return jsonify({"error": "Note not found"}), 404
        
        return jsonify(note.model_dump()), 200
    
    except Exception as e:
        logger.error(f"Failed to get note: {e}", exc_info=True)
        return jsonify({"error": "Failed to get note"}), 500


@notes_bp.route("/notes/<note_id>", methods=["PATCH"])
def update_note(note_id: str):
    """Update an Analytical Note.
    
    Request body (JSON):
        {
            "text": str (optional),
            "tags": List[str] (optional),
            "state": str (optional, "Draft" or "Manuscript"),
            "linked_rq": str (optional),
            "source_ref": str (optional),
            "critic_flags": List[str] (optional),
            "promotion_reason": str (optional, required if state=Manuscript),
        }
    
    Returns:
        Updated AnalyticalNote object or 404 if not found.
    """
    service = _get_notes_service()
    if not service:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        payload = request.json or {}
        
        # Validate state enum if provided
        if "state" in payload:
            state_str = payload["state"]
            try:
                NoteState(state_str)  # Validate enum
            except ValueError:
                return jsonify({"error": f"Invalid state: {state_str}. Must be 'Draft' or 'Manuscript'."}), 400
            
            # Validate: Manuscript state requires promotion_reason
            if state_str == NoteState.MANUSCRIPT.value and not payload.get("promotion_reason"):
                # Check if note already has promotion_reason
                existing_note = service.get_note(note_id)
                if not existing_note or not existing_note.promotion_reason:
                    return jsonify({"error": "Manuscript state requires promotion_reason."}), 400
        
        # Update note
        note = service.update_note(note_id, payload)
        if not note:
            return jsonify({"error": "Note not found"}), 404
        
        return jsonify(note.model_dump()), 200
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to update note: {e}", exc_info=True)
        return jsonify({"error": "Failed to update note"}), 500


@notes_bp.route("/notes/<note_id>", methods=["DELETE"])
def delete_note(note_id: str):
    """Delete an Analytical Note.
    
    Returns:
        204 No Content if deleted, 404 if not found.
    """
    service = _get_notes_service()
    if not service:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        deleted = service.delete_note(note_id)
        if not deleted:
            return jsonify({"error": "Note not found"}), 404
        
        return "", 204
    
    except Exception as e:
        logger.error(f"Failed to delete note: {e}", exc_info=True)
        return jsonify({"error": "Failed to delete note"}), 500
