"""
Unit tests for ProjectService (src/project/service.py).

Tests project creation, retrieval, listing, and seed file management.
All database operations are mocked to avoid requiring a running ArangoDB instance.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
import pytest
from arango.exceptions import ArangoError

from src.project.service import ProjectService
from src.project.types import ProjectCreate, ProjectConfig, ProjectSummary


@pytest.fixture
def mock_db():
    """Mock ArangoDB StandardDatabase instance."""
    db = Mock()
    db.has_collection = Mock(return_value=False)
    db.create_collection = Mock(return_value=Mock())
    db.collection = Mock(return_value=Mock())
    db.aql = Mock()
    return db


@pytest.fixture
def project_service(mock_db):
    """Create a ProjectService instance with mocked database."""
    with patch.object(ProjectService, 'ensure_schema'):
        service = ProjectService(mock_db)
        return service


def test_create_project_generates_uuid_and_timestamp(project_service, mock_db):
    """Verify create_project generates a UUID and calls db.insert_document with correct timestamp."""
    # Setup
    mock_collection = Mock()
    mock_db.collection.return_value = mock_collection
    mock_collection.insert.return_value = {"_key": "test-key", "_id": "projects/test-key", "_rev": "1"}
    
    config = ProjectCreate(
        title="Test Project",
        thesis="Test thesis statement",
        research_questions=["RQ1: What is the question?"],
    )
    
    # Execute
    result = project_service.create_project(config)
    
    # Verify
    assert isinstance(result, ProjectConfig)
    assert result.id is not None
    assert len(result.id) == 36  # UUID format
    assert result.title == "Test Project"
    assert result.thesis == "Test thesis statement"
    assert result.research_questions == ["RQ1: What is the question?"]
    assert result.seed_files == []
    assert result.created_at is not None
    
    # Verify insert was called with correct structure
    mock_collection.insert.assert_called_once()
    call_args = mock_collection.insert.call_args[0][0]
    assert call_args["_key"] == result.id
    assert call_args["title"] == "Test Project"
    assert call_args["thesis"] == "Test thesis statement"
    assert "created_at" in call_args
    assert isinstance(call_args["created_at"], str)  # ISO format string


def test_create_project_validates_empty_title(project_service):
    """Verify create_project raises ValueError for empty title."""
    config = ProjectCreate(
        title="",
        thesis="Test thesis",
        research_questions=["RQ1"],
    )
    
    with pytest.raises(ValueError, match="title cannot be empty"):
        project_service.create_project(config)


def test_create_project_validates_empty_thesis(project_service):
    """Verify create_project raises ValueError for empty thesis."""
    config = ProjectCreate(
        title="Test",
        thesis="",
        research_questions=["RQ1"],
    )
    
    with pytest.raises(ValueError, match="thesis cannot be empty"):
        project_service.create_project(config)


def test_create_project_validates_no_rqs(project_service):
    """Verify create_project raises ValueError when no research questions provided."""
    config = ProjectCreate(
        title="Test",
        thesis="Test thesis",
        research_questions=[],
    )
    
    with pytest.raises(ValueError, match="at least one research question"):
        project_service.create_project(config)


def test_create_project_handles_optional_fields(project_service, mock_db):
    """Verify create_project handles optional fields (anti_scope, target_journal)."""
    mock_collection = Mock()
    mock_db.collection.return_value = mock_collection
    mock_collection.insert.return_value = {"_key": "test-key", "_id": "projects/test-key", "_rev": "1"}
    
    config = ProjectCreate(
        title="Test Project",
        thesis="Test thesis",
        research_questions=["RQ1"],
        anti_scope=["Mobile apps"],
        target_journal="IEEE Security",
    )
    
    result = project_service.create_project(config)
    
    assert result.anti_scope == ["Mobile apps"]
    assert result.target_journal == "IEEE Security"
    
    # Verify optional fields in insert call
    call_args = mock_collection.insert.call_args[0][0]
    assert call_args["anti_scope"] == ["Mobile apps"]
    assert call_args["target_journal"] == "IEEE Security"


def test_get_project_returns_project_config(project_service, mock_db):
    """Verify get_project returns a ProjectConfig Pydantic model."""
    project_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    
    mock_collection = Mock()
    mock_db.collection.return_value = mock_collection
    mock_collection.get.return_value = {
        "_key": project_id,
        "title": "Test Project",
        "thesis": "Test thesis",
        "research_questions": ["RQ1"],
        "seed_files": ["file1.pdf"],
        "created_at": created_at,
    }
    
    result = project_service.get_project(project_id)
    
    assert isinstance(result, ProjectConfig)
    assert result.id == project_id
    assert result.title == "Test Project"
    assert result.thesis == "Test thesis"
    assert result.research_questions == ["RQ1"]
    assert result.seed_files == ["file1.pdf"]
    assert result.created_at == created_at
    
    # Verify get was called with correct key
    mock_collection.get.assert_called_once_with(project_id)


def test_get_project_raises_value_error_when_not_found(project_service, mock_db):
    """Verify get_project raises ValueError when project not found."""
    project_id = str(uuid.uuid4())
    
    mock_collection = Mock()
    mock_db.collection.return_value = mock_collection
    mock_collection.get.return_value = None
    
    with pytest.raises(ValueError, match=f"Project not found: {project_id}"):
        project_service.get_project(project_id)


def test_get_project_defaults_seed_files_to_empty_list(project_service, mock_db):
    """Verify get_project defaults seed_files to empty list if missing."""
    project_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    
    mock_collection = Mock()
    mock_db.collection.return_value = mock_collection
    mock_collection.get.return_value = {
        "_key": project_id,
        "title": "Test Project",
        "thesis": "Test thesis",
        "research_questions": ["RQ1"],
        "created_at": created_at,
        # seed_files missing
    }
    
    result = project_service.get_project(project_id)
    
    assert result.seed_files == []


def test_add_seed_file_executes_correct_aql_query(project_service, mock_db):
    """Verify add_seed_file executes the correct AQL PUSH query."""
    project_id = str(uuid.uuid4())
    filename = "test.pdf"
    
    mock_cursor = Mock()
    mock_cursor.__iter__ = Mock(return_value=iter([{"_key": project_id}]))
    mock_db.aql.execute.return_value = mock_cursor
    
    # Execute
    project_service.add_seed_file(project_id, filename)
    
    # Verify AQL query was called with correct bind vars
    mock_db.aql.execute.assert_called_once()
    call_args = mock_db.aql.execute.call_args
    
    # Check query contains PUSH operation
    query = call_args[0][0]
    assert "PUSH" in query
    assert "@col" in query
    assert "@key" in query
    assert "@filename" in query
    
    # Check bind vars
    bind_vars = call_args[1]["bind_vars"]
    assert bind_vars["@col"] == "projects"
    assert bind_vars["key"] == project_id
    assert bind_vars["filename"] == filename


def test_add_seed_file_raises_value_error_when_project_not_found(project_service, mock_db):
    """Verify add_seed_file raises ValueError when project not found."""
    project_id = str(uuid.uuid4())
    filename = "test.pdf"
    
    mock_cursor = Mock()
    mock_cursor.__iter__ = Mock(return_value=iter([]))  # Empty result
    mock_db.aql.execute.return_value = mock_cursor
    
    with pytest.raises(ValueError, match=f"Project not found: {project_id}"):
        project_service.add_seed_file(project_id, filename)


def test_add_seed_file_raises_value_error_for_empty_filename(project_service):
    """Verify add_seed_file raises ValueError for empty filename."""
    project_id = str(uuid.uuid4())
    
    with pytest.raises(ValueError, match="Filename cannot be empty"):
        project_service.add_seed_file(project_id, "")


def test_list_projects_returns_summaries(project_service, mock_db):
    """Verify list_projects returns List[ProjectSummary] sorted by created_at DESC."""
    project_id1 = str(uuid.uuid4())
    project_id2 = str(uuid.uuid4())
    created_at1 = "2024-01-01T00:00:00Z"
    created_at2 = "2024-01-02T00:00:00Z"
    
    mock_cursor = Mock()
    mock_cursor.__iter__ = Mock(return_value=iter([
        {"id": project_id2, "title": "Project 2", "created_at": created_at2},
        {"id": project_id1, "title": "Project 1", "created_at": created_at1},
    ]))
    mock_db.aql.execute.return_value = mock_cursor
    
    result = project_service.list_projects()
    
    assert len(result) == 2
    assert all(isinstance(s, ProjectSummary) for s in result)
    assert result[0].id == project_id2  # Newest first
    assert result[0].title == "Project 2"
    assert result[1].id == project_id1
    assert result[1].title == "Project 1"
    
    # Verify AQL query was called
    mock_db.aql.execute.assert_called_once()
    query = mock_db.aql.execute.call_args[0][0]
    assert "SORT p.created_at DESC" in query


def test_create_project_handles_arango_error(project_service, mock_db):
    """Verify create_project raises RuntimeError when ArangoDB operation fails."""
    mock_collection = Mock()
    mock_db.collection.return_value = mock_collection
    mock_collection.insert.side_effect = ArangoError("Connection failed")
    
    config = ProjectCreate(
        title="Test Project",
        thesis="Test thesis",
        research_questions=["RQ1"],
    )
    
    with pytest.raises(RuntimeError, match="Failed to create project"):
        project_service.create_project(config)


def test_get_project_handles_arango_error(project_service, mock_db):
    """Verify get_project raises RuntimeError when ArangoDB operation fails."""
    project_id = str(uuid.uuid4())
    
    mock_collection = Mock()
    mock_db.collection.return_value = mock_collection
    mock_collection.get.side_effect = ArangoError("Connection failed")
    
    with pytest.raises(RuntimeError, match="Failed to fetch project"):
        project_service.get_project(project_id)

