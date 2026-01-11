"""
Prompt Profile Service for Project Vyasa.

Handles persistence, versioning, and activation of prompt profiles.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ..schemas.settings import PromptProfile, ActivePromptSet
from ...shared.logger import get_logger
from ...shared.utils import get_utc_now

logger = get_logger("orchestrator", __name__)

PROMPT_PROFILES_COLLECTION = "prompt_profiles"
ACTIVE_PROMPT_SET_COLLECTION = "active_prompt_set"
ACTIVE_PROMPT_SET_KEY = "active_prompt_set"


class PromptProfileService:
    """Service for managing versioned PromptProfiles and the active prompt set in ArangoDB."""
    
    def __init__(self, db: StandardDatabase) -> None:
        """Initialize the PromptProfileService.
        
        Args:
            db: ArangoDB database instance.
        """
        self.db = db
        self._ensure_collections()
    
    def _parse_ts(self, value: Any) -> Optional[datetime]:
        """Parse a timestamp value into a timezone-aware UTC datetime.
        
        Handles multiple input formats:
        - datetime object (ensures tz-aware, assumes UTC if naive)
        - ISO 8601 string (handles Z, +00:00, fractional seconds)
        - None or invalid -> returns None
        
        Args:
            value: Timestamp value (datetime, str, or None).
        
        Returns:
            Timezone-aware UTC datetime, or None if unparseable.
        """
        if value is None:
            return None
        
        # If already a datetime object
        if isinstance(value, datetime):
            if value.tzinfo is None:
                # Naive datetime: assume UTC
                return value.replace(tzinfo=timezone.utc)
            # Already timezone-aware: convert to UTC
            return value.astimezone(timezone.utc)
        
        # If string, try to parse
        if isinstance(value, str):
            if not value.strip():
                return None
            
            try:
                # Handle common ISO 8601 formats
                normalized = value.strip()
                
                # Replace Z with +00:00 for fromisoformat compatibility
                if normalized.endswith("Z"):
                    normalized = normalized[:-1] + "+00:00"
                
                # Check if timezone is already present
                has_tz = False
                # Look for pattern like +HH:MM or -HH:MM at the end
                tz_pattern = r'[+-]\d{2}:\d{2}$'
                if re.search(tz_pattern, normalized):
                    has_tz = True
                
                # If no timezone indicator, assume UTC
                if not has_tz:
                    normalized = normalized + "+00:00"
                
                dt = datetime.fromisoformat(normalized)
                
                # Ensure timezone-aware
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    # Convert to UTC
                    dt = dt.astimezone(timezone.utc)
                
                return dt
            except (ValueError, TypeError) as e:
                logger.debug(f"Failed to parse timestamp '{value}': {e}")
                return None
        
        # Unsupported type
        logger.debug(f"Unsupported timestamp type: {type(value)}")
        return None
    
    def _ensure_collections(self) -> None:
        """Ensure required collections exist with proper indexes."""
        # Prompt profiles collection
        if not self.db.has_collection(PROMPT_PROFILES_COLLECTION):
            self.db.create_collection(PROMPT_PROFILES_COLLECTION)
            logger.info(f"Created collection: {PROMPT_PROFILES_COLLECTION}")
        
        coll = self.db.collection(PROMPT_PROFILES_COLLECTION)
        try:
            # Index for efficient queries
            coll.ensure_persistent_index(["prompt_id", "version"], unique=True)
            coll.ensure_persistent_index(["prompt_id"])
            coll.ensure_persistent_index(["version"])
        except ArangoError:
            # Indexes may already exist
            pass
        
        # Active prompt set collection
        if not self.db.has_collection(ACTIVE_PROMPT_SET_COLLECTION):
            self.db.create_collection(ACTIVE_PROMPT_SET_COLLECTION)
            logger.info(f"Created collection: {ACTIVE_PROMPT_SET_COLLECTION}")
    
    def get_latest_version(self, prompt_id: str) -> Optional[int]:
        """Get the latest version number for a prompt_id.
        
        Args:
            prompt_id: Prompt identifier.
        
        Returns:
            Latest version number, or None if no versions exist.
        """
        try:
            query = f"""
            FOR p IN {PROMPT_PROFILES_COLLECTION}
                FILTER p.prompt_id == @prompt_id
                SORT p.version DESC
                LIMIT 1
                RETURN p.version
            """
            cursor = self.db.aql.execute(query, bind_vars={"prompt_id": prompt_id})
            result = list(cursor)
            return result[0] if result else None
        except ArangoError as e:
            logger.warning(f"Failed to get latest version for {prompt_id}: {e}")
            return None
    
    def create_profile(
        self,
        prompt_id: str,
        template: str,
        output_type: str,
        required_fields: List[str],
        constraints: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> PromptProfile:
        """Create a new prompt profile version.
        
        Args:
            prompt_id: Prompt identifier.
            template: Prompt template text.
            output_type: Output type ('json' or 'markdown').
            required_fields: Required fields for JSON output (must be non-empty if output_type='json').
            constraints: Optional constraints dictionary.
            created_by: Optional user/system identifier that created this version.
        
        Returns:
            Created PromptProfile with auto-incremented version.
        
        Raises:
            ValueError: If validation fails.
            ArangoError: If database operation fails.
        """
        # Get next version number
        latest_version = self.get_latest_version(prompt_id)
        next_version = (latest_version or 0) + 1
        
        # Create profile
        from ..schemas.settings import PromptConstraints
        constraints_obj = PromptConstraints.model_validate(constraints or {})
        
        profile = PromptProfile(
            key=f"{prompt_id}_v{next_version}",
            prompt_id=prompt_id,
            version=next_version,
            template=template,
            output_type=output_type,
            required_fields=required_fields,
            constraints=constraints_obj,
            created_by=created_by,
        )
        
        try:
            coll = self.db.collection(PROMPT_PROFILES_COLLECTION)
            profile_dict = profile.model_dump(mode="json", exclude_none=True)
            coll.insert(profile_dict)
            
            logger.info(
                f"Created prompt profile version",
                extra={
                    "payload": {
                        "prompt_id": prompt_id,
                        "version": next_version,
                        "created_by": created_by,
                    }
                }
            )
            
            return profile
        except ArangoError as e:
            logger.error(f"Failed to create prompt profile: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating prompt profile: {e}", exc_info=True)
            raise
    
    def update_validation_status(
        self,
        prompt_id: str,
        version: int,
        validation_result: Dict[str, Any],
    ) -> None:
        """Update validation status for a prompt profile version.
        
        Updates validation status regardless of whether validation passed or failed.
        This ensures that failed validations are persisted and visible on reload.
        
        Args:
            prompt_id: Prompt identifier.
            version: Version number.
            validation_result: Dict with 'valid' (bool) and 'errors' (List[str]).
                Must include 'valid' key. 'errors' defaults to empty list if missing.
        
        Raises:
            ValueError: If prompt_id/version combination not found in database.
            ArangoError: If database operation fails.
        """
        try:
            coll = self.db.collection(PROMPT_PROFILES_COLLECTION)
            key = f"{prompt_id}_v{version}"
            doc = coll.get(key)
            
            if not doc:
                raise ValueError(f"Prompt profile {prompt_id} v{version} not found. Cannot update validation status.")
            
            # Determine validation status from result
            is_valid = validation_result.get("valid", False)
            validation_status = "valid" if is_valid else "invalid"
            
            # Get errors list (default to empty if missing)
            validation_errors = validation_result.get("errors", [])
            if not isinstance(validation_errors, list):
                validation_errors = []
            
            # Update document with validation status, timestamp, and errors
            doc["validation_status"] = validation_status
            doc["validation_timestamp"] = get_utc_now().isoformat()
            doc["validation_errors"] = validation_errors
            
            coll.update(doc)
            
            logger.info(
                f"Updated validation status for {prompt_id} v{version}",
                extra={
                    "payload": {
                        "prompt_id": prompt_id,
                        "version": version,
                        "validation_status": validation_status,
                        "valid": is_valid,
                        "error_count": len(validation_errors),
                    }
                }
            )
        except ValueError as e:
            # Re-raise ValueError (profile not found)
            logger.error(f"Failed to update validation status: {e}", exc_info=True)
            raise
        except ArangoError as e:
            logger.error(f"ArangoDB error updating validation status: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating validation status: {e}", exc_info=True)
            raise
    
    def get_profile(self, prompt_id: str, version: Optional[int] = None) -> Optional[PromptProfile]:
        """Get a prompt profile by ID and version.
        
        Args:
            prompt_id: Prompt identifier.
            version: Version number. If None, returns the active version (or latest if no active).
        
        Returns:
            PromptProfile if found, None otherwise.
        """
        try:
            if version is None:
                # Get active version
                active_set = self.get_active_prompt_set()
                version = active_set.active_versions.get(prompt_id)
                
                # If no active version, get latest
                if version is None:
                    version = self.get_latest_version(prompt_id)
                    if version is None:
                        return None
            
            coll = self.db.collection(PROMPT_PROFILES_COLLECTION)
            key = f"{prompt_id}_v{version}"
            doc = coll.get(key)
            
            if doc:
                doc.pop("_id", None)
                doc.pop("_rev", None)
                # Parse validation_timestamp using shared helper
                if "validation_timestamp" in doc:
                    parsed_ts = self._parse_ts(doc["validation_timestamp"])
                    if parsed_ts is not None:
                        doc["validation_timestamp"] = parsed_ts
                    # If parsing fails, keep original value (Pydantic will handle validation)
                return PromptProfile.model_validate(doc)
            
            return None
        except ArangoError as e:
            logger.warning(f"Failed to get prompt profile {prompt_id} v{version}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting prompt profile: {e}", exc_info=True)
            return None
    
    def list_profiles(self, prompt_id: Optional[str] = None) -> List[PromptProfile]:
        """List prompt profiles, optionally filtered by prompt_id.
        
        Args:
            prompt_id: Optional prompt identifier to filter by.
        
        Returns:
            List of PromptProfile objects.
        """
        try:
            if prompt_id:
                query = f"""
                FOR p IN {PROMPT_PROFILES_COLLECTION}
                    FILTER p.prompt_id == @prompt_id
                    SORT p.version DESC
                    RETURN p
                """
                bind_vars = {"prompt_id": prompt_id}
            else:
                query = f"""
                FOR p IN {PROMPT_PROFILES_COLLECTION}
                    SORT p.prompt_id, p.version DESC
                    RETURN p
                """
                bind_vars = {}
            
            cursor = self.db.aql.execute(query, bind_vars=bind_vars)
            profiles = []
            for doc in cursor:
                doc.pop("_id", None)
                doc.pop("_rev", None)
                # Parse validation_timestamp using shared helper
                if "validation_timestamp" in doc:
                    parsed_ts = self._parse_ts(doc["validation_timestamp"])
                    if parsed_ts is not None:
                        doc["validation_timestamp"] = parsed_ts
                    # If parsing fails, keep original value (Pydantic will handle validation)
                profiles.append(PromptProfile.model_validate(doc))
            
            return profiles
        except ArangoError as e:
            logger.warning(f"Failed to list prompt profiles: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing prompt profiles: {e}", exc_info=True)
            return []
    
    def get_active_prompt_set(self) -> ActivePromptSet:
        """Get active prompt version mapping (singleton).
        
        Returns:
            ActivePromptSet instance. If none exists, returns empty set.
        """
        try:
            coll = self.db.collection(ACTIVE_PROMPT_SET_COLLECTION)
            doc = coll.get(ACTIVE_PROMPT_SET_KEY)
            
            if doc:
                doc.pop("_id", None)
                doc.pop("_rev", None)
                return ActivePromptSet.model_validate(doc)
            else:
                return ActivePromptSet()
        except ArangoError as e:
            logger.warning(f"Failed to retrieve active prompt set: {e}, returning empty set")
            return ActivePromptSet()
        except Exception as e:
            logger.error(f"Unexpected error retrieving active prompt set: {e}", exc_info=True)
            return ActivePromptSet()
    
    def activate_version(
        self,
        prompt_id: str,
        version: int,
        updated_by: Optional[str] = None,
    ) -> ActivePromptSet:
        """Activate a specific prompt profile version.
        
        Safety checks:
        - Version must exist
        - Last validation must have passed (validation_status == 'valid')
        - Validation timestamp must be recent (within 30 minutes)
        
        Args:
            prompt_id: Prompt identifier.
            version: Version number to activate.
            updated_by: Optional user/system identifier that made the activation.
        
        Returns:
            Updated ActivePromptSet.
        
        Raises:
            ValueError: If the specified version does not exist, validation failed, or validation is stale.
            ArangoError: If database operation fails.
        """
        # Verify version exists
        profile = self.get_profile(prompt_id, version)
        if not profile:
            raise ValueError(f"Prompt profile {prompt_id} v{version} does not exist")
        
        # Safety check 1: Validation must have passed
        if profile.validation_status != "valid":
            if profile.validation_status == "invalid":
                error_msg = f"Cannot activate {prompt_id} v{version}: validation failed. Errors: {', '.join(profile.validation_errors[:3])}"
                if len(profile.validation_errors) > 3:
                    error_msg += f" (and {len(profile.validation_errors) - 3} more)"
                raise ValueError(error_msg)
            else:
                raise ValueError(
                    f"Cannot activate {prompt_id} v{version}: not validated. "
                    "Please validate the template before activation."
                )
        
        # Safety check 2: Validation timestamp must be recent (within 30 minutes)
        validation_time = self._parse_ts(profile.validation_timestamp)
        
        if validation_time is None:
            # Missing or unparseable timestamp -> block activation
            raise ValueError(
                f"Cannot activate {prompt_id} v{version}: validation timestamp missing or invalid. "
                "Please validate the template before activation."
            )
        
        # Compute age using tz-aware datetimes only
        now = get_utc_now()
        age = now - validation_time
        
        if age > timedelta(minutes=30):
            raise ValueError(
                f"Cannot activate {prompt_id} v{version}: validation is stale (age: {age.total_seconds() / 60:.1f} minutes). "
                "Please re-validate the template before activation."
            )
        
        # Get or create active prompt set
        active_set = self.get_active_prompt_set()
        active_set.active_versions[prompt_id] = version
        active_set.updated_at = get_utc_now()
        active_set.updated_by = updated_by
        active_set.key = ACTIVE_PROMPT_SET_KEY
        
        try:
            coll = self.db.collection(ACTIVE_PROMPT_SET_COLLECTION)
            active_set_dict = active_set.model_dump(mode="json", exclude_none=True)
            coll.insert(active_set_dict, overwrite=True)
            
            logger.info(
                f"Activated prompt profile version",
                extra={
                    "payload": {
                        "prompt_id": prompt_id,
                        "version": version,
                        "updated_by": updated_by,
                        "validation_status": profile.validation_status,
                        "validation_age_minutes": age.total_seconds() / 60,
                    }
                }
            )
            
            return active_set
        except ArangoError as e:
            logger.error(f"Failed to activate prompt profile version: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error activating prompt profile version: {e}", exc_info=True)
            raise
    
    def validate_template(
        self,
        template: str,
        output_type: str,
        required_fields: List[str],
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validate a prompt template without saving it.
        
        Enhanced validation:
        - For JSON: required_fields must be present, JSON schema check
        - For Markdown: citation token format, mandatory clauses
        
        Args:
            template: Prompt template text to validate.
            output_type: Output type ('json' or 'markdown').
            required_fields: Required fields for JSON output.
            constraints: Optional constraints dictionary.
        
        Returns:
            Dict with 'valid' (bool), 'errors' (List[str]), and 'warnings' (List[str]) keys.
        """
        errors = []
        warnings = []
        
        # Validate template is non-empty
        if not template or not template.strip():
            errors.append("Template must be non-empty")
            return {"valid": False, "errors": errors, "warnings": warnings}
        
        # Validate output_type
        if output_type not in ("json", "markdown"):
            errors.append("output_type must be 'json' or 'markdown'")
            return {"valid": False, "errors": errors, "warnings": warnings}
        
        # Parse constraints
        from ..schemas.settings import PromptConstraints
        constraints_obj = None
        if constraints:
            try:
                constraints_obj = PromptConstraints.model_validate(constraints)
            except Exception as e:
                errors.append(f"Invalid constraints: {str(e)}")
        
        # JSON-specific validation
        if output_type == "json":
            if not required_fields:
                errors.append("required_fields must be non-empty for output_type='json'")
            else:
                # Lightweight JSON schema check: verify template mentions required fields
                template_lower = template.lower()
                missing_fields = []
                for field in required_fields:
                    # Check if field is mentioned in template (as JSON key or in instructions)
                    field_patterns = [
                        f'"{field}"',  # JSON key
                        f"'{field}'",  # JSON key (single quotes)
                        field,  # Direct mention
                    ]
                    if not any(pattern in template_lower for pattern in field_patterns):
                        missing_fields.append(field)
                
                if missing_fields:
                    warnings.append(
                        f"Template may not produce required fields: {', '.join(missing_fields)}. "
                        "Ensure the prompt instructs the LLM to include these fields in JSON output."
                    )
                
                # Check for JSON structure hints
                if "json" not in template_lower and "{" not in template:
                    warnings.append("Template may not instruct JSON output format. Consider adding explicit JSON format instructions.")
        
        # Markdown-specific validation
        if output_type == "markdown":
            # Check citation token format rule exists
            if constraints_obj and constraints_obj.citation_token_format:
                citation_format = constraints_obj.citation_token_format
                # Check if template mentions citation format
                if citation_format not in template and "citation" not in template.lower():
                    warnings.append(
                        f"Template may not enforce citation format '{citation_format}'. "
                        "Ensure the prompt instructs the LLM to use this format."
                    )
            
            # Check for mandatory clauses if configured
            if constraints_obj and constraints_obj.packet_a_facts_only:
                if "packet a" not in template_lower and "evidence pack" not in template_lower:
                    warnings.append(
                        "Template may not enforce 'Packet A facts-only' rule. "
                        "Ensure the prompt instructs the LLM to cite only from Packet A (EvidencePack)."
                    )
            
            # Check for Packet B style-only mention
            if "packet b" not in template_lower and "analytical notes" not in template_lower:
                warnings.append(
                    "Template may not clarify Packet B (Analytical Notes) is style-only, not citeable. "
                    "Consider adding explicit instruction that Packet B is for style influence only."
                )
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }
