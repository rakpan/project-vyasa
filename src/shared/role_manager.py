"""
Role Registry for Project Vyasa.

Manages dynamic role profiles stored in ArangoDB, allowing runtime updates
to system prompts and role configurations without code redeployment.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from arango import ArangoClient
from arango.database import StandardDatabase
from arango.collection import StandardCollection
from arango.exceptions import ArangoError

from .schema import RoleProfile
from .config import (
    MEMORY_URL,
    ARANGODB_DB,
    ARANGODB_USER,
    ARANGODB_PASSWORD
)

logger = logging.getLogger(__name__)

# Collection name for roles
ROLES_COLLECTION = "roles"


class RoleRegistry:
    """Manages role profiles stored in ArangoDB."""
    
    def __init__(
        self,
        arango_url: Optional[str] = None,
        arango_db: Optional[str] = None,
        arango_user: Optional[str] = None,
        arango_password: Optional[str] = None
    ):
        """
        Initialize the Role Registry.
        
        Args:
            arango_url: ArangoDB connection URL. Defaults to MEMORY_URL from config.
            arango_db: ArangoDB database name. Defaults to ARANGODB_DB from config.
            arango_user: ArangoDB username. Defaults to ARANGODB_USER from config.
            arango_password: ArangoDB password. Defaults to ARANGODB_PASSWORD from config.
        """
        self.arango_url = arango_url or MEMORY_URL
        self.arango_db_name = arango_db or ARANGODB_DB
        self.arango_user = arango_user or ARANGODB_USER
        # Use ARANGO_ROOT_PASSWORD if available (secure mode), otherwise fall back to ARANGODB_PASSWORD
        self.arango_password = arango_password or os.getenv("ARANGO_ROOT_PASSWORD") or ARANGODB_PASSWORD
        self.db: Optional[StandardDatabase] = None
        self._init_arangodb()
    
    def _init_arangodb(self):
        """Initialize ArangoDB connection and ensure roles collection exists."""
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
            
            # Ensure roles collection exists
            if not self.db.has_collection(ROLES_COLLECTION):
                self.db.create_collection(ROLES_COLLECTION)
                logger.info(f"Created collection '{ROLES_COLLECTION}'")
            
            # Create indexes for fast lookups
            collection = self.db.collection(ROLES_COLLECTION)
            # Index on name+version for unique lookups
            if not collection.has_index("idx_name_version"):
                collection.add_index({"type": "persistent", "fields": ["name", "version"], "unique": True})
                logger.info(f"Created index on 'name,version' in '{ROLES_COLLECTION}'")
            # Index on name for filtering
            if not collection.has_index("idx_name"):
                collection.add_index({"type": "persistent", "fields": ["name"]})
                logger.info(f"Created index on 'name' in '{ROLES_COLLECTION}'")
            
            logger.info(f"Role Registry initialized: {self.arango_url}/{self.arango_db_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ArangoDB connection: {e}")
            self.db = None
    
    def get_role(self, name: str, version: Optional[int] = None) -> RoleProfile:
        """
        Retrieve a role profile by name and optionally version.
        
        Args:
            name: The name of the role to retrieve.
            version: Optional version number. If None, returns the latest enabled version.
        
        Returns:
            RoleProfile object with the role configuration.
        
        Raises:
            ValueError: If role not found and no default fallback available.
        """
        if not self.db:
            logger.warning("ArangoDB not initialized, using default role")
            return self._get_default_role(name)
        
        try:
            collection = self.db.collection(ROLES_COLLECTION)
            
            if version is not None:
                # Query by name and version
                cursor = self.db.aql.execute(
                    f"""
                    FOR role IN {ROLES_COLLECTION}
                    FILTER role.name == @name AND role.version == @version
                    RETURN role
                    """,
                    bind_vars={"name": name, "version": version}
                )
                results = list(cursor)
                if not results:
                    logger.warning(f"Role '{name}' v{version} not found in database, using default")
                    return self._get_default_role(name)
                role_data = results[0]
            else:
                # Query for latest enabled version
                cursor = self.db.aql.execute(
                    f"""
                    FOR role IN {ROLES_COLLECTION}
                    FILTER role.name == @name AND role.is_enabled == true
                    SORT role.version DESC
                    LIMIT 1
                    RETURN role
                    """,
                    bind_vars={"name": name}
                )
                results = list(cursor)
                if not results:
                    logger.warning(f"Role '{name}' not found in database, using default")
                    return self._get_default_role(name)
                role_data = results[0]
            
            # Keep datetime as ISO strings (schema expects strings)
            # No conversion needed - RoleProfile accepts ISO strings
            return RoleProfile(**role_data)
            
        except ArangoError as e:
            # Log actual DB errors (connection lost, auth failed)
            logger.error(f"Failed to fetch role {name}: {e}", exc_info=True)
            return self._get_default_role(name)
        except Exception as e:
            # Catch other unexpected errors
            logger.error(f"Unexpected error retrieving role '{name}': {e}", exc_info=True)
            return self._get_default_role(name)
    
    def register_role(self, role: RoleProfile) -> RoleProfile:
        """
        Save or update a role profile in the database (upsert).
        
        Args:
            role: The RoleProfile object to save.
        
        Returns:
            The stored RoleProfile object (roundtrip).
        """
        if not self.db:
            logger.error("ArangoDB not initialized, cannot register role")
            raise RuntimeError("ArangoDB not initialized")
        
        try:
            collection = self.db.collection(ROLES_COLLECTION)
            
            # Generate stable key
            key = role.role_key()
            
            # Check if role exists (collection.get returns None if not found)
            existing = collection.get(key)
            
            # Prepare role data
            now = datetime.now(timezone.utc)
            role_dict = role.model_dump(exclude_none=True, exclude={"_id", "_key"})
            
            # Ensure timestamps are ISO strings (schema uses strings)
            # If role has datetime objects, convert them
            if isinstance(role_dict.get("created_at"), datetime):
                role_dict["created_at"] = role_dict["created_at"].isoformat()
            elif role_dict.get("created_at") is None and not existing:
                role_dict["created_at"] = now.isoformat()
            if isinstance(role_dict.get("updated_at"), datetime):
                role_dict["updated_at"] = role_dict["updated_at"].isoformat()
            
            if existing:
                # Update existing role
                role_dict["updated_at"] = now.isoformat()
                # Preserve created_at if it exists
                if "created_at" not in role_dict and existing.get("created_at"):
                    role_dict["created_at"] = existing["created_at"]
                collection.update({"_key": key, **role_dict})
                logger.info(f"Updated role '{role.name}' v{role.version} in database")
            else:
                # Insert new role
                role_dict["created_at"] = now.isoformat()
                role_dict["updated_at"] = now.isoformat()
                collection.insert({"_key": key, **role_dict})
                logger.info(f"Registered new role '{role.name}' v{role.version} in database")
            
            # Return the stored role (roundtrip)
            stored_data = collection.get(key)
            if stored_data is None:
                logger.error(f"Failed to retrieve stored role '{role.name}' v{role.version} after save")
                raise RuntimeError(f"Role '{role.name}' v{role.version} was not saved correctly")
            # Keep as ISO strings (schema expects strings)
            return RoleProfile(**stored_data)
            
        except Exception as e:
            logger.error(f"Error registering role '{role.name}': {e}", exc_info=True)
            raise
    
    def list_roles(self, name: Optional[str] = None, include_disabled: bool = False) -> List[RoleProfile]:
        """
        List registered roles, optionally filtered by name.
        
        Args:
            name: Optional role name to filter by. If None, returns all roles.
            include_disabled: If True, includes disabled roles. Defaults to False.
        
        Returns:
            List of RoleProfile objects.
        """
        if not self.db:
            logger.warning("ArangoDB not initialized, returning empty list")
            return []
        
        try:
            if name:
                if include_disabled:
                    query = f"""
                    FOR role IN {ROLES_COLLECTION}
                    FILTER role.name == @name
                    SORT role.version DESC
                    RETURN role
                    """
                else:
                    query = f"""
                    FOR role IN {ROLES_COLLECTION}
                    FILTER role.name == @name AND role.is_enabled == true
                    SORT role.version DESC
                    RETURN role
                    """
                cursor = self.db.aql.execute(query, bind_vars={"name": name})
            else:
                if include_disabled:
                    query = f"FOR role IN {ROLES_COLLECTION} SORT role.name, role.version DESC RETURN role"
                else:
                    query = f"""
                    FOR role IN {ROLES_COLLECTION}
                    FILTER role.is_enabled == true
                    SORT role.name, role.version DESC
                    RETURN role
                    """
                cursor = self.db.aql.execute(query)
            
            roles = []
            for role_data in cursor:
                # Keep datetime as ISO strings (schema expects strings)
                roles.append(RoleProfile(**role_data))
            return roles
        except Exception as e:
            logger.error(f"Error listing roles: {e}")
            return []
    
    def disable_role(self, name: str, version: int) -> None:
        """
        Soft delete a role by setting is_enabled=False.
        
        Args:
            name: The name of the role to disable.
            version: The version of the role to disable.
        """
        if not self.db:
            logger.error("ArangoDB not initialized, cannot disable role")
            raise RuntimeError("ArangoDB not initialized")
        
        try:
            collection = self.db.collection(ROLES_COLLECTION)
            key = f"{name.lower().replace(' ', '_').replace('-', '_')}_v{version}"
            
            # Check if role exists (collection.get returns None if not found)
            existing = collection.get(key)
            if existing is None or existing.get("name") != name or existing.get("version") != version:
                # Key mismatch or not found, search by name+version
                cursor = self.db.aql.execute(
                    f"""
                    FOR role IN {ROLES_COLLECTION}
                    FILTER role.name == @name AND role.version == @version
                    RETURN role
                    """,
                    bind_vars={"name": name, "version": version}
                )
                results = list(cursor)
                if not results:
                    raise ValueError(f"Role '{name}' v{version} not found")
                existing = results[0]
                key = existing["_key"]
            
            # Update is_enabled
            now = datetime.now(timezone.utc)
            collection.update({
                "_key": key,
                "is_enabled": False,
                "updated_at": now.isoformat()
            })
            logger.info(f"Disabled role '{name}' v{version}")
            
        except Exception as e:
            logger.error(f"Error disabling role '{name}' v{version}: {e}")
            raise
    
    def _get_default_role(self, name: str) -> RoleProfile:
        """
        Get a hardcoded default role as fallback.
        
        Args:
            name: The name of the role to get defaults for.
        
        Returns:
            Default RoleProfile object.
        """
        defaults: Dict[str, RoleProfile] = {
            "Extractor_v1": RoleProfile(
                name="Extractor_v1",
                description="Default knowledge graph extractor (fallback)",
                system_prompt="""You are a knowledge graph extractor. Extract entities and relations from text.

