"""
Unit tests for ingestion API endpoints.

Tests:
- Duplicate detection logic
- Status transitions
- First glance summary generation
- Retry operations
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

from src.orchestrator.api.ingestion import ingestion_bp, _get_ingestion_store
from src.orchestrator.ingestion_store import IngestionStore, IngestionStatus, IngestionRecord
from src.orchestrator.state import JobStatus


@pytest.fixture
def app():
    """Flask test app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(ingestion_bp)
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def mock_ingestion_store():
    """Mock IngestionStore."""
    store = Mock(spec=IngestionStore)
    return store


@pytest.fixture
def mock_project_service():
    """Mock ProjectService."""
    service = Mock()
    service.db = Mock()
    return service


def test_check_duplicate_success(client, mock_ingestion_store, mock_project_service):
    """Test duplicate detection with matches."""
    project_id = "test-project-123"
    file_hash = "a" * 64  # Valid SHA256 hash
    
    # Mock duplicate results
    duplicates = [
        {"project_id": "other-project-1", "title": "Other Project 1"},
        {"project_id": "other-project-2", "title": "Other Project 2"},
    ]
    mock_ingestion_store.find_duplicates.return_value = duplicates
    
    with patch('src.orchestrator.api.ingestion._get_ingestion_store', return_value=mock_ingestion_store):
        response = client.post(
            f'/api/projects/{project_id}/ingest/check-duplicate',
            json={"file_hash": file_hash, "filename": "test.pdf"}
        )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["is_duplicate"] is True
    assert len(data["matches"]) == 2
    mock_ingestion_store.find_duplicates.assert_called_once_with(file_hash, exclude_project_id=project_id)


def test_check_duplicate_no_matches(client, mock_ingestion_store):
    """Test duplicate detection with no matches."""
    project_id = "test-project-123"
    file_hash = "a" * 64
    
    mock_ingestion_store.find_duplicates.return_value = []
    
    with patch('src.orchestrator.api.ingestion._get_ingestion_store', return_value=mock_ingestion_store):
        response = client.post(
            f'/api/projects/{project_id}/ingest/check-duplicate',
            json={"file_hash": file_hash}
        )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["is_duplicate"] is False
    assert len(data["matches"]) == 0


def test_check_duplicate_invalid_hash(client):
    """Test duplicate detection with invalid hash format."""
    project_id = "test-project-123"
    
    response = client.post(
        f'/api/projects/{project_id}/ingest/check-duplicate',
        json={"file_hash": "invalid"}
    )
    
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_get_ingestion_status_queued(client, mock_ingestion_store):
    """Test getting ingestion status in Queued state."""
    project_id = "test-project-123"
    ingestion_id = "ingestion-123"
    
    record = IngestionRecord(
        ingestion_id=ingestion_id,
        project_id=project_id,
        filename="test.pdf",
        file_hash="a" * 64,
        status=IngestionStatus.QUEUED,
        progress_pct=0.0,
    )
    mock_ingestion_store.get_ingestion.return_value = record
    
    with patch('src.orchestrator.api.ingestion._get_ingestion_store', return_value=mock_ingestion_store):
        with patch('src.orchestrator.job_manager.get_job', return_value=None):
            response = client.get(
                f'/api/projects/{project_id}/ingest/{ingestion_id}/status'
            )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["ingestion_id"] == ingestion_id
    assert data["status"] == IngestionStatus.QUEUED
    assert data["progress_pct"] == 0.0


