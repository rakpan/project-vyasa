"""
Settings API endpoints for Project Vyasa.

Provides CRUD operations for system settings including vocabulary guard,
system settings, and prompt profiles.
"""

import os
from typing import List, Optional, Dict, Any
from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from arango import ArangoClient

from ...shared.vocab_guard_service import get_vocab_guard_service, VocabGuardService
from ...shared.schema import ForbiddenWord
from ...shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, get_arango_password
from ...shared.logger import get_logger
from ..services.settings_service import SettingsService
from ..services.prompt_profile_service import PromptProfileService
from ..schemas.settings import SystemSettings, PromptProfile

logger = get_logger("orchestrator", __name__)

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")


def _is_debug_mode() -> bool:
    """Check if running in debug/development mode.
    
    Returns:
        True if DEBUG mode is enabled (FLASK_ENV=development or DEBUG=true).
    """
    flask_env = os.getenv("FLASK_ENV", "").lower()
    debug_flag = os.getenv("DEBUG", "").lower()
    return flask_env == "development" or debug_flag in ("true", "1", "yes")


def _error_response(error_summary: str, details: Optional[List[str]] = None, exception: Optional[Exception] = None) -> tuple:
    """Create a standardized error response.
    
    Args:
        error_summary: High-level error message (always included).
        details: Optional list of detailed error messages (included if provided).
        exception: Optional exception object (details included in debug mode only).
    
    Returns:
        Tuple of (jsonify response dict, status_code).
        Status code defaults to 500 for exceptions, 400 for validation errors.
    """
    response = {"error": error_summary}
    
    # Add details if provided
    if details:
        response["details"] = details
    
    # In debug mode, include exception details
    if exception and _is_debug_mode():
        if "details" not in response:
            response["details"] = []
        if not isinstance(response["details"], list):
            response["details"] = [response["details"]]
        response["details"].append(f"Exception: {str(exception)}")
    
    # Determine status code
    status_code = 500  # Default for server errors
    if "validation" in error_summary.lower() or "required" in error_summary.lower() or "invalid" in error_summary.lower():
        status_code = 400
    
    return jsonify(response), status_code


def _get_db():
    """Get ArangoDB database instance."""
    try:
        client = ArangoClient(hosts=get_memory_url())
        return client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}", exc_info=True)
        return None


def _get_settings_service() -> Optional[SettingsService]:
    """Get SettingsService instance."""
    db = _get_db()
    if not db:
        return None
    return SettingsService(db)


def _get_prompt_profile_service() -> Optional[PromptProfileService]:
    """Get PromptProfileService instance."""
    db = _get_db()
    if not db:
        return None
    return PromptProfileService(db)


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
            return _error_response("VocabGuardService unavailable")
        
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
        return _error_response("Failed to get forbidden words", exception=e)


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
            return _error_response("VocabGuardService unavailable")
        
        data = request.get_json()
        if not data:
            return _error_response("Request body required", details=["Request body must be valid JSON"])
        
        forbidden_words = data.get("forbidden_words", [])
        if not isinstance(forbidden_words, list):
            return _error_response("Invalid request", details=["Field 'forbidden_words' must be an array"])
        
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
        return _error_response("Failed to update forbidden words", exception=e)


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
            return _error_response("VocabGuardService unavailable")
        
        hard_delete = request.args.get("hard", "").lower() == "true"
        service.remove_word(word, soft_delete=not hard_delete)
        
        return jsonify({
            "success": True,
            "message": f"Word '{word}' {'deleted' if hard_delete else 'deactivated'} successfully"
        })
        
    except Exception as e:
        logger.error(f"Failed to delete word '{word}': {e}", exc_info=True)
        return _error_response("Failed to delete word", exception=e)


# ============================================================================
# System Settings Endpoints
# ============================================================================

