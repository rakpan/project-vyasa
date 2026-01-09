"""
Unit tests for Blueprint API endpoints.

Tests:
- GET /api/projects/:project_id/blueprint (get blueprint)
- POST /api/projects/:project_id/blueprint (save blueprint)
- POST /api/projects/:project_id/sections/:section_id/run (run section)
- GET /api/projects/:project_id/sections/:section_id/status (get section status)
- GET /api/projects/:project_id/manuscript/blocks (list manuscript blocks)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

from src.orchestrator.api.blueprint import blueprint_bp, _get_blueprint_service
from src.orchestrator.services.blueprint_service import BlueprintService
from src.orchestrator.schemas.blueprint import (
    ManuscriptBlueprint,
    BlueprintSection,
    JournalSlot,
    DepthIntent,
)


@pytest.fixture
def app():
    """Flask test app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(blueprint_bp)
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def mock_blueprint_service():
    """Mock BlueprintService."""
    service = Mock(spec=BlueprintService)
    return service


@pytest.fixture
def sample_blueprint():
    """Sample Manuscript Blueprint for testing."""
    section = BlueprintSection(
        section_id="section-1",
        heading="Introduction",
        journal_slot=JournalSlot.INTRODUCTION,
        linked_rqs=["RQ1"],
        depth_intent=DepthIntent.PROOF,
    )
    
    return ManuscriptBlueprint.create(
        project_id="test-project-123",
        sections=[section],
        target_journal="IEEE Security & Privacy",
    )


def test_get_blueprint_success(client, mock_blueprint_service, sample_blueprint):
    """Test getting blueprint successfully."""
    project_id = "test-project-123"
    
    mock_blueprint_service.get_blueprint.return_value = sample_blueprint
    
    with patch('src.orchestrator.api.blueprint._get_blueprint_service', return_value=mock_blueprint_service):
        response = client.get(f'/api/projects/{project_id}/blueprint')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["blueprint_id"] == sample_blueprint.blueprint_id
    assert len(data["sections"]) == 1
    mock_blueprint_service.get_blueprint.assert_called_once_with(project_id, version=None)


def test_get_blueprint_with_version(client, mock_blueprint_service, sample_blueprint):
    """Test getting blueprint with specific version."""
    project_id = "test-project-123"
    version = 2
    
    sample_blueprint.version = version
    mock_blueprint_service.get_blueprint.return_value = sample_blueprint
    
    with patch('src.orchestrator.api.blueprint._get_blueprint_service', return_value=mock_blueprint_service):
        response = client.get(
            f'/api/projects/{project_id}/blueprint',
            query_string={"version": str(version)}
        )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["version"] == version
    mock_blueprint_service.get_blueprint.assert_called_once_with(project_id, version=version)


def test_get_blueprint_not_found(client, mock_blueprint_service):
    """Test getting non-existent blueprint."""
    project_id = "non-existent-project"
    
    mock_blueprint_service.get_blueprint.return_value = None
    
    with patch('src.orchestrator.api.blueprint._get_blueprint_service', return_value=mock_blueprint_service):
        response = client.get(f'/api/projects/{project_id}/blueprint')
    
    assert response.status_code == 404
    data = response.get_json()
    assert "not found" in data["error"].lower()


def test_save_blueprint_success(client, mock_blueprint_service, sample_blueprint):
    """Test saving blueprint successfully."""
    project_id = "test-project-123"
    
    mock_blueprint_service.save_blueprint.return_value = sample_blueprint
    
    with patch('src.orchestrator.api.blueprint._get_blueprint_service', return_value=mock_blueprint_service):
        response = client.post(
            f'/api/projects/{project_id}/blueprint',
            json={
                "sections": [
                    {
                        "heading": "Introduction",
                        "journal_slot": "introduction",
                        "linked_rqs": ["RQ1"],
                        "depth_intent": "proof",
                    }
                ],
                "target_journal": "IEEE Security & Privacy",
            }
        )
    
    assert response.status_code == 201
    data = response.get_json()
    assert data["blueprint_id"] == sample_blueprint.blueprint_id
    assert len(data["sections"]) == 1
    mock_blueprint_service.save_blueprint.assert_called_once()


def test_save_blueprint_empty_sections(client, mock_blueprint_service):
    """Test saving blueprint with empty sections."""
    project_id = "test-project-123"
    
    with patch('src.orchestrator.api.blueprint._get_blueprint_service', return_value=mock_blueprint_service):
        response = client.post(
            f'/api/projects/{project_id}/blueprint',
            json={"sections": []}
        )
    
    assert response.status_code == 400
    data = response.get_json()
    assert "at least one section" in data["error"].lower()


