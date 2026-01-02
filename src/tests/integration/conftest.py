"""
Integration Test Setup - Real client connections and health checks.

This conftest.py provides fixtures for integration tests that require
real Docker services (ArangoDB, Cortex, Firecrawl).

Integration tests should be marked with @pytest.mark.integration.

**Safety & Hygiene:**
- All integration tests must be marked with @pytest.mark.integration
- Tests automatically skip if Docker stack is not fully operational
- Test data (projects, documents, claims) is automatically cleaned up after each test
"""

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Generator

import pytest
import requests
from arango import ArangoClient
from arango.database import StandardDatabase

from src.shared.config import (
    get_arango_url,
    get_arango_password,
    get_brain_url,
    get_worker_url,
    ARANGODB_DB,
    ARANGODB_USER,
)
from src.project.service import ProjectService
from src.project.types import ProjectCreate, ProjectConfig


def wait_for_service(url: str, timeout: int = 5, path: str = "/health") -> bool:
    """Poll a service health endpoint until it responds or timeout.
    
    Args:
        url: Base URL of the service (e.g., "http://localhost:8529")
        timeout: Maximum seconds to wait
        path: Health check endpoint path (default: "/health")
        
    Returns:
        True if service responds with 200, False otherwise
    """
    start_time = time.time()
    check_url = f"{url.rstrip('/')}{path}"
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(check_url, timeout=2)
            if response.status_code == 200:
                return True
        except (requests.exceptions.RequestException, requests.exceptions.Timeout):
            pass
        time.sleep(0.5)
    
    return False


@pytest.fixture(scope="session")
def integration_env() -> Dict[str, str]:
    """Load environment variables for integration tests with sensible defaults.
    
    Returns:
        Dictionary of environment variables for stack services
    """
    return {
        "ARANGO_URL": os.getenv("ARANGO_URL", "http://localhost:8529"),
        "CORTEX_BRAIN_URL": os.getenv("CORTEX_BRAIN_URL", "http://localhost:30000"),
        "CORTEX_WORKER_URL": os.getenv("CORTEX_WORKER_URL", "http://localhost:30001"),
        "FIRECRAWL_URL": os.getenv("FIRECRAWL_URL", "http://localhost:3002"),
        "ARANGO_DB": os.getenv("ARANGODB_DB", ARANGODB_DB),
        "ARANGO_USER": os.getenv("ARANGODB_USER", ARANGODB_USER),
        "ARANGO_PASSWORD": os.getenv("ARANGO_ROOT_PASSWORD") or os.getenv("ARANGODB_PASSWORD", ""),
    }


@pytest.fixture(scope="session")
def active_stack(integration_env: Dict[str, str]) -> Generator[Dict[str, bool], None, None]:
    """Health check fixture - verifies Docker stack is fully operational.
    
    Checks connectivity to:
    - ArangoDB at :8529 (required)
    - Cortex Brain at :30000 (required)
    - Firecrawl at :3002 (optional - may not be running)
    
    Skips all integration tests if ANY required service is unreachable.
    
    Yields:
        Dictionary mapping service names to availability status
    """
    services_available = {}
    required_services = []
    
    # Check ArangoDB (required)
    arango_url = integration_env["ARANGO_URL"]
    try:
        # ArangoDB uses /_api/version for health check
        if wait_for_service(arango_url, timeout=5, path="/_api/version"):
            services_available["arango"] = True
        else:
            services_available["arango"] = False
            required_services.append("ArangoDB")
    except Exception:
        services_available["arango"] = False
        required_services.append("ArangoDB")
    
    # Check Cortex Brain (required)
    brain_url = integration_env["CORTEX_BRAIN_URL"]
    try:
        if wait_for_service(brain_url, timeout=5, path="/health"):
            services_available["cortex_brain"] = True
        else:
            services_available["cortex_brain"] = False
            required_services.append("Cortex Brain")
    except Exception:
        services_available["cortex_brain"] = False
        required_services.append("Cortex Brain")
    
    # Check Firecrawl (optional - don't fail if not available)
    firecrawl_url = integration_env["FIRECRAWL_URL"]
    try:
        if wait_for_service(firecrawl_url, timeout=3, path="/health"):
            services_available["firecrawl"] = True
        else:
            services_available["firecrawl"] = False
    except Exception:
        services_available["firecrawl"] = False
    
    # Fail if any required service is unavailable
    if required_services:
        pytest.skip(
            f"Docker stack not fully operational - missing services: {', '.join(required_services)}"
        )
    
    yield services_available


@pytest.fixture
def real_arango_client(active_stack: Dict[str, bool], integration_env: Dict[str, str]) -> Generator[StandardDatabase, None, None]:
    """Real ArangoDB connection fixture.
    
    Connects to the real ArangoDB instance using configuration from integration_env.
    Skips if connection fails.
    
    Yields:
        ArangoDB StandardDatabase instance
    """
    try:
        url = integration_env["ARANGO_URL"]
        db_name = integration_env["ARANGO_DB"]
        username = integration_env["ARANGO_USER"]
        password = integration_env["ARANGO_PASSWORD"]
        
        if not password:
            pytest.skip("ArangoDB password not configured (set ARANGO_ROOT_PASSWORD or ARANGODB_PASSWORD)")
        
        client = ArangoClient(hosts=url)
        
        # Try to connect
        try:
            db = client.db(db_name, username=username, password=password)
            # Test connection with a simple query
            db.version()
            yield db
        except Exception as e:
            pytest.skip(f"ArangoDB not available: {e}")
    except ImportError:
        pytest.skip("python-arango not installed")
    except Exception as e:
        pytest.skip(f"ArangoDB connection failed: {e}")