def test_get_ingestion_status_with_job(client, mock_ingestion_store):
    """Test getting ingestion status synced from job."""
    project_id = "test-project-123"
    ingestion_id = "ingestion-123"
    job_id = "job-123"
    
    record = IngestionRecord(
        ingestion_id=ingestion_id,
        project_id=project_id,
        filename="test.pdf",
        file_hash="a" * 64,
        status=IngestionStatus.QUEUED,
        job_id=job_id,
        progress_pct=0.0,
    )
    mock_ingestion_store.get_ingestion.return_value = record
    
    job = {
        "job_id": job_id,
        "status": JobStatus.RUNNING,
        "current_step": "cartographer",
        "progress": 0.3,
    }
    
    with patch('src.orchestrator.api.ingestion._get_ingestion_store', return_value=mock_ingestion_store):
        with patch('src.orchestrator.job_manager.get_job', return_value=job):
            response = client.get(
                f'/api/projects/{project_id}/ingest/{ingestion_id}/status'
            )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == IngestionStatus.EXTRACTING
    assert data["progress_pct"] == 30.0


def test_get_ingestion_status_completed_with_first_glance(client, mock_ingestion_store):
    """Test getting ingestion status with first glance summary."""
    project_id = "test-project-123"
    ingestion_id = "ingestion-123"
    job_id = "job-123"
    
    record = IngestionRecord(
        ingestion_id=ingestion_id,
        project_id=project_id,
        filename="test.pdf",
        file_hash="a" * 64,
        status=IngestionStatus.QUEUED,
        job_id=job_id,
        progress_pct=0.0,
    )
    mock_ingestion_store.get_ingestion.return_value = record
    
    job = {
        "job_id": job_id,
        "status": JobStatus.SUCCEEDED,
        "progress": 1.0,
        "result": {
            "raw_text": "x" * 10000,  # ~3 pages
            "extracted_json": {
                "triples": [
                    {"subject": "Table 1", "object": "data", "source_pointer": {}},
                    {"subject": "Figure 1", "object": "chart", "source_pointer": {}},
                ] * 5,  # 10 triples total
            },
        },
    }
    
    with patch('src.orchestrator.api.ingestion._get_ingestion_store', return_value=mock_ingestion_store):
        with patch('src.orchestrator.job_manager.get_job', return_value=job):
            response = client.get(
                f'/api/projects/{project_id}/ingest/{ingestion_id}/status'
            )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == IngestionStatus.COMPLETED
    assert "first_glance" in data
    assert data["first_glance"]["pages"] >= 1
    assert "confidence" in data


def test_retry_ingestion(client, mock_ingestion_store):
    """Test retrying a failed ingestion."""
    project_id = "test-project-123"
    ingestion_id = "ingestion-123"
    
    record = IngestionRecord(
        ingestion_id=ingestion_id,
        project_id=project_id,
        filename="test.pdf",
        file_hash="a" * 64,
        status=IngestionStatus.FAILED,
        error_message="Processing failed",
    )
    mock_ingestion_store.get_ingestion.return_value = record
    mock_ingestion_store.update_ingestion.return_value = True
    
    with patch('src.orchestrator.api.ingestion._get_ingestion_store', return_value=mock_ingestion_store):
        response = client.post(
            f'/api/projects/{project_id}/ingest/{ingestion_id}/retry'
        )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["ingestion_id"] == ingestion_id
    assert data["status"] == IngestionStatus.QUEUED
    mock_ingestion_store.update_ingestion.assert_called_once()
    call_kwargs = mock_ingestion_store.update_ingestion.call_args[1]
    assert call_kwargs["status"] == IngestionStatus.QUEUED
    assert call_kwargs["error_message"] is None


def test_retry_ingestion_not_failed(client, mock_ingestion_store):
    """Test retrying a non-failed ingestion should fail."""
    project_id = "test-project-123"
    ingestion_id = "ingestion-123"
    
    record = IngestionRecord(
        ingestion_id=ingestion_id,
        project_id=project_id,
        filename="test.pdf",
        file_hash="a" * 64,
        status=IngestionStatus.COMPLETED,
    )
    mock_ingestion_store.get_ingestion.return_value = record
    
    with patch('src.orchestrator.api.ingestion._get_ingestion_store', return_value=mock_ingestion_store):
        response = client.post(
            f'/api/projects/{project_id}/ingest/{ingestion_id}/retry'
        )
    
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data