def test_save_blueprint_invalid_journal_slot(client, mock_blueprint_service):
    """Test saving blueprint with invalid journal_slot."""
    project_id = "test-project-123"
    
    with patch('src.orchestrator.api.blueprint._get_blueprint_service', return_value=mock_blueprint_service):
        response = client.post(
            f'/api/projects/{project_id}/blueprint',
            json={
                "sections": [
                    {
                        "heading": "Introduction",
                        "journal_slot": "invalid_slot",
                        "linked_rqs": ["RQ1"],
                    }
                ]
            }
        )
    
    assert response.status_code == 400
    data = response.get_json()
    assert "invalid journal_slot" in data["error"].lower()


def test_save_blueprint_invalid_depth_intent(client, mock_blueprint_service):
    """Test saving blueprint with invalid depth_intent."""
    project_id = "test-project-123"
    
    with patch('src.orchestrator.api.blueprint._get_blueprint_service', return_value=mock_blueprint_service):
        response = client.post(
            f'/api/projects/{project_id}/blueprint',
            json={
                "sections": [
                    {
                        "heading": "Introduction",
                        "journal_slot": "introduction",
                        "depth_intent": "invalid_intent",
                    }
                ]
            }
        )
    
    assert response.status_code == 400
    data = response.get_json()
    assert "invalid depth_intent" in data["error"].lower()


def test_run_section_success(client, mock_blueprint_service, sample_blueprint):
    """Test running section synthesis."""
    project_id = "test-project-123"
    section_id = "section-1"
    
    mock_blueprint_service.get_blueprint.return_value = sample_blueprint
    
    with patch('src.orchestrator.api.blueprint._get_blueprint_service', return_value=mock_blueprint_service):
        with patch('src.orchestrator.api.blueprint.create_job_record', return_value="job-123"):
            response = client.post(
                f'/api/projects/{project_id}/sections/{section_id}/run',
                json={"ingestion_id": "ingestion-123"}
            )
    
    assert response.status_code == 202
    data = response.get_json()
    assert data["job_id"] == "job-123"
    assert "status" in data


def test_run_section_blueprint_not_found(client, mock_blueprint_service):
    """Test running section when blueprint not found."""
    project_id = "test-project-123"
    section_id = "section-1"
    
    mock_blueprint_service.get_blueprint.return_value = None
    
    with patch('src.orchestrator.api.blueprint._get_blueprint_service', return_value=mock_blueprint_service):
        response = client.post(
            f'/api/projects/{project_id}/sections/{section_id}/run',
            json={}
        )
    
    assert response.status_code == 404
    data = response.get_json()
    assert "blueprint not found" in data["error"].lower()


def test_run_section_section_not_found(client, mock_blueprint_service, sample_blueprint):
    """Test running section when section not found in blueprint."""
    project_id = "test-project-123"
    section_id = "non-existent-section"
    
    mock_blueprint_service.get_blueprint.return_value = sample_blueprint
    
    with patch('src.orchestrator.api.blueprint._get_blueprint_service', return_value=mock_blueprint_service):
        response = client.post(
            f'/api/projects/{project_id}/sections/{section_id}/run',
            json={}
        )
    
    assert response.status_code == 404
    data = response.get_json()
    assert "section" in data["error"].lower() and "not found" in data["error"].lower()


def test_get_section_status_success(client):
    """Test getting section synthesis status."""
    project_id = "test-project-123"
    section_id = "section-1"
    job_id = "job-123"
    
    job_record = {
        "job_id": job_id,
        "status": "completed",
        "progress": 1.0,
        "message": "Completed",
        "error": None,
        "result": {"block_id": "block-1"},
        "initial_state": {
            "project_id": project_id,
            "section_id": section_id,
        },
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    }
    
    with patch('src.orchestrator.api.blueprint.get_job_record', return_value=job_record):
        response = client.get(
            f'/api/projects/{project_id}/sections/{section_id}/status',
            query_string={"job_id": job_id}
        )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["job_id"] == job_id
    assert data["status"] == "completed"
    assert data["progress"] == 1.0


def test_get_section_status_stage_complete(client):
    """Test getting section status with current_step='complete' maps to stage='complete'."""
    project_id = "test-project-123"
    section_id = "section-1"
    job_id = "job-123"
    
    job_record = {
        "job_id": job_id,
        "status": "SUCCEEDED",
        "progress": 1.0,
        "current_step": "complete",
        "message": "Section synthesis completed",
        "error": None,
        "result": {"block_id": "block-1"},
        "initial_state": {
            "project_id": project_id,
            "section_id": section_id,
        },
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    }
    
    with patch('src.orchestrator.api.blueprint.get_job_record', return_value=job_record):
        response = client.get(
            f'/api/projects/{project_id}/sections/{section_id}/status',
            query_string={"job_id": job_id}
        )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["stage"] == "complete"
    assert data["current_step"] == "complete"