@settings_bp.route("", methods=["GET"])
def get_system_settings():
    """Get current system settings.
    
    Returns:
        JSON response with system settings (runtime budgets, manuscript defaults, feature flags).
    """
    try:
        service = _get_settings_service()
        if not service:
            return _error_response("Database unavailable")
        
        settings = service.get_settings()
        return jsonify(settings.model_dump(mode="json", exclude_none=True)), 200
        
    except Exception as e:
        logger.error(f"Failed to get system settings: {e}", exc_info=True)
        return _error_response("Failed to get system settings", exception=e)


@settings_bp.route("", methods=["POST"])
def update_system_settings():
    """Update system settings.
    
    Request body:
        {
            "runtime_budgets": {...},
            "manuscript_defaults": {...},
            "feature_flags": {...},
            "updated_by": "user@example.com" (optional)
        }
    
    Returns:
        JSON response with updated settings (includes updated_by and updated_at).
    """
    try:
        service = _get_settings_service()
        if not service:
            return _error_response("Database unavailable")
        
        data = request.get_json()
        if not data:
            return _error_response("Request body required", details=["Request body must be valid JSON"])
        
        # Get current settings and merge updates
        current_settings = service.get_settings()
        current_dict = current_settings.model_dump(mode="json", exclude_none=True)
        
        # Merge updates (preserve existing values if not provided)
        if "runtime_budgets" in data:
            if "tier_a" in data["runtime_budgets"]:
                current_dict.setdefault("runtime_budgets", {}).setdefault("tier_a", {}).update(data["runtime_budgets"]["tier_a"])
            if "tier_b" in data["runtime_budgets"]:
                current_dict.setdefault("runtime_budgets", {}).setdefault("tier_b", {}).update(data["runtime_budgets"]["tier_b"])
        
        if "manuscript_defaults" in data:
            current_dict.setdefault("manuscript_defaults", {}).update(data["manuscript_defaults"])
        
        if "feature_flags" in data:
            current_dict.setdefault("feature_flags", {}).update(data["feature_flags"])
        
        # Validate and update
        try:
            updated_settings = SystemSettings.model_validate(current_dict)
        except ValidationError as e:
            return _error_response("Invalid settings", details=e.errors())
        
        # Use provided updated_by or fall back to remote_addr
        updated_by = data.get("updated_by") or request.remote_addr
        updated_settings = service.update_settings(updated_settings, updated_by=updated_by)
        
        return jsonify(updated_settings.model_dump(mode="json", exclude_none=True)), 200
        
    except ValidationError as e:
        return _error_response("Validation failed", details=e.errors())
    except Exception as e:
        logger.error(f"Failed to update system settings: {e}", exc_info=True)
        return _error_response("Failed to update system settings", exception=e)


# ============================================================================
# Prompt Profile Endpoints
# ============================================================================

@settings_bp.route("/prompts", methods=["GET"])
def get_prompt_profiles():
    """Get prompt profiles, optionally filtered by prompt_id.
    
    Query params:
        prompt_id: Optional prompt identifier to filter by.
    
    Returns:
        JSON response with list of prompt profiles.
    """
    try:
        service = _get_prompt_profile_service()
        if not service:
            return _error_response("Database unavailable")
        
        prompt_id = request.args.get("prompt_id")
        profiles = service.list_profiles(prompt_id=prompt_id)
        
        return jsonify([p.model_dump(mode="json", exclude_none=True) for p in profiles]), 200
        
    except Exception as e:
        logger.error(f"Failed to get prompt profiles: {e}", exc_info=True)
        return _error_response("Failed to get prompt profiles", exception=e)


