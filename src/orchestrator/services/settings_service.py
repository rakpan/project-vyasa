"""
Settings Service for Project Vyasa.

Handles persistence and retrieval of system settings (singleton document).
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ..schemas.settings import SystemSettings
from ...shared.logger import get_logger
from ...shared.utils import get_utc_now

logger = get_logger("orchestrator", __name__)

SYSTEM_SETTINGS_COLLECTION = "system_settings"
SYSTEM_SETTINGS_KEY = "system_settings"


class SettingsService:
    """Service for managing system settings."""
    
    def __init__(self, db: StandardDatabase) -> None:
        """Initialize the settings service.
        
        Args:
            db: ArangoDB database instance.
        """
        self.db = db
        self._ensure_collection()
    
    def _ensure_collection(self) -> None:
        """Ensure the system_settings collection exists."""
        if not self.db.has_collection(SYSTEM_SETTINGS_COLLECTION):
            self.db.create_collection(SYSTEM_SETTINGS_COLLECTION)
            logger.info(f"Created collection: {SYSTEM_SETTINGS_COLLECTION}")
    
    def get_settings(self) -> SystemSettings:
        """Get current system settings (singleton).
        
        Returns:
            SystemSettings instance. If no settings exist, returns default settings.
        """
        try:
            coll = self.db.collection(SYSTEM_SETTINGS_COLLECTION)
            doc = coll.get(SYSTEM_SETTINGS_KEY)
            
            if doc:
                # Remove ArangoDB internal fields
                doc.pop("_id", None)
                doc.pop("_rev", None)
                return SystemSettings.model_validate(doc)
            else:
                # Return default settings if none exist
                logger.info("No system settings found, returning defaults")
                return SystemSettings()
        except ArangoError as e:
            logger.warning(f"Failed to retrieve system settings: {e}, returning defaults")
            return SystemSettings()
        except Exception as e:
            logger.error(f"Unexpected error retrieving system settings: {e}", exc_info=True)
            return SystemSettings()
    
    def update_settings(
        self,
        settings: SystemSettings,
        updated_by: Optional[str] = None,
    ) -> SystemSettings:
        """Update system settings (singleton).
        
        Args:
            settings: SystemSettings to save.
            updated_by: Optional user/system identifier that made the update.
        
        Returns:
            Updated SystemSettings with updated_at timestamp.
        
        Raises:
            ValueError: If validation fails.
            ArangoError: If database operation fails.
        """
        # Set updated timestamp and user
        settings.updated_at = get_utc_now()
        settings.updated_by = updated_by
        settings._key = SYSTEM_SETTINGS_KEY
        
        try:
            coll = self.db.collection(SYSTEM_SETTINGS_COLLECTION)
            settings_dict = settings.model_dump(mode="json", exclude_none=True)
            
            # Use insert with overwrite=True for upsert behavior
            coll.insert(settings_dict, overwrite=True)
            
            logger.info(
                "Updated system settings",
                extra={"payload": {"updated_by": updated_by}}
            )
            
            return settings
        except ArangoError as e:
            logger.error(f"Failed to update system settings: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating system settings: {e}", exc_info=True)
            raise
