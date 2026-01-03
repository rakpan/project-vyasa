"""
Project Service for Project Vyasa.

Handles persistence and retrieval of project configurations in ArangoDB.
The Graph (ArangoDB) is the system of record.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from .types import ProjectConfig, ProjectCreate, ProjectSummary
from .hub_types import ProjectHubSummary, ManifestSummary, ProjectGrouping
from ..shared.rigor_config import load_rigor_policy_yaml

logger = logging.getLogger(__name__)

# Default active research window: projects updated within last 30 days
ACTIVE_RESEARCH_DAYS = 30


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
            
            # Use rigor_level from payload, or default to "exploratory" if not provided
            rigor_level = config.rigor_level or "exploratory"
            # Validate rigor_level value
            if rigor_level not in ("exploratory", "conservative"):
                raise ValueError(f"Invalid rigor_level: {rigor_level}. Must be 'exploratory' or 'conservative'")

            # Prepare document for ArangoDB
            # Use _key = project_id (UUID)
            doc = {
                "_key": project_id,
                "title": config.title,
                "thesis": config.thesis,
                "research_questions": config.research_questions,
                "created_at": created_at,
                "seed_files": seed_files,
                "rigor_level": rigor_level,
            }
            
            # Add optional fields if present
            if config.anti_scope is not None:
                doc["anti_scope"] = config.anti_scope
            if config.target_journal is not None:
                doc["target_journal"] = config.target_journal
            
            # Initialize tags as empty list if not provided
            doc["tags"] = []
            
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
                rigor_level=rigor_level,
                created_at=created_at,  # Keep as ISO string
                tags=None,  # Tags initialized as empty list in DB
                last_updated=None,  # Will be derived from jobs
                archived=None,  # Will be derived from grouping logic
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
            rigor_level = doc.get("rigor_level", "exploratory")
            tags = doc.get("tags")
            if not isinstance(tags, list):
                tags = []
            
            # Map _key → id, keep created_at as stored value (ISO string)
            return ProjectConfig(
                id=doc["_key"],  # Map _key to id
                title=doc["title"],
                thesis=doc["thesis"],
                research_questions=doc.get("research_questions", []),
                anti_scope=doc.get("anti_scope"),
                target_journal=doc.get("target_journal"),
                seed_files=seed_files,
                rigor_level=rigor_level,
                created_at=doc["created_at"],  # Keep as ISO string
                tags=tags if tags else None,
                last_updated=doc.get("last_updated"),
                archived=doc.get("archived"),
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
    
    def _get_latest_job(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest job for a project (by created_at DESC).
        
        Args:
            project_id: Project identifier.
        
        Returns:
            Latest job record or None if no jobs exist.
        """
        try:
            from ..orchestrator.job_store import list_jobs_by_project
            jobs = list_jobs_by_project(project_id, limit=1)
            return jobs[0] if jobs else None
        except Exception as e:
            logger.warning(f"Failed to get latest job for project {project_id}: {e}", exc_info=True)
            return None
    
    def _get_last_updated(self, project_id: str, latest_job: Optional[Dict[str, Any]] = None) -> str:
        """Get last_updated timestamp for a project.
        
        Args:
            project_id: Project identifier.
            latest_job: Optional latest job record (to avoid re-querying).
        
        Returns:
            ISO timestamp string (defaults to created_at if no jobs).
        """
        try:
            collection = self.db.collection(self.COLLECTION_NAME)
            doc = collection.get(project_id)
            if doc and doc.get("last_updated"):
                return doc["last_updated"]
            
            # Fall back to latest job's created_at or project's created_at
            if latest_job and latest_job.get("created_at"):
                return latest_job["created_at"]
            
            if doc and doc.get("created_at"):
                return doc["created_at"]
            
            # Ultimate fallback: current time
            return datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.warning(f"Failed to get last_updated for project {project_id}: {e}", exc_info=True)
            return datetime.now(timezone.utc).isoformat()
    
    def _derive_project_status(
        self,
        project_id: str,
        latest_job: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Derive project status from latest job (server-side).
        
        Args:
            project_id: Project identifier.
            latest_job: Optional latest job record.
        
        Returns:
            "Idle" | "Processing" | "AttentionNeeded"
        """
        if latest_job is None:
            latest_job = self._get_latest_job(project_id)
        
        if latest_job is None:
            return "Idle"
        
        job_status = latest_job.get("status", "")
        
        # Processing: QUEUED, PENDING, RUNNING, PROCESSING
        if job_status in ("QUEUED", "PENDING", "RUNNING", "PROCESSING"):
            return "Processing"
        
        # AttentionNeeded: FAILED, NEEDS_SIGNOFF, or has conflicts
        if job_status in ("FAILED", "NEEDS_SIGNOFF"):
            return "AttentionNeeded"
        
        # Check for conflicts in succeeded jobs
        if job_status in ("SUCCEEDED", "COMPLETED"):
            job_id = latest_job.get("job_id")
            if job_id:
                try:
                    from ..orchestrator.job_store import get_job_record
                    job_record = get_job_record(job_id)
                    if job_record:
                        # Check for conflict_report_id
                        if job_record.get("conflict_report_id"):
                            return "AttentionNeeded"
                        # Check result for conflict flags
                        result = job_record.get("result", {})
                        if isinstance(result, dict):
                            conflict_flags = result.get("conflict_flags", [])
                            if conflict_flags and len(conflict_flags) > 0:
                                return "AttentionNeeded"
                except Exception as e:
                    logger.warning(f"Failed to check conflicts for job {job_id}: {e}", exc_info=True)
        
        # Default: Idle
        return "Idle"
    
    def _count_open_flags(
        self,
        project_id: str,
        latest_job: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Count open flags for a project.
        
        Args:
            project_id: Project identifier.
            latest_job: Optional latest job record.
        
        Returns:
            Count of open flags (failed jobs, conflicts, etc.).
        """
        if latest_job is None:
            latest_job = self._get_latest_job(project_id)
        
        if latest_job is None:
            return 0
        
        count = 0
        job_status = latest_job.get("status", "")
        job_id = latest_job.get("job_id")
        
        # Failed job counts as 1 flag
        if job_status == "FAILED":
            count += 1
        
        # NEEDS_SIGNOFF counts as 1 flag
        if job_status == "NEEDS_SIGNOFF":
            count += 1
        
        # Check for conflicts
        if job_id:
            try:
                from ..orchestrator.job_store import get_job_record
                job_record = get_job_record(job_id)
                if job_record:
                    # Conflict report counts as 1 flag
                    if job_record.get("conflict_report_id"):
                        count += 1
                    # Conflict flags in result
                    result = job_record.get("result", {})
                    if isinstance(result, dict):
                        conflict_flags = result.get("conflict_flags", [])
                        if isinstance(conflict_flags, list):
                            count += len(conflict_flags)
            except Exception as e:
                logger.warning(f"Failed to count flags for job {job_id}: {e}", exc_info=True)
        
        return count
    
    def _get_manifest_summary(
        self,
        project_id: str,
        latest_job: Optional[Dict[str, Any]] = None,
    ) -> Optional[ManifestSummary]:
        """Extract manifest summary from latest successful job.
        
        Args:
            project_id: Project identifier.
            latest_job: Optional latest job record.
        
        Returns:
            ManifestSummary or None if not available.
        """
        if latest_job is None:
            latest_job = self._get_latest_job(project_id)
        
        if latest_job is None:
            return None
        
        job_status = latest_job.get("status", "")
        # Only extract from succeeded/completed jobs
        if job_status not in ("SUCCEEDED", "COMPLETED"):
            return None
        
        job_id = latest_job.get("job_id")
        if not job_id:
            return None
        
        try:
            from ..orchestrator.job_store import get_job_record
            job_record = get_job_record(job_id)
            if not job_record:
                return None
            
            result = job_record.get("result", {})
            if not isinstance(result, dict):
                return None
            
            manifest = result.get("artifact_manifest")
            if not isinstance(manifest, dict):
                return None
            
            # Extract metrics
            metrics = manifest.get("metrics", {})
            totals = manifest.get("totals", {})
            
            # Calculate words, claims, density
            words = metrics.get("total_words") or totals.get("words") or 0
            claims = metrics.get("total_claims") or 0
            density = metrics.get("claims_per_100_words") or 0.0
            citations = metrics.get("citation_count") or totals.get("citations") or 0
            tables = totals.get("tables") or 0
            figures = totals.get("figures") or 0
            
            # Extract flags_count_by_type from blocks, tables, figures
            flags_count_by_type: Dict[str, int] = {}
            
            # Count flags from blocks
            blocks = manifest.get("blocks", [])
            if isinstance(blocks, list):
                for block in blocks:
                    if isinstance(block, dict):
                        # Count tone_flags
                        tone_flags = block.get("tone_flags", [])
                        if isinstance(tone_flags, list) and len(tone_flags) > 0:
                            flags_count_by_type["tone"] = flags_count_by_type.get("tone", 0) + len(tone_flags)
                        # Count other flags
                        flags = block.get("flags", [])
                        if isinstance(flags, list):
                            for flag in flags:
                                if isinstance(flag, str):
                                    # Parse flag type (e.g., "precision:max_decimals" -> "precision")
                                    parts = flag.split(":", 1)
                                    if len(parts) > 0:
                                        flag_type = parts[0]
                                        flags_count_by_type[flag_type] = flags_count_by_type.get(flag_type, 0) + 1
            
            # Count flags from tables
            tables_list = manifest.get("tables", [])
            if isinstance(tables_list, list):
                for table in tables_list:
                    if isinstance(table, dict):
                        flags = table.get("flags", [])
                        if isinstance(flags, list):
                            for flag in flags:
                                if isinstance(flag, str):
                                    parts = flag.split(":", 1)
                                    if len(parts) > 0:
                                        flag_type = parts[0]
                                        flags_count_by_type[flag_type] = flags_count_by_type.get(flag_type, 0) + 1
            
            # Count flags from figures
            figures_list = manifest.get("figures", [])
            if isinstance(figures_list, list):
                for figure in figures_list:
                    if isinstance(figure, dict):
                        flags = figure.get("flags", [])
                        if isinstance(flags, list):
                            for flag in flags:
                                if isinstance(flag, str):
                                    parts = flag.split(":", 1)
                                    if len(parts) > 0:
                                        flag_type = parts[0]
                                        flags_count_by_type[flag_type] = flags_count_by_type.get(flag_type, 0) + 1
            
            return ManifestSummary(
                words=words,
                claims=claims,
                density=density,
                citations=citations,
                tables=tables,
                figures=figures,
                flags_count_by_type=flags_count_by_type,
            )
        except Exception as e:
            logger.warning(f"Failed to extract manifest summary for project {project_id}: {e}", exc_info=True)
            return None
    
    def list_projects_hub(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        rigor: Optional[str] = None,
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        include_manifest: bool = False,
    ) -> ProjectGrouping:
        """List projects with hub view (grouping, filtering, summaries).
        
        Args:
            query: Search query (matches title and tags).
            tags: List of tags to filter by (all must match).
            rigor: Filter by rigor_level (exploratory or conservative).
            status: Filter by derived status (Idle, Processing, AttentionNeeded).
            from_date: Filter by last_updated >= from_date (ISO date).
            to_date: Filter by last_updated <= to_date (ISO date).
            include_manifest: If True, include manifest_summary in response.
        
        Returns:
            ProjectGrouping with active_research and archived_insights lists.
        
        Raises:
            RuntimeError: If database operation fails.
        """
        try:
            # Build AQL query with filters
            aql_filters = []
            bind_vars = {"@col": self.COLLECTION_NAME}
            
            # Query filter (title or tags)
            if query:
                aql_filters.append(
                    "(p.title LIKE CONCAT('%', @query, '%') OR "
                    "LENGTH(p.tags[* FILTER CURRENT LIKE CONCAT('%', @query, '%')]) > 0)"
                )
                bind_vars["query"] = query
            
            # Tags filter (all must match)
            if tags and len(tags) > 0:
                aql_filters.append(
                    "LENGTH(p.tags[* FILTER CURRENT IN @tags]) == @tags_count"
                )
                bind_vars["tags"] = tags
                bind_vars["tags_count"] = len(tags)
            
            # Rigor filter
            if rigor:
                aql_filters.append("p.rigor_level == @rigor")
                bind_vars["rigor"] = rigor
            
            # Build base query
            base_query = "FOR p IN @@col"
            if aql_filters:
                base_query += " FILTER " + " AND ".join(aql_filters)
            base_query += " RETURN p"
            
            # Execute query
            cursor = self.db.aql.execute(base_query, bind_vars=bind_vars)
            projects = list(cursor)
            
            # Process projects and derive status/manifest
            active_research: List[ProjectHubSummary] = []
            archived_insights: List[ProjectHubSummary] = []
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=ACTIVE_RESEARCH_DAYS)
            
            for doc in projects:
                project_id = doc.get("_key", "")
                if not project_id:
                    continue
                
                # Get latest job for status derivation
                latest_job = self._get_latest_job(project_id)
                
                # Derive status (server-side)
                derived_status = self._derive_project_status(project_id, latest_job)
                
                # Apply status filter if specified
                if status and derived_status != status:
                    continue
                
                # Get last_updated
                last_updated = self._get_last_updated(project_id, latest_job)
                
                # Apply date range filter
                if from_date or to_date:
                    try:
                        last_updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                        if from_date:
                            from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
                            if last_updated_dt < from_dt:
                                continue
                        if to_date:
                            to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
                            if last_updated_dt > to_dt:
                                continue
                    except Exception as e:
                        logger.warning(f"Failed to parse date for filtering: {e}", exc_info=True)
                
                # Get tags (default to empty array)
                tags_list = doc.get("tags")
                if not isinstance(tags_list, list):
                    tags_list = []
                
                # Get rigor_level (default to exploratory)
                rigor_level = doc.get("rigor_level", "exploratory")
                
                # Count open flags
                open_flags_count = self._count_open_flags(project_id, latest_job)
                
                # Get manifest summary if requested
                manifest_summary = None
                if include_manifest:
                    manifest_summary = self._get_manifest_summary(project_id, latest_job)
                
                # Build ProjectHubSummary (guaranteed fields)
                summary = ProjectHubSummary(
                    project_id=project_id,
                    title=doc.get("title", ""),
                    tags=tags_list,  # Always a list (default empty)
                    rigor_level=rigor_level,
                    last_updated=last_updated,
                    status=derived_status,  # Server-side derived
                    open_flags_count=open_flags_count,
                    manifest_summary=manifest_summary,  # Optional but stable shape if present
                )
                
                # Group into active_research or archived_insights
                # Logic: Active if:
                #   - status is Processing or AttentionNeeded, OR
                #   - last_updated within ACTIVE_RESEARCH_DAYS, OR
                #   - manually archived flag is False/None
                # Archived if:
                #   - manually archived flag is True, OR
                #   - status is Idle AND last_updated is older than ACTIVE_RESEARCH_DAYS
                archived_flag = doc.get("archived")
                try:
                    last_updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                    is_recent = last_updated_dt >= cutoff_date
                except Exception:
                    is_recent = False
                
                if archived_flag is True:
                    archived_insights.append(summary)
                elif derived_status in ("Processing", "AttentionNeeded") or is_recent:
                    active_research.append(summary)
                else:
                    # Idle and old -> archived
                    archived_insights.append(summary)
            
            # Sort active_research by last_updated DESC (most recent first)
            active_research.sort(key=lambda p: p.last_updated, reverse=True)
            # Sort archived_insights by last_updated DESC
            archived_insights.sort(key=lambda p: p.last_updated, reverse=True)
            
            return ProjectGrouping(
                active_research=active_research,
                archived_insights=archived_insights,
            )
            
        except ArangoError as e:
            logger.error(f"Failed to list projects for hub: {e}", exc_info=True)
            raise RuntimeError(f"Failed to list projects for hub: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error listing projects for hub: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error listing projects for hub: {e}") from e