def _cleanup_project_data(db: StandardDatabase, project_id: str) -> None:
    """Delete all data associated with a project.
    
    Removes:
    - Project document from 'projects' collection
    - Extractions from 'extractions' collection
    - Manuscript blocks from 'manuscript_blocks' collection
    - Candidate knowledge from 'candidate_knowledge' collection
    - External references from 'external_references' collection
    - Canonical knowledge entries linked to this project
    
    Args:
        db: ArangoDB database instance
        project_id: Project ID to clean up
    """
    try:
        # Delete from projects collection
        if db.has_collection("projects"):
            projects_coll = db.collection("projects")
            try:
                projects_coll.delete(project_id)
            except Exception:
                pass  # Project may not exist
        
        # Delete extractions
        if db.has_collection("extractions"):
            extractions_coll = db.collection("extractions")
            query = """
            FOR e IN extractions
            FILTER e.project_id == @project_id
            REMOVE e IN extractions
            """
            try:
                db.aql.execute(query, bind_vars={"project_id": project_id})
            except Exception:
                pass
        
        # Delete manuscript blocks
        if db.has_collection("manuscript_blocks"):
            blocks_coll = db.collection("manuscript_blocks")
            query = """
            FOR b IN manuscript_blocks
            FILTER b.project_id == @project_id
            REMOVE b IN manuscript_blocks
            """
            try:
                db.aql.execute(query, bind_vars={"project_id": project_id})
            except Exception:
                pass
        
        # Delete candidate knowledge
        if db.has_collection("candidate_knowledge"):
            candidates_coll = db.collection("candidate_knowledge")
            query = """
            FOR c IN candidate_knowledge
            FILTER c.project_id == @project_id
            REMOVE c IN candidate_knowledge
            """
            try:
                db.aql.execute(query, bind_vars={"project_id": project_id})
            except Exception:
                pass
        
        # Delete external references
        if db.has_collection("external_references"):
            refs_coll = db.collection("external_references")
            query = """
            FOR r IN external_references
            FILTER r.project_id == @project_id
            REMOVE r IN external_references
            """
            try:
                db.aql.execute(query, bind_vars={"project_id": project_id})
            except Exception:
                pass
        
        # Delete canonical knowledge entries (remove project from provenance_log)
        if db.has_collection("canonical_knowledge"):
            canon_coll = db.collection("canonical_knowledge")
            query = """
            FOR c IN canonical_knowledge
            FILTER LENGTH(c.provenance_log[* FILTER CURRENT.project_id == @project_id]) > 0
            UPDATE c WITH {
                provenance_log: c.provenance_log[* FILTER CURRENT.project_id != @project_id]
            } IN canonical_knowledge
            """
            try:
                db.aql.execute(query, bind_vars={"project_id": project_id})
            except Exception:
                pass
        
    except Exception as e:
        # Log but don't fail - cleanup is best effort
        print(f"Warning: Failed to cleanup project data for {project_id}: {e}")


@pytest.fixture(scope="function")
def test_project_context(real_arango_client: StandardDatabase) -> Generator[ProjectConfig, None, None]:
    """Create a test project with automatic cleanup.
    
    This fixture:
    1. Generates a unique project_id (test_int_{uuid})
    2. Creates the project in real ArangoDB
    3. Yields the project config
    4. **Teardown:** Deletes the project and all associated data
    
    Yields:
        ProjectConfig instance for the test project
    """
    # Generate unique project ID
    project_id = f"test_int_{uuid.uuid4().hex[:12]}"
    
    # Create project using ProjectService
    project_service = ProjectService(real_arango_client)
    
    project_create = ProjectCreate(
        title=f"Integration Test Project {project_id}",
        thesis="This is a test project for integration testing. It will be automatically deleted.",
        research_questions=["What is the purpose of this test?"],
        anti_scope=[],
        target_journal=None,
        seed_files=[],
    )
    
    try:
        project_config = project_service.create_project(project_create)
        # Override the generated ID with our test ID
        project_config.id = project_id
        
        # Update the document in DB with our test ID
        projects_coll = real_arango_client.collection("projects")
        try:
            # Delete the auto-generated project
            projects_coll.delete(project_config.id)
        except Exception:
            pass
        
        # Insert with our test ID
        doc = {
            "_key": project_id,
            "title": project_create.title,
            "thesis": project_create.thesis,
            "research_questions": project_create.research_questions,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seed_files": project_create.seed_files,
            "rigor_level": "exploratory",
        }
        projects_coll.insert(doc)
        
        # Create ProjectConfig with test ID
        test_project = ProjectConfig(
            id=project_id,
            title=project_create.title,
            thesis=project_create.thesis,
            research_questions=project_create.research_questions,
            anti_scope=project_create.anti_scope,
            target_journal=project_create.target_journal,
            seed_files=project_create.seed_files,
            rigor_level="exploratory",
            created_at=datetime.now(timezone.utc),
        )
        
        yield test_project
        
    finally:
        # Teardown: Clean up all project data
        _cleanup_project_data(real_arango_client, project_id)