@settings_bp.route("/prompts", methods=["POST"])
def create_prompt_profile():
    """Create a new prompt profile version.
    
    Note: New versions are created as drafts (validation_status=None).
    They must be validated before activation.
    
    Request body:
        {
            "prompt_id": "critic_verify",
            "template": "...",
            "output_type": "json",
            "required_fields": ["decision", "rationale"],
            "constraints": {...},
            "created_by": "user@example.com" (optional)
        }
    
    Returns:
        JSON response with created prompt profile (including version).
    """
    try:
        service = _get_prompt_profile_service()
        if not service:
            return _error_response("Database unavailable")
        
        data = request.get_json()
        if not data:
            return _error_response("Request body required", details=["Request body must be valid JSON"])
        
        prompt_id = data.get("prompt_id")
        template = data.get("template")
        output_type = data.get("output_type")
        required_fields = data.get("required_fields", [])
        constraints = data.get("constraints")
        created_by = data.get("created_by") or request.remote_addr  # Use IP if not provided
        
        validation_errors = []
        if not prompt_id:
            validation_errors.append("Field 'prompt_id' is required")
        if not template:
            validation_errors.append("Field 'template' is required")
        if not output_type:
            validation_errors.append("Field 'output_type' is required")
        
        if validation_errors:
            return _error_response("Request validation failed", details=validation_errors)
        
        try:
            profile = service.create_profile(
                prompt_id=prompt_id,
                template=template,
                output_type=output_type,
                required_fields=required_fields,
                constraints=constraints,
                created_by=created_by,
            )
            
            return jsonify(profile.model_dump(mode="json", exclude_none=True)), 201
            
        except ValidationError as e:
            return _error_response("Validation failed", details=e.errors())
        except ValueError as e:
            return _error_response("Invalid request", details=[str(e)], exception=e)
        
    except Exception as e:
        logger.error(f"Failed to create prompt profile: {e}", exc_info=True)
        return _error_response("Failed to create prompt profile", exception=e)