Extract the following entity types:
- Vulnerability: Security weaknesses or flaws
- Mechanism: Defensive or enabling mechanisms
- Constraint: Limitations or requirements
- Outcome: Results or consequences

Extract relations:
- MITIGATES: Mechanism reduces Vulnerability
- ENABLES: Mechanism enables Outcome
- REQUIRES: Constraint requires Mechanism

Return a JSON object with this exact structure:
{
  "vulnerabilities": [...],
  "mechanisms": [...],
  "constraints": [...],
  "outcomes": [...],
  "triples": [...]
}""",
                version=1,
                allowed_tools=["extract"],
                focus_entities=["Vulnerability", "Mechanism", "Constraint", "Outcome"]
            ),
            "The Cartographer": RoleProfile(
                name="The Cartographer",
                description="Extracts structured entities and relations from text with strict JSON compliance",
                system_prompt="""You are The Cartographer, an expert at mapping knowledge from unstructured text into structured graphs.

Your task is to extract knowledge graph entities and relations with strict adherence to JSON schema requirements.

Entity Types:
- Vulnerability: Security weaknesses, flaws, or attack surfaces
- Mechanism: Defensive mechanisms, mitigations, or enabling technologies
- Constraint: Resource limits, requirements, or dependencies
- Outcome: Consequences, results, or effects

