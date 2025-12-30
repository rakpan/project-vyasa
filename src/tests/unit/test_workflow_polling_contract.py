"""
Contract tests for workflow polling endpoints.

What's covered:
- GET /workflow/status/<job_id>: 404 when missing, returns progress_pct and status
- GET /workflow/result/<job_id>: 404 when missing, 202 when QUEUED/RUNNING, 500 when FAILED, 200 when SUCCEEDED
- Result normalization: extracted_json.triples is always present (even if empty)
- Error propagation: FAILED jobs include error message

All external dependencies are mocked (job_manager, normalize_extracted_json).
"""

import json
from unittest.mock import Mock, patch
import pytest

from src.orchestrator.server import app
from src.orchestrator.state import JobStatus
from datetime import datetime, timezone


@pytest.fixture
def client():
    """Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_job_info():
    """Create a mock JobInfo structure."""
    def _create_job(status, result=None, error=None, progress=0.0, current_step=None):
        return {
            "job_id": "job-123",
            "status": status,
            "result": result,
            "error": error,
            "progress": progress,
            "current_step": current_step,
            "created_at": datetime.now(timezone.utc),
            "started_at": datetime.now(timezone.utc) if status != JobStatus.QUEUED else None,
            "completed_at": datetime.now(timezone.utc) if status in (JobStatus.SUCCEEDED, JobStatus.FAILED) else None,
        }
    return _create_job


def test_get_workflow_status_404_when_missing(client):
    """GET /workflow/status/<job_id>: 404 when job missing."""
    with patch('src.orchestrator.server.get_job', return_value=None):
        response = client.get('/workflow/status/nonexistent-job')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data
        assert "not found" in data["error"].lower()


def test_get_workflow_status_returns_progress_and_status(client, mock_job_info):
    """GET /workflow/status/<job_id>: returns progress_pct and status fields."""
    job = mock_job_info(
        status=JobStatus.RUNNING,
        progress=0.5,
        current_step="Cartographer"
    )
    
    with patch('src.orchestrator.server.get_job', return_value=job):
        response = client.get('/workflow/status/job-123')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert "job_id" in data
        assert data["job_id"] == "job-123"
        assert "status" in data
        assert data["status"] == JobStatus.RUNNING.value
        assert "progress_pct" in data
        assert data["progress_pct"] == 50.0
        assert "current_step" in data
        assert data["current_step"] == "Cartographer"
        assert "created_at" in data
        assert "started_at" in data


def test_get_workflow_status_completed_includes_result(client, mock_job_info):
    """GET /workflow/status/<job_id>: COMPLETED includes result."""
    result = {
        "raw_text": "Test text",
        "extracted_json": {"triples": [{"subject": "A", "predicate": "relates", "object": "B"}]},
    }
    job = mock_job_info(
        status=JobStatus.SUCCEEDED,
        result=result,
        progress=1.0
    )
    
    with patch('src.orchestrator.server.get_job', return_value=job):
        response = client.get('/workflow/status/job-123')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert "status" in data
        assert data["status"] == JobStatus.SUCCEEDED.value
        assert "result" in data
        assert data["result"]["raw_text"] == "Test text"
        assert "completed_at" in data


def test_get_workflow_result_404_when_missing(client):
    """GET /workflow/result/<job_id>: 404 when missing."""
    with patch('src.orchestrator.server.get_job', return_value=None):
        response = client.get('/workflow/result/nonexistent-job')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data
        assert "not found" in data["error"].lower()


def test_get_workflow_result_202_when_queued(client, mock_job_info):
    """GET /workflow/result/<job_id>: 202 when QUEUED."""
    job = mock_job_info(
        status=JobStatus.QUEUED,
        progress=0.0
    )
    
    with patch('src.orchestrator.server.get_job', return_value=job):
        response = client.get('/workflow/result/job-123')
        
        assert response.status_code == 202
        data = json.loads(response.data)
        
        assert "job_id" in data
        assert data["job_id"] == "job-123"
        assert "status" in data
        assert data["status"] == JobStatus.QUEUED.value
        assert "progress_pct" in data
        assert "result" not in data  # No result yet


def test_get_workflow_result_202_when_running(client, mock_job_info):
    """GET /workflow/result/<job_id>: 202 when RUNNING."""
    job = mock_job_info(
        status=JobStatus.RUNNING,
        progress=0.3,
        current_step="Critic"
    )
    
    with patch('src.orchestrator.server.get_job', return_value=job):
        response = client.get('/workflow/result/job-123')
        
        assert response.status_code == 202
        data = json.loads(response.data)
        
        assert "status" in data
        assert data["status"] == JobStatus.RUNNING.value
        assert "progress_pct" in data
        assert data["progress_pct"] == 30.0
        assert "result" not in data  # No result yet


def test_get_workflow_result_500_when_failed(client, mock_job_info):
    """GET /workflow/result/<job_id>: 500 when FAILED (includes error)."""
    error_msg = "Database connection failed"
    job = mock_job_info(
        status=JobStatus.FAILED,
        error=error_msg,
        progress=0.0
    )
    
    with patch('src.orchestrator.server.get_job', return_value=job):
        response = client.get('/workflow/result/job-123')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        
        assert "job_id" in data
        assert data["job_id"] == "job-123"
        assert "status" in data
        assert data["status"] == JobStatus.FAILED.value
        assert "error" in data
        assert data["error"] == error_msg


def test_get_workflow_result_200_when_succeeded_with_triples(client, mock_job_info):
    """GET /workflow/result/<job_id>: 200 when SUCCEEDED, MUST include extracted_json.triples."""
    result = {
        "raw_text": "Test text",
        "extracted_json": {"triples": [{"subject": "A", "predicate": "relates", "object": "B"}]},
        "critiques": [],
    }
    job = mock_job_info(
        status=JobStatus.SUCCEEDED,
        result=result
    )
    
    with patch('src.orchestrator.server.get_job', return_value=job):
        with patch('src.orchestrator.server.normalize_extracted_json') as mock_normalize:
            # Mock normalize to ensure it's called
            mock_normalize.return_value = {"triples": [{"subject": "A", "predicate": "relates", "object": "B"}]}
            
            response = client.get('/workflow/result/job-123')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert "job_id" in data
            assert data["job_id"] == "job-123"
            assert "status" in data
            assert data["status"] == JobStatus.SUCCEEDED.value
            assert "result" in data
            
            # Critical: extracted_json.triples must be present
            assert "extracted_json" in data["result"]
            assert "triples" in data["result"]["extracted_json"]
            assert isinstance(data["result"]["extracted_json"]["triples"], list)
            assert len(data["result"]["extracted_json"]["triples"]) == 1
            
            # Verify normalize was called
            mock_normalize.assert_called_once()


def test_get_workflow_result_200_normalizes_empty_triples(client, mock_job_info):
    """GET /workflow/result/<job_id>: Normalizes empty/missing triples to empty list."""
    result = {
        "raw_text": "Test text",
        "extracted_json": {},  # Missing triples
    }
    job = mock_job_info(
        status=JobStatus.SUCCEEDED,
        result=result
    )
    
    with patch('src.orchestrator.server.get_job', return_value=job):
        with patch('src.orchestrator.server.normalize_extracted_json') as mock_normalize:
            # Mock normalize to return empty triples
            mock_normalize.return_value = {"triples": []}
            
            response = client.get('/workflow/result/job-123')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Critical: triples must be present even if empty
            assert "extracted_json" in data["result"]
            assert "triples" in data["result"]["extracted_json"]
            assert isinstance(data["result"]["extracted_json"]["triples"], list)
            assert len(data["result"]["extracted_json"]["triples"]) == 0
            
            # Verify normalize was called
            mock_normalize.assert_called_once()


def test_get_workflow_result_200_normalizes_malformed_triples(client, mock_job_info):
    """GET /workflow/result/<job_id>: Normalizes malformed extracted_json."""
    result = {
        "raw_text": "Test text",
        "extracted_json": {"relations": [{"s": "A", "p": "relates", "o": "B"}]},  # Wrong key
    }
    job = mock_job_info(
        status=JobStatus.SUCCEEDED,
        result=result
    )
    
    with patch('src.orchestrator.server.get_job', return_value=job):
        with patch('src.orchestrator.server.normalize_extracted_json') as mock_normalize:
            # Mock normalize to convert relations -> triples
            mock_normalize.return_value = {"triples": [{"subject": "A", "predicate": "relates", "object": "B"}]}
            
            response = client.get('/workflow/result/job-123')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Critical: triples must be present after normalization
            assert "extracted_json" in data["result"]
            assert "triples" in data["result"]["extracted_json"]
            assert isinstance(data["result"]["extracted_json"]["triples"], list)
            
            # Verify normalize was called with the malformed input
            mock_normalize.assert_called_once_with({"relations": [{"s": "A", "p": "relates", "o": "B"}]})

