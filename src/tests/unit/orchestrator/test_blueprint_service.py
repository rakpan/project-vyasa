"""
Unit tests for Blueprint Service.

Tests:
- Save/get blueprint
- Version management (auto-increment)
- Blueprint validation (sections minimal fields)
- Section uniqueness within blueprint
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from src.orchestrator.schemas.blueprint import (
    ManuscriptBlueprint,
    BlueprintSection,
    JournalSlot,
    DepthIntent,
)
from src.orchestrator.services.blueprint_service import BlueprintService


@pytest.fixture
def mock_db():
    """Mock ArangoDB database."""
    db = Mock()
    db.has_collection = Mock(return_value=False)
    db.create_collection = Mock()
    db.collection = Mock(return_value=Mock())
    return db


@pytest.fixture
def blueprint_service(mock_db):
    """Blueprint Service with mocked DB."""
    return BlueprintService(mock_db)


@pytest.fixture
def sample_blueprint():
    """Sample Manuscript Blueprint for testing."""
    section = BlueprintSection(
        section_id="section-1",
        heading="Introduction",
        journal_slot=JournalSlot.INTRODUCTION,
        linked_rqs=["RQ1", "RQ2"],
        depth_intent=DepthIntent.PROOF,
    )
    
    return ManuscriptBlueprint.create(
        project_id="test-project-123",
        sections=[section],
        target_journal="IEEE Security & Privacy",
    )


def test_save_blueprint(blueprint_service, sample_blueprint, mock_db):
    """Test saving a Manuscript Blueprint."""
    coll = Mock()
    coll.insert = Mock(return_value={"_id": "blueprints/test-123", "_key": "test-123"})
    mock_db.collection.return_value = coll
    mock_db.has_collection.return_value = True
    
    # Mock get_latest_version to return 0 (no existing blueprint)
    with patch.object(blueprint_service, "_get_latest_version", return_value=0):
        blueprint = blueprint_service.save_blueprint(sample_blueprint)
        
        assert blueprint.version == 1
        assert blueprint.blueprint_id == sample_blueprint.blueprint_id
        assert len(blueprint.sections) == 1
        assert coll.insert.called_once


def test_save_blueprint_version_increment(blueprint_service, sample_blueprint, mock_db):
    """Test blueprint version auto-increment."""
    coll = Mock()
    coll.insert = Mock(return_value={"_id": "blueprints/test-123", "_key": "test-123"})
    mock_db.collection.return_value = coll
    mock_db.has_collection.return_value = True
    
    # Mock get_latest_version to return 3 (existing blueprint version 3)
    with patch.object(blueprint_service, "_get_latest_version", return_value=3):
        blueprint = blueprint_service.save_blueprint(sample_blueprint)
        
        assert blueprint.version == 4  # Incremented from 3
        assert coll.insert.called_once


def test_save_blueprint_empty_sections(blueprint_service, sample_blueprint, mock_db):
    """Test saving blueprint with empty sections (should fail validation)."""
    sample_blueprint.sections = []
    
    with pytest.raises(ValueError, match="Section heading must be non-empty"):
        blueprint_service.save_blueprint(sample_blueprint)


def test_save_blueprint_invalid_journal_slot(blueprint_service, sample_blueprint, mock_db):
    """Test saving blueprint with invalid journal_slot."""
    sample_blueprint.sections[0].journal_slot = "invalid_slot"  # type: ignore
    
    with pytest.raises(ValueError, match="Invalid journal_slot"):
        blueprint_service.save_blueprint(sample_blueprint)


def test_save_blueprint_invalid_depth_intent(blueprint_service, sample_blueprint, mock_db):
    """Test saving blueprint with invalid depth_intent."""
    sample_blueprint.sections[0].depth_intent = "invalid_intent"  # type: ignore
    
    with pytest.raises(ValueError, match="Invalid depth_intent"):
        blueprint_service.save_blueprint(sample_blueprint)


def test_save_blueprint_duplicate_section_ids(blueprint_service, sample_blueprint, mock_db):
    """Test saving blueprint with duplicate section_ids."""
    duplicate_section = BlueprintSection(
        section_id=sample_blueprint.sections[0].section_id,  # Same ID
        heading="Duplicate Section",
        journal_slot=JournalSlot.METHODS,
    )
    sample_blueprint.sections.append(duplicate_section)
    
    with pytest.raises(ValueError, match="Section IDs must be unique"):
        blueprint_service.save_blueprint(sample_blueprint)


def test_get_blueprint_latest(blueprint_service, mock_db):
    """Test getting latest blueprint version."""
    project_id = "test-project-123"
    blueprint_doc = {
        "blueprint_id": "blueprint-123",
        "project_id": project_id,
        "version": 2,
        "sections": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    cursor = Mock()
    cursor.__iter__ = Mock(return_value=iter([blueprint_doc]))
    mock_db.aql.execute = Mock(return_value=cursor)
    mock_db.has_collection.return_value = True
    
    blueprint = blueprint_service.get_blueprint(project_id)
    
    assert blueprint is not None
    assert blueprint.blueprint_id == "blueprint-123"
    assert blueprint.version == 2
    assert mock_db.aql.execute.called_once


def test_get_blueprint_specific_version(blueprint_service, mock_db):
    """Test getting specific blueprint version."""
    project_id = "test-project-123"
    version = 1
    
    blueprint_doc = {
        "blueprint_id": "blueprint-123",
        "project_id": project_id,
        "version": version,
        "sections": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    cursor = Mock()
    cursor.__iter__ = Mock(return_value=iter([blueprint_doc]))
    mock_db.aql.execute = Mock(return_value=cursor)
    mock_db.has_collection.return_value = True
    
    blueprint = blueprint_service.get_blueprint(project_id, version=version)
    
    assert blueprint is not None
    assert blueprint.version == version


def test_get_blueprint_not_found(blueprint_service, mock_db):
    """Test getting non-existent blueprint."""
    cursor = Mock()
    cursor.__iter__ = Mock(return_value=iter([]))
    mock_db.aql.execute = Mock(return_value=cursor)
    mock_db.has_collection.return_value = True
    
    blueprint = blueprint_service.get_blueprint("non-existent-project")
    
    assert blueprint is None


def test_list_blueprints(blueprint_service, mock_db):
    """Test listing all blueprint versions for a project."""
    project_id = "test-project-123"
    
    blueprints_data = [
        {
            "blueprint_id": "blueprint-123",
            "project_id": project_id,
            "version": 2,
            "sections": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "blueprint_id": "blueprint-123",
            "project_id": project_id,
            "version": 1,
            "sections": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    
    cursor = Mock()
    cursor.__iter__ = Mock(return_value=iter(blueprints_data))
    mock_db.aql.execute = Mock(return_value=cursor)
    mock_db.has_collection.return_value = True
    
    blueprints = blueprint_service.list_blueprints(project_id)
    
    assert len(blueprints) == 2
    assert blueprints[0].version == 2  # Sorted by version DESC
    assert blueprints[1].version == 1