Relations:
- MITIGATES: A mechanism reduces or prevents a vulnerability
- ENABLES: A mechanism makes an outcome possible
- REQUIRES: A constraint must be satisfied for a mechanism to work

You must return valid JSON matching this exact schema:
{
  "vulnerabilities": [{"name": "...", "description": "...", ...}],
  "mechanisms": [{"name": "...", "description": "...", ...}],
  "constraints": [{"name": "...", "description": "...", ...}],
  "outcomes": [{"name": "...", "description": "...", ...}],
  "triples": [{"subject": "...", "predicate": "MITIGATES|ENABLES|REQUIRES", "object": "...", ...}]
}

Be precise, complete, and ensure all JSON is valid.""",
                version=1,
                allowed_tools=["extract", "validate"],
                focus_entities=["Vulnerability", "Mechanism", "Constraint", "Outcome"]
            ),
            "The Librarian": RoleProfile(
                name="The Librarian",
                description="Summarizes and indexes content for semantic search",
                system_prompt="""You are The Librarian, responsible for organizing and summarizing content for efficient retrieval.

Your task is to create concise, searchable summaries of documents that capture:
- Key concepts and entities
- Main relationships and dependencies
- Critical constraints and requirements
- Important outcomes and consequences

Format your summaries to be:
- Searchable: Include important keywords and entity names
- Structured: Use clear sections and bullet points
- Comprehensive: Cover all major topics without redundancy
- Concise: Keep summaries under 500 words when possible