def test_get_section_status_stage_unmapped(client):
    """Test getting section status with unmapped current_step returns stage=None."""
    project_id = "test-project-123"
    section_id = "section-1"
    job_id = "job-123"
    
    job_record = {
        "job_id": job_id,
        "status": "RUNNING",
        "progress": 0.5,
        "current_step": "weird_step",
        "message": "Processing",
        "error": None,
        "result": None,
        "initial_state": {
            "project_id": project_id,
            "section_id": section_id,
        },
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    }
    
    with patch('src.orchestrator.api.blueprint.get_job_record', return_value=job_record):
        response = client.get(
            f'/api/projects/{project_id}/sections/{section_id}/status',
            query_string={"job_id": job_id}
        )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["stage"] is None  # Unmapped stage returns None, not "unknown"
    assert data["current_step"] == "weird_step"  # Raw current_step still included


def test_get_section_status_stage_missing(client):
    """Test getting section status with missing current_step returns stage=None."""
    project_id = "test-project-123"
    section_id = "section-1"
    job_id = "job-123"
    
    job_record = {
        "job_id": job_id,
        "status": "QUEUED",
        "progress": 0.0,
        "message": "Queued",
        "error": None,
        "result": None,
        "initial_state": {
            "project_id": project_id,
            "section_id": section_id,
        },
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }
    # Note: current_step is missing from job_record
    
    with patch('src.orchestrator.api.blueprint.get_job_record', return_value=job_record):
        response = client.get(
            f'/api/projects/{project_id}/sections/{section_id}/status',
            query_string={"job_id": job_id}
        )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["stage"] is None  # Missing current_step returns None
    assert data.get("current_step") is None  # current_step is None when missing


def test_get_section_status_no_job_id(client):
    """Test getting section status without job_id."""
    project_id = "test-project-123"
    section_id = "section-1"
    
    response = client.get(
        f'/api/projects/{project_id}/sections/{section_id}/status'
    )
    
    assert response.status_code == 400
    data = response.get_json()
    assert "job_id" in data["error"].lower()


def test_list_manuscript_blocks_success(client):
    """Test listing manuscript blocks."""
    project_id = "test-project-123"
    
    from src.shared.schema import ManuscriptBlock
    
    blocks = [
        ManuscriptBlock(
            block_id="block-1",
            section_title="Introduction",
            content="# Introduction\n\n...",
            order_index=0,
            claim_ids=["claim-1"],
            citation_keys=["smith2023"],
        ),
        ManuscriptBlock(
            block_id="block-2",
            section_title="Methods",
            content="# Methods\n\n...",
            order_index=1,
            claim_ids=["claim-2"],
            citation_keys=["jones2024"],
        ),
    ]
    
    mock_manuscript_service = Mock()
    mock_manuscript_service.list_blocks = Mock(return_value=blocks)
    
    with patch('src.orchestrator.api.blueprint._get_db', return_value=Mock()):
        with patch('src.orchestrator.api.blueprint.ManuscriptService', return_value=mock_manuscript_service):
            response = client.get(f'/api/projects/{project_id}/manuscript/blocks')
    
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2
    assert data[0]["block_id"] == "block-1"
    assert data[1]["block_id"] == "block-2"


def test_list_manuscript_blocks_with_section_filter(client):
    """Test listing manuscript blocks filtered by section_id."""
    project_id = "test-project-123"
    section_id = "section-1"
    
    from src.shared.schema import ManuscriptBlock
    
    blocks = [
        ManuscriptBlock(
            block_id="block-1",
            section_title="Introduction",
            content="# Introduction\n\n...",
            order_index=0,
            section_id=section_id,  # type: ignore
        ),
    ]
    
    mock_manuscript_service = Mock()
    mock_manuscript_service.list_blocks = Mock(return_value=blocks)
    
    with patch('src.orchestrator.api.blueprint._get_db', return_value=Mock()):
        with patch('src.orchestrator.api.blueprint.ManuscriptService', return_value=mock_manuscript_service):
            response = client.get(
                f'/api/projects/{project_id}/manuscript/blocks',
                query_string={"section_id": section_id}
            )
    
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["block_id"] == "block-1"