@settings_bp.route("/prompts/validate", methods=["POST"])
def validate_prompt_template():
    """Validate a prompt template without saving it.
    
    Enhanced validation with JSON schema checks and Markdown requirements.
    
    Request body:
        {
            "template": "...",
            "output_type": "json",
            "required_fields": ["decision", "rationale"],
            "constraints": {...},
            "prompt_id": "critic_verify",  # Optional: if provided, updates validation status
            "version": 2  # Optional: if provided, updates validation status
        }
    
    Returns:
        JSON response with validation result:
        {
            "valid": bool,
            "errors": [str] (empty if none),
            "warnings": [str] (optional),
            "validation_status": "valid" | "invalid" (always present),
            "validation_timestamp": ISO timestamp with timezone (always present if prompt_id/version provided)
        }
        
        Note: If prompt_id and version are provided, validation status is persisted to DB
        regardless of whether validation passed or failed. The response includes the
        persisted status and timestamp.
    
    Examples:
        Success (valid template):
            Request:
                POST /api/settings/prompts/validate
                {
                    "template": "You are a critic. Analyze the claim and output JSON with 'decision' and 'rationale' fields.",
                    "output_type": "json",
                    "required_fields": ["decision", "rationale"],
                    "prompt_id": "critic_verify",
                    "version": 2
                }
            
            Response (200):
                {
                    "valid": true,
                    "errors": [],
                    "warnings": [],
                    "validation_status": "valid",
                    "validation_timestamp": "2025-01-15T10:30:45.123+00:00"
                }
        
        Invalid (missing required fields):
            Request:
                POST /api/settings/prompts/validate
                {
                    "template": "You are a critic.",
                    "output_type": "json",
                    "required_fields": [],  # Empty!
                    "prompt_id": "critic_verify",
                    "version": 2
                }
            
            Response (200):
                {
                    "valid": false,
                    "errors": ["required_fields must be non-empty when output_type is 'json'"],
                    "warnings": [],
                    "validation_status": "invalid",
                    "validation_timestamp": "2025-01-15T10:30:45.123+00:00"
                }
        
        Request validation error (missing template):
            Request:
                POST /api/settings/prompts/validate
                {
                    "output_type": "json",
                    "required_fields": ["decision"]
                }
            
            Response (400):
                {
                    "error": "Request validation failed",
                    "details": ["Field 'template' is required"]
                }
    """
    try:
        service = _get_prompt_profile_service()
        if not service:
            return _error_response("Database unavailable")
        
        data = request.get_json()
        if not data:
            return _error_response("Request body required", details=["Request body must be valid JSON"])
        
        template = data.get("template")
        output_type = data.get("output_type")
        required_fields = data.get("required_fields", [])
        constraints = data.get("constraints")
        prompt_id = data.get("prompt_id")
        version = data.get("version")
        
        # Validate required fields with clear error messages
        validation_errors = []
        
        # Validate template: must be non-empty string
        if template is None:
            validation_errors.append("Field 'template' is required")
        elif not isinstance(template, str):
            validation_errors.append("Field 'template' must be a string")
        elif not template.strip():
            validation_errors.append("Field 'template' must be non-empty")
        
        # Validate output_type: must be "json" or "markdown"
        if output_type is None:
            validation_errors.append("Field 'output_type' is required")
        elif not isinstance(output_type, str):
            validation_errors.append("Field 'output_type' must be a string")
        elif output_type not in ("json", "markdown"):
            validation_errors.append(f"Field 'output_type' must be 'json' or 'markdown', got '{output_type}'")
        
        # Validate required_fields: must be a list, and non-empty if output_type is "json"
        # Only validate if output_type is valid (to avoid errors when output_type itself is invalid)
        if output_type in ("json", "markdown"):
            if output_type == "json":
                if not isinstance(required_fields, list):
                    validation_errors.append("Field 'required_fields' must be a list when output_type is 'json'")
                elif len(required_fields) == 0:
                    validation_errors.append("Field 'required_fields' must be non-empty when output_type is 'json'")
            elif output_type == "markdown" and required_fields is not None:
                # For markdown, required_fields is optional but if provided should be a list
                if not isinstance(required_fields, list):
                    validation_errors.append("Field 'required_fields' must be a list if provided")
        
        # Return 400 if any validation errors found
        if validation_errors:
            return _error_response("Request validation failed", details=validation_errors)
        
        result = service.validate_template(
            template=template,
            output_type=output_type,
            required_fields=required_fields,
            constraints=constraints,
        )
        
        # Ensure result has required fields with defaults
        if "errors" not in result:
            result["errors"] = []
        if "warnings" not in result:
            result["warnings"] = []
        if "valid" not in result:
            result["valid"] = False
        
        # Determine validation status from result
        validation_status = "valid" if result["valid"] else "invalid"
        
        # If prompt_id and version provided, update validation status in DB (regardless of result.valid)
        if prompt_id and version:
            try:
                # Always update validation status (for both success and failure)
                service.update_validation_status(prompt_id, version, result)
                
                # After updating, enrich result with persisted status and timestamp from DB
                profile = service.get_profile(prompt_id, version)
                if profile:
                    # Use persisted status (should match what we just set)
                    result["validation_status"] = profile.validation_status or validation_status
                    if profile.validation_timestamp:
                        # Ensure timestamp is in ISO format with timezone
                        if isinstance(profile.validation_timestamp, str):
                            result["validation_timestamp"] = profile.validation_timestamp
                        else:
                            result["validation_timestamp"] = profile.validation_timestamp.isoformat()
                    else:
                        # Fallback: should not happen if update succeeded, but handle gracefully
                        from ...shared.utils import get_utc_now
                        result["validation_timestamp"] = get_utc_now().isoformat()
                else:
                    # Fallback if profile not found after update (should not happen)
                    result["validation_status"] = validation_status
                    from ...shared.utils import get_utc_now
                    result["validation_timestamp"] = get_utc_now().isoformat()
            except Exception as e:
                logger.warning(f"Failed to update validation status: {e}", exc_info=True)
                # Non-fatal: validation result still returned with computed (not persisted) status
                result["validation_status"] = validation_status
                from ...shared.utils import get_utc_now
                result["validation_timestamp"] = get_utc_now().isoformat()
        else:
            # If not persisting, still include status in response (computed, not persisted)
            result["validation_status"] = validation_status
            from ...shared.utils import get_utc_now
            result["validation_timestamp"] = get_utc_now().isoformat()
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Failed to validate prompt template: {e}", exc_info=True)
        return _error_response("Failed to validate prompt template", exception=e)


