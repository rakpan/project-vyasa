"""
Settings API endpoints for Project Vyasa.

Provides CRUD operations for system settings including vocabulary guard.
"""

from typing import List, Optional
from flask import Blueprint, request, jsonify
from pydantic import ValidationError

from ...shared.vocab_guard_service import get_vocab_guard_service, VocabGuardService
from ...shared.schema import ForbiddenWord
from ...shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, get_arango_password
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")


def _get_vocab_service() -> Optional[VocabGuardService]:
    """Get VocabGuardService instance (uses global singleton)."""
    try:
        # Use global singleton (already initialized on orchestrator startup)
        return get_vocab_guard_service()
    except Exception as e:
        logger.error(f"Failed to get VocabGuardService: {e}", exc_info=True)
        return None


@settings_bp.route("/vocab-guard", methods=["GET"])
def get_vocab_guard_words():
    """Get all forbidden words from database.
    
    Returns:
        JSON response with list of forbidden words.
    """
    try:
        service = _get_vocab_service()
        if not service:
            return jsonify({"error": "VocabGuardService unavailable"}), 500
        
        words = service.list_words(include_inactive=False)
        
        # Convert to frontend format
        forbidden_words = []
        for word_obj in words:
            forbidden_words.append({
                "word": word_obj.word,
                "alternative": word_obj.alternative or ""
            })
        
        return jsonify({"forbidden_words": forbidden_words})
        
    except Exception as e:
        logger.error(f"Failed to get forbidden words: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/vocab-guard", methods=["POST"])
def update_vocab_guard():
    """Update forbidden words in database.
    
    Request body:
        {
            "forbidden_words": [
                {"word": "crisis", "alternative": "significant challenge"},
                ...
            ]
        }
    
    Returns:
        JSON response with success status.
    """
    try:
        service = _get_vocab_service()
        if not service:
            return jsonify({"error": "VocabGuardService unavailable"}), 500
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        forbidden_words = data.get("forbidden_words", [])
        if not isinstance(forbidden_words, list):
            return jsonify({"error": "forbidden_words must be an array"}), 400
        
        # Get current words from DB
        current_words = {w.word: w for w in service.list_words(include_inactive=True)}
        
        # Track words to keep
        words_to_keep = set()
        
        # Add or update words
        for item in forbidden_words:
            if not isinstance(item, dict):
                continue
            
            word = item.get("word", "").strip().lower()
            if not word:
                continue
            
            alternative = item.get("alternative", "").strip()
            words_to_keep.add(word)
            
            # Add or update word
            try:
                service.add_word(word, alternative=alternative if alternative else None)
            except Exception as e:
                logger.error(f"Failed to add/update word '{word}': {e}", exc_info=True)
                # Continue with other words
        
        # Soft-delete words that are no longer in the list
        for word_key in current_words:
            if word_key not in words_to_keep:
                try:
                    service.remove_word(word_key, soft_delete=True)
                except Exception as e:
                    logger.error(f"Failed to remove word '{word_key}': {e}", exc_info=True)
        
        return jsonify({
            "success": True,
            "message": "Vocabulary guard settings updated successfully"
        })
        
    except Exception as e:
        logger.error(f"Failed to update forbidden words: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/vocab-guard/<word>", methods=["DELETE"])
def delete_vocab_word(word: str):
    """Delete a forbidden word (soft delete by default).
    
    Args:
        word: The word to delete.
    
    Query params:
        hard: If "true", permanently delete. Otherwise soft delete (mark inactive).
    
    Returns:
        JSON response with success status.
    """
    try:
        service = _get_vocab_service()
        if not service:
            return jsonify({"error": "VocabGuardService unavailable"}), 500
        
        hard_delete = request.args.get("hard", "").lower() == "true"
        service.remove_word(word, soft_delete=not hard_delete)
        
        return jsonify({
            "success": True,
            "message": f"Word '{word}' {'deleted' if hard_delete else 'deactivated'} successfully"
        })
        
    except Exception as e:
        logger.error(f"Failed to delete word '{word}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