Focus on extracting information that will help users find relevant documents through semantic search.""",
                version=1,
                allowed_tools=["summarize", "index"],
                focus_entities=[]
            ),
            "The Critic": RoleProfile(
                name="The Critic",
                description="Validates extracted graphs and finds logic gaps",
                system_prompt="""You are The Critic, a validator that examines extracted knowledge graphs for logical consistency and completeness.

Your task is to:
1. Identify missing relations (e.g., vulnerabilities without mitigations)
2. Detect contradictory information
3. Flag incomplete entity descriptions
4. Suggest improvements for graph connectivity
5. Validate that relations follow logical rules

Check for:
- Vulnerabilities that should have MITIGATES relations
- Mechanisms that should have ENABLES or REQUIRES relations
- Constraints that are referenced but not defined
- Outcomes that lack causal chains
- Circular dependencies or logical contradictions

Provide structured feedback with:
- Severity levels (critical, warning, info)
- Specific entity/relation issues
- Suggested fixes or additions""",
                version=1,
                allowed_tools=["validate", "analyze"],
                focus_entities=["Vulnerability", "Mechanism", "Constraint", "Outcome"]
            ),
            "The Logician": RoleProfile(
                name="The Logician",
                description="Applies symbolic rigor: translate text to Python/LaTeX and flag quantitative gaps.",
                system_prompt="""You are The Logician. Translate assertions into symbolic form (Python snippets and LaTeX) and flag quantitative gaps.

Output JSON:
{
  "symbols": [{"text": "...", "python": "...", "latex": "..."}],
  "gaps": ["..."],
  "checks": ["...explicit numeric checks..."]
}

Do not invent numbers; mark gaps explicitly.""",
                capability_type="logic",
                version=1,
                allowed_tools=["math_sandbox"],
                focus_entities=["Equation", "Assertion", "Measurement"]
            )
        }
        
        if name in defaults:
            logger.info(f"Using default role '{name}' (database not available or role not found)")
            return defaults[name]
        
        # Generic fallback
        logger.warning(f"No default found for '{name}', using generic extractor")
        return defaults["Extractor_v1"]