@settings_bp.route("/prompts/activate", methods=["POST"])
def activate_prompt_version():
    """Activate a specific prompt profile version.
    
    Safety checks:
    - Version must exist
    - Last validation must have passed (validation_status == "valid")
    - Validation timestamp must be recent (within 30 minutes)
    
    Request body:
        {
            "prompt_id": "critic_verify",
            "version": 2,
            "updated_by": "user@example.com" (optional)
        }
    
    Returns:
        JSON response with updated active prompt set:
        {
            "_key": "active_prompt_set",
            "active_versions": {
                "critic_verify": 2,
                ...
            },
            "updated_at": "2025-01-15T10:30:45.123+00:00",
            "updated_by": "user@example.com"
        }
    
    Examples:
        Success (recent valid validation):
            Request:
                POST /api/settings/prompts/activate
                {
                    "prompt_id": "critic_verify",
                    "version": 2,
                    "updated_by": "user@example.com"
                }
            
            Response (200):
                {
                    "_key": "active_prompt_set",
                    "active_versions": {
                        "critic_verify": 2
                    },
                    "updated_at": "2025-01-15T10:30:45.123+00:00",
                    "updated_by": "user@example.com"
                }
        
        Error: Validation not passed (invalid status):
            Request:
                POST /api/settings/prompts/activate
                {
                    "prompt_id": "critic_verify",
                    "version": 2
                }
            
            Response (400):
                {
                    "error": "Validation failed",
                    "details": [
                        "Cannot activate critic_verify v2: validation failed. Errors: Template must include required fields"
                    ]
                }
        
        Error: Stale validation (older than 30 minutes):
            Request:
                POST /api/settings/prompts/activate
                {
                    "prompt_id": "critic_verify",
                    "version": 2
                }
            
            Response (400):
                {
                    "error": "Validation failed",
                    "details": [
                        "Cannot activate critic_verify v2: validation is stale (age: 35.2 minutes). Please re-validate the template before activation."
                    ]
                }
        
        Error: Missing validation timestamp:
            Request:
                POST /api/settings/prompts/activate
                {
                    "prompt_id": "critic_verify",
                    "version": 2
                }
            
            Response (400):
                {
                    "error": "Validation failed",
                    "details": [
                        "Cannot activate critic_verify v2: validation timestamp missing or invalid. Please validate the template before activation."
                    ]
                }
        
        Error: Version not found:
            Request:
                POST /api/settings/prompts/activate
                {
                    "prompt_id": "critic_verify",
                    "version": 999
                }
            
            Response (400):
                {
                    "error": "Validation failed",
                    "details": [
                        "Prompt profile critic_verify v999 does not exist"
                    ]
                }
    """
    try:
        service = _get_prompt_profile_service()
        if not service:
            return _error_response("Database unavailable")
        
        data = request.get_json()
        if not data:
            return _error_response("Request body required", details=["Request body must be valid JSON"])
        
        prompt_id = data.get("prompt_id")
        version = data.get("version")
        updated_by = data.get("updated_by") or request.remote_addr  # Use IP if not provided
        
        validation_errors = []
        if not prompt_id:
            validation_errors.append("Field 'prompt_id' is required")
        if not version or not isinstance(version, int):
            validation_errors.append("Field 'version' must be a positive integer")
        
        if validation_errors:
            return _error_response("Request validation failed", details=validation_errors)
        
        try:
            active_set = service.activate_version(
                prompt_id=prompt_id,
                version=version,
                updated_by=updated_by,
            )
            
            return jsonify(active_set.model_dump(mode="json", exclude_none=True)), 200
            
        except ValueError as e:
            # Validation failed or stale - return clear error
            return _error_response("Validation failed", details=[str(e)], exception=e)
        
    except Exception as e:
        logger.error(f"Failed to activate prompt version: {e}", exc_info=True)
        return _error_response("Failed to activate prompt version", exception=e)
