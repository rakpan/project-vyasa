"""
Vocabulary Guard Service for Project Vyasa.

Manages forbidden vocabulary stored in ArangoDB (system of record).
Automatically seeds from YAML file on first initialization if collection is empty.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from arango import ArangoClient
from arango.database import StandardDatabase
from arango.collection import StandardCollection
from arango.exceptions import ArangoError

from .schema import ForbiddenWord
from .config import (
    MEMORY_URL,
    ARANGODB_DB,
    ARANGODB_USER,
    ARANGODB_PASSWORD
)

logger = logging.getLogger(__name__)

# Collection name for forbidden vocabulary
VOCAB_GUARD_COLLECTION = "vocab_guard"

# Default path to YAML seed file
# Try multiple possible paths (works in both dev and Docker)
def _get_default_yaml_path() -> Path:
    """Get the path to the forbidden_vocab.yaml seed file."""
    # Try /app/deploy (Docker container - mounted volume)
    docker_path = Path("/app/deploy/forbidden_vocab.yaml")
    if docker_path.exists():
        return docker_path
    
    # Try relative to this file (development)
    dev_path = Path(__file__).resolve().parents[2] / "deploy" / "forbidden_vocab.yaml"
    if dev_path.exists():
        return dev_path
    
    # Try /app/deploy-config (Docker container with alternative mount)
    docker_config_path = Path("/app/deploy-config/forbidden_vocab.yaml")
    if docker_config_path.exists():
        return docker_config_path
    
    # Default to Docker path (will be checked in _seed_from_yaml)
    return docker_path

DEFAULT_YAML_PATH = _get_default_yaml_path()


class VocabGuardService:
    """Manages forbidden vocabulary stored in ArangoDB."""
    
    def __init__(
        self,
        arango_url: Optional[str] = None,
        arango_db: Optional[str] = None,
        arango_user: Optional[str] = None,
        arango_password: Optional[str] = None,
        yaml_seed_path: Optional[Path] = None
    ):
        """
        Initialize the Vocabulary Guard Service.
        
        Args:
            arango_url: ArangoDB connection URL. Defaults to MEMORY_URL from config.
            arango_db: ArangoDB database name. Defaults to ARANGODB_DB from config.
            arango_user: ArangoDB username. Defaults to ARANGODB_USER from config.
            arango_password: ArangoDB password. Defaults to ARANGODB_PASSWORD from config.
            yaml_seed_path: Path to YAML seed file. Defaults to deploy/forbidden_vocab.yaml.
        """
        self.arango_url = arango_url or MEMORY_URL
        self.arango_db_name = arango_db or ARANGODB_DB
        self.arango_user = arango_user or ARANGODB_USER
        # Use ARANGO_ROOT_PASSWORD if available (secure mode), otherwise fall back to ARANGODB_PASSWORD
        self.arango_password = arango_password or os.getenv("ARANGO_ROOT_PASSWORD") or ARANGODB_PASSWORD
        self.yaml_seed_path = yaml_seed_path or DEFAULT_YAML_PATH
        self.db: Optional[StandardDatabase] = None
        self._cache: Optional[Dict[str, str]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._init_arangodb()
        self._seed_if_empty()
    
    def _init_arangodb(self):
        """Initialize ArangoDB connection and ensure vocab_guard collection exists."""
        try:
            client = ArangoClient(hosts=self.arango_url)
            sys_db = client.db("_system", username=self.arango_user, password=self.arango_password)
            
            # Check if database exists, create if not
            if not sys_db.has_database(self.arango_db_name):
                sys_db.create_database(self.arango_db_name)
                logger.info(f"Created database '{self.arango_db_name}'")
            
            # Connect to the database
            self.db = client.db(
                self.arango_db_name,
                username=self.arango_user,
                password=self.arango_password
            )
            
            # Ensure vocab_guard collection exists
            if not self.db.has_collection(VOCAB_GUARD_COLLECTION):
                self.db.create_collection(VOCAB_GUARD_COLLECTION)
                logger.info(f"Created collection '{VOCAB_GUARD_COLLECTION}'")
            
            # Create indexes for fast lookups
            collection = self.db.collection(VOCAB_GUARD_COLLECTION)
            
            # Get existing indexes
            existing_indexes = {idx.get("name", idx.get("id", "")): idx for idx in collection.indexes()}
            
            # Index on word for unique lookups
            if "idx_word" not in existing_indexes:
                try:
                    collection.add_index({
                        "type": "persistent",
                        "fields": ["word"],
                        "unique": True,
                        "name": "idx_word"
                    })
                    logger.info(f"Created unique index on 'word' in '{VOCAB_GUARD_COLLECTION}'")
                except ArangoError as e:
                    if "duplicate" not in str(e).lower():
                        logger.warning(f"Failed to create idx_word index: {e}")
            
            # Index on is_active for filtering
            if "idx_is_active" not in existing_indexes:
                try:
                    collection.add_index({
                        "type": "persistent",
                        "fields": ["is_active"],
                        "name": "idx_is_active"
                    })
                    logger.info(f"Created index on 'is_active' in '{VOCAB_GUARD_COLLECTION}'")
                except ArangoError as e:
                    if "duplicate" not in str(e).lower():
                        logger.warning(f"Failed to create idx_is_active index: {e}")
            
            logger.info(f"VocabGuardService initialized: {self.arango_url}/{self.arango_db_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ArangoDB connection: {e}", exc_info=True)
            self.db = None
    
    def _seed_if_empty(self):
        """Automatically seed from YAML if collection is empty (idempotent)."""
        if not self.db:
            logger.warning("ArangoDB not initialized, skipping seed")
            return
        
        try:
            collection = self.db.collection(VOCAB_GUARD_COLLECTION)
            
            # Check if collection is empty
            count = collection.count()
            if count > 0:
                logger.debug(f"vocab_guard collection has {count} words, skipping seed")
                return
            
            # Collection is empty - seed from YAML
            logger.info(f"vocab_guard collection is empty, seeding from {self.yaml_seed_path}...")
            self._seed_from_yaml(self.yaml_seed_path)
            
        except Exception as e:
            logger.error(f"Failed to check/seed vocab_guard collection: {e}", exc_info=True)
    
    def _seed_from_yaml(self, yaml_path: Path):
        """Load words from YAML file into database (idempotent)."""
        if not yaml_path.exists():
            logger.warning(f"YAML seed file not found: {yaml_path}, skipping seed")
            return
        
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            collection = self.db.collection(VOCAB_GUARD_COLLECTION)
            now = datetime.now(timezone.utc).isoformat()
            seeded_count = 0
            
            for item in data.get("forbidden_words", []):
                if isinstance(item, dict):
                    word = item.get("word", "").strip().lower()
                    if not word:
                        continue
                    
                    alternative = item.get("alternative", "")
                    if isinstance(alternative, list):
                        alternative = " or ".join(str(a).strip() for a in alternative if a)
                    else:
                        alternative = str(alternative).strip() if alternative else ""
                    
                    # Sanitize document key (ArangoDB keys can only contain alphanumeric, underscore, hyphen)
                    # Replace spaces and special chars with underscores
                    import re
                    doc_key = re.sub(r'[^a-zA-Z0-9_-]', '_', word)
                    # Remove consecutive underscores
                    doc_key = re.sub(r'_+', '_', doc_key).strip('_')
                    # Ensure key is not empty
                    if not doc_key:
                        doc_key = f"word_{hash(word) % 1000000}"
                    
                    # Check if word already exists (idempotent)
                    try:
                        existing = collection.get(doc_key)
                        if existing and existing.get("word") == word:
                            logger.debug(f"Word '{word}' already exists, skipping")
                            continue
                    except ArangoError:
                        # Word doesn't exist, continue to insert
                        pass
                    
                    # Insert new word
                    doc = {
                        "_key": doc_key,  # Sanitized key
                        "word": word,  # Original word (preserved)
                        "alternative": alternative,
                        "version": 1,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                        "metadata": {
                            "source": "yaml_seed",
                            "seed_file": str(yaml_path)
                        }
                    }
                    collection.insert(doc)
                    seeded_count += 1
            
            logger.info(f"✅ Seeded {seeded_count} words from {yaml_path}")
            # Clear cache to force refresh
            self._cache = None
            
        except Exception as e:
            logger.error(f"Failed to seed from YAML: {e}", exc_info=True)
            # Don't raise - allow service to continue with empty collection
    
    def get_all_words(self, include_inactive: bool = False) -> Dict[str, str]:
        """
        Get all forbidden words with alternatives (cached).
        
        Args:
            include_inactive: Whether to include inactive words.
        
        Returns:
            Dictionary mapping word (lowercased) to alternative string.
        """
        if not self.db:
            logger.warning("ArangoDB not initialized, returning empty vocabulary")
            return {}
        
        # Check cache (5 minute TTL)
        now = datetime.now(timezone.utc)
        if self._cache is not None and self._cache_timestamp is not None:
            cache_age = (now - self._cache_timestamp).total_seconds()
            if cache_age < 300:  # 5 minutes
                if include_inactive:
                    # Return full cache (we'd need to cache inactive separately)
                    pass
                else:
                    # Filter out inactive words from cache
                    return {k: v for k, v in self._cache.items()}
        
        try:
            collection = self.db.collection(VOCAB_GUARD_COLLECTION)
            
            # Query active words
            query = f"""
            FOR word IN {VOCAB_GUARD_COLLECTION}
            FILTER word.is_active == true
            RETURN word
            """
            if include_inactive:
                query = f"""
                FOR word IN {VOCAB_GUARD_COLLECTION}
                RETURN word
                """
            
            cursor = self.db.aql.execute(query)
            words = {}
            for doc in cursor:
                words[doc["word"]] = doc.get("alternative", "")
            
            # Update cache
            self._cache = words
            self._cache_timestamp = now
            
            return words
            
        except ArangoError as e:
            logger.error(f"Failed to load forbidden words from database: {e}", exc_info=True)
            return {}
    
    def add_word(
        self, 
        word: str, 
        alternative: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ForbiddenWord:
        """
        Add or update a forbidden word.
        
        Args:
            word: The forbidden word (will be lowercased).
            alternative: Suggested alternative(s).
            metadata: Optional metadata dictionary.
        
        Returns:
            ForbiddenWord object.
        """
        if not self.db:
            raise RuntimeError("ArangoDB not initialized")
        
        word = word.strip().lower()
        if not word:
            raise ValueError("Word must be non-empty")
        
        collection = self.db.collection(VOCAB_GUARD_COLLECTION)
        now = datetime.now(timezone.utc).isoformat()
        
        # Check if word exists
        try:
            existing = collection.get(word)
            if existing and existing.get("word") == word:
                # Update existing word
                update_doc = {
                    "alternative": alternative or existing.get("alternative", ""),
                    "updated_at": now,
                    "is_active": True
                }
                if metadata:
                    existing_metadata = existing.get("metadata", {})
                    existing_metadata.update(metadata)
                    update_doc["metadata"] = existing_metadata
                
                collection.update({"_key": doc_key, **update_doc})
                logger.info(f"Updated forbidden word: {word}")
                # Clear cache
                self._cache = None
                
                # Return updated document
                updated = collection.get(doc_key)
                return ForbiddenWord(**updated)
            else:
                # Check if word exists with different key (by word field)
                cursor = self.db.aql.execute(
                    f"FOR w IN {VOCAB_GUARD_COLLECTION} FILTER w.word == @word RETURN w",
                    bind_vars={"word": word}
                )
                existing_by_word = list(cursor)
                if existing_by_word:
                    # Update existing word with different key
                    existing_doc = existing_by_word[0]
                    update_doc = {
                        "alternative": alternative or existing_doc.get("alternative", ""),
                        "updated_at": now,
                        "is_active": True
                    }
                    if metadata:
                        existing_metadata = existing_doc.get("metadata", {})
                        existing_metadata.update(metadata)
                        update_doc["metadata"] = existing_metadata
                    
                    collection.update({"_key": existing_doc["_key"], **update_doc})
                    logger.info(f"Updated forbidden word: {word}")
                    self._cache = None
                    updated = collection.get(existing_doc["_key"])
                    return ForbiddenWord(**updated)
                
                # Insert new word
                doc = {
                    "_key": doc_key,
                    "word": word,
                    "alternative": alternative or "",
                    "version": 1,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "metadata": metadata or {}
                }
                collection.insert(doc)
                logger.info(f"Added forbidden word: {word}")
                # Clear cache
                self._cache = None
                
                return ForbiddenWord(**doc)
                
        except ArangoError as e:
            logger.error(f"Failed to add/update word '{word}': {e}", exc_info=True)
            raise
    
    def remove_word(self, word: str, soft_delete: bool = True):
        """
        Remove a forbidden word.
        
        Args:
            word: The word to remove (will be lowercased).
            soft_delete: If True, mark as inactive. If False, delete permanently.
        """
        if not self.db:
            raise RuntimeError("ArangoDB not initialized")
        
        word = word.strip().lower()
        collection = self.db.collection(VOCAB_GUARD_COLLECTION)
        
        try:
            # Find document by word field (not key, since key may be sanitized)
            cursor = self.db.aql.execute(
                f"FOR w IN {VOCAB_GUARD_COLLECTION} FILTER w.word == @word RETURN w",
                bind_vars={"word": word}
            )
            existing = list(cursor)
            
            if not existing:
                raise ValueError(f"Word '{word}' not found")
            
            doc_key = existing[0]["_key"]
            
            if soft_delete:
                # Soft delete: mark as inactive
                collection.update({
                    "_key": doc_key,
                    "is_active": False,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                })
                logger.info(f"Deactivated forbidden word: {word}")
            else:
                # Hard delete: remove from database
                collection.delete(doc_key)
                logger.info(f"Deleted forbidden word: {word}")
            
            # Clear cache
            self._cache = None
            
        except ArangoError as e:
            logger.error(f"Failed to remove word '{word}': {e}", exc_info=True)
            raise
    
    def list_words(self, include_inactive: bool = False) -> List[ForbiddenWord]:
        """
        List all forbidden words.
        
        Args:
            include_inactive: Whether to include inactive words.
        
        Returns:
            List of ForbiddenWord objects.
        """
        if not self.db:
            logger.warning("ArangoDB not initialized, returning empty list")
            return []
        
        try:
            collection = self.db.collection(VOCAB_GUARD_COLLECTION)
            
            query = f"""
            FOR word IN {VOCAB_GUARD_COLLECTION}
            FILTER word.is_active == true
            SORT word.word ASC
            RETURN word
            """
            if include_inactive:
                query = f"""
                FOR word IN {VOCAB_GUARD_COLLECTION}
                SORT word.word ASC
                RETURN word
                """
            
            cursor = self.db.aql.execute(query)
            words = []
            for doc in cursor:
                words.append(ForbiddenWord(**doc))
            
            return words
            
        except ArangoError as e:
            logger.error(f"Failed to list words: {e}", exc_info=True)
            return []


# Global instance (lazy-loaded)
_service_instance: Optional[VocabGuardService] = None


def get_vocab_guard_service(
    arango_url: Optional[str] = None,
    arango_db: Optional[str] = None,
    arango_user: Optional[str] = None,
    arango_password: Optional[str] = None
) -> VocabGuardService:
    """
    Get or create the global VocabGuardService instance.
    
    Args:
        arango_url: Optional ArangoDB URL. Only used on first call.
        arango_db: Optional database name. Only used on first call.
        arango_user: Optional username. Only used on first call.
        arango_password: Optional password. Only used on first call.
    
    Returns:
        VocabGuardService instance.
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = VocabGuardService(
            arango_url=arango_url,
            arango_db=arango_db,
            arango_user=arango_user,
            arango_password=arango_password
        )
    return _service_instance

