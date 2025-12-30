"""
Project Service for Project Vyasa.

Handles persistence and retrieval of project configurations in ArangoDB.
The Graph (ArangoDB) is the system of record.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from .types import ProjectConfig, ProjectCreate, ProjectSummary

logger = logging.getLogger(__name__)


class ProjectService:
    """Service for managing project configurations in ArangoDB."""
    
    COLLECTION_NAME = "projects"
    
    def __init__(self, db: StandardDatabase) -> None:
        """
        Initialize the Project Service.
        
        Args:
            db: ArangoDB StandardDatabase instance (must be connected).
        
        Raises:
            ValueError: If db is None or not connected.
        """
        if db is None:
            raise ValueError("Database instance is required")
        self.db = db
        self.ensure_schema()
    
    def ensure_schema(self) -> None:
        """Ensure the collection exists and has required indexes.
        
        Creates the collection if missing and ensures a persistent index
        on created_at for UI sorting.
        
        Raises:
            RuntimeError: If schema setup fails.
        """
        try:
            # Create collection if missing
            if not self.db.has_collection(self.COLLECTION_NAME):
                self.db.create_collection(self.COLLECTION_NAME)
                logger.info(f"Created collection '{self.COLLECTION_NAME}'")
            
            # Ensure persistent index on created_at for sorting
            collection = self.db.collection(self.COLLECTION_NAME)
            collection.ensure_persistent_index(["created_at"])
            logger.debug(f"Ensured index on 'created_at' in '{self.COLLECTION_NAME}'")
            
        except ArangoError as e:
            logger.error(f"Failed to ensure schema for '{self.COLLECTION_NAME}': {e}", exc_info=True)
            raise RuntimeError(f"Schema setup failed: {e}") from e
    
    def create_project(self, config: ProjectCreate) -> ProjectConfig:
        """Create a new project in the database.
        
        Args:
            config: ProjectCreate payload with project details.
        
        Returns:
            ProjectConfig with generated ID and created_at timestamp.
        
        Raises:
            ValueError: If input validation fails (empty title, thesis, or no RQs).
            RuntimeError: If database operation fails.
        """
        # Fail fast on invalid inputs
        if not config.title or not config.title.strip():
            raise ValueError("Project title cannot be empty")
        if not config.thesis or not config.thesis.strip():
            raise ValueError("Project thesis cannot be empty")
        if not config.research_questions:
            raise ValueError("Project must have at least one research question")
        
        try:
            # Generate UUID and UTC timestamp
            project_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat()
            seed_files = config.seed_files or []
            
            # Prepare document for ArangoDB
            # Use _key = project_id (UUID)
            doc = {
                "_key": project_id,
                "title": config.title,
                "thesis": config.thesis,
                "research_questions": config.research_questions,
                "created_at": created_at,
                "seed_files": seed_files,
            }
            
            # Add optional fields if present
            if config.anti_scope is not None:
                doc["anti_scope"] = config.anti_scope
            if config.target_journal is not None:
                doc["target_journal"] = config.target_journal
            
            # Insert into collection
            collection = self.db.collection(self.COLLECTION_NAME)
            collection.insert(doc)
            
            logger.info(f"Created project '{config.title}' with ID {project_id}")
            
            # Return ProjectConfig mapping _key → id
            return ProjectConfig(
                id=project_id,  # Map _key to id
                title=config.title,
                thesis=config.thesis,
                research_questions=config.research_questions,
                anti_scope=config.anti_scope,
                target_journal=config.target_journal,
                seed_files=seed_files,
                created_at=created_at,  # Keep as ISO string
            )
            
        except ArangoError as e:
            logger.error(f"Failed to create project: {e}", exc_info=True)
            raise RuntimeError(f"Failed to create project: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error creating project: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error creating project: {e}") from e
    
    def get_project(self, project_id: str) -> ProjectConfig:
        """Retrieve a project by ID.
        
        Args:
            project_id: The UUID of the project (used as _key).
        
        Returns:
            ProjectConfig with mapped fields.
        
        Raises:
            ValueError: If project not found.
            RuntimeError: If database operation fails.
        """
        try:
            collection = self.db.collection(self.COLLECTION_NAME)
            
            # Fetch by _key (project_id is the _key)
            doc = collection.get(project_id)
            
            if doc is None:
                raise ValueError(f"Project not found: {project_id}")
            
            # Ensure seed_files is always a list (default empty if missing)
            seed_files = doc.get("seed_files")
            if not isinstance(seed_files, list):
                seed_files = []
            
            # Map _key → id, keep created_at as stored value (ISO string)
            return ProjectConfig(
                id=doc["_key"],  # Map _key to id
                title=doc["title"],
                thesis=doc["thesis"],
                research_questions=doc.get("research_questions", []),
                anti_scope=doc.get("anti_scope"),
                target_journal=doc.get("target_journal"),
                seed_files=seed_files,
                created_at=doc["created_at"],  # Keep as ISO string
            )
            
        except ValueError:
            raise
        except ArangoError as e:
            logger.error(f"Failed to fetch project {project_id}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to fetch project: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching project {project_id}: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error fetching project: {e}") from e
    
    def list_projects(self) -> List[ProjectSummary]:
        """List all projects as summaries, sorted by created_at (newest first).
        
        Returns:
            List of ProjectSummary objects.
        
        Raises:
            RuntimeError: If database operation fails.
        """
        try:
            # AQL query with safe bind vars
            query = """
            FOR p IN @@col
            SORT p.created_at DESC
            RETURN { id: p._key, title: p.title, created_at: p.created_at }
            """
            
            cursor = self.db.aql.execute(
                query,
                bind_vars={"@col": self.COLLECTION_NAME}
            )
            
            summaries = []
            for doc in cursor:
                summaries.append(ProjectSummary(**doc))
            
            logger.info(f"Listed {len(summaries)} projects")
            return summaries
            
        except ArangoError as e:
            logger.error(f"Failed to list projects: {e}", exc_info=True)
            raise RuntimeError(f"Failed to list projects: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error listing projects: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error listing projects: {e}") from e
    
    def add_seed_file(self, project_id: str, filename: str) -> None:
        """Atomically append filename to seed_files with uniqueness guarantee.
        
        Args:
            project_id: The UUID of the project (used as _key).
            filename: The filename to add to seed_files.
        
        Raises:
            ValueError: If project not found or filename is empty.
            RuntimeError: If database operation fails.
        """
        if not filename or not filename.strip():
            raise ValueError("Filename cannot be empty")
        
        try:
            # Atomic AQL PUSH operation with correct scoping
            # Use OLD correctly and filter by _key
            query = """
            FOR p IN @@col
            FILTER p._key == @key
            UPDATE p WITH {
              seed_files: PUSH(p.seed_files ? p.seed_files : [], @filename, true)
            } IN @@col
            RETURN NEW
            """
            
            cursor = self.db.aql.execute(
                query,
                bind_vars={
                    "@col": self.COLLECTION_NAME,
                    "key": project_id,
                    "filename": filename
                }
            )
            
            results = list(cursor)
            
            if not results:
                raise ValueError(f"Project not found: {project_id}")
            
            logger.info(f"Added seed file '{filename}' to project {project_id}")
            
        except ValueError:
            raise
        except ArangoError as e:
            logger.error(f"Failed to add seed file to project {project_id}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to add seed file: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error adding seed file: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error adding seed file: {e}") from e
