"""
Unit tests for saver reliability and "no silent success" behavior.

What's covered:
- Saver failure propagation: When saver_node raises exception, job becomes FAILED
- Error tracking: Failed jobs include error message in status
- Job status updates: update_job_status called with FAILED status and error

This tests server-level job status propagation, not DB integration.
All external dependencies are mocked (workflow, job_manager).
"""

import json
from unittest.mock import Mock, patch
import pytest

from src.orchestrator.server import app
from src.orchestrator.state import JobStatus


@pytest.fixture
def client():
    """Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_project_service():
    """Mock ProjectService instance."""
    service = Mock()
    from src.project.types import ProjectConfig
    
    project_config = ProjectConfig(
        id="550e8400-e29b-41d4-a716-446655440000",
        title="Test Project",
        thesis="Test thesis",
        research_questions=["RQ1"],
        seed_files=[],
        created_at="2024-01-15T10:30:00Z",
    )
    
    service.get_project.return_value = project_config
    return service


def test_saver_failure_propagates_to_job_status(mock_project_service):
    """When saver_node raises exception, job becomes FAILED with error."""
    from src.orchestrator.server import _run_workflow_async
    
    job_id = "job-fail-123"
    initial_state = {
        "raw_text": "Test text",
        "project_id": "550e8400-e29b-41d4-a716-446655440000",
    }
    
    # Mock workflow to raise exception (simulating saver failure)
    mock_workflow = Mock()
    db_error = Exception("ArangoDB connection failed: Connection refused")
    mock_workflow.invoke.side_effect = db_error
    
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        with patch('src.orchestrator.server.workflow_app', mock_workflow):
            with patch('src.orchestrator.server.acquire_job_slot', return_value=True):
                with patch('src.orchestrator.server.release_job_slot') as mock_release:
                    with patch('src.orchestrator.server.update_job_status') as mock_update_status:
                        # Execute async workflow
                        _run_workflow_async(job_id, initial_state)
                        
                        # Verify job status was updated to FAILED
                        mock_update_status.assert_any_call(
                            job_id,
                            JobStatus.FAILED,
                            error=str(db_error),
                            message="Failed"
                        )
                        
                        # Verify slot was released (cleanup)
                        mock_release.assert_called_once()


def test_saver_failure_includes_error_message(mock_project_service):
    """Failed jobs include error message in status response."""
    from src.orchestrator.server import _run_workflow_async, get_job
    
    job_id = "job-fail-456"
    initial_state = {
        "raw_text": "Test text",
        "project_id": "550e8400-e29b-41d4-a716-446655440000",
    }
    
    error_msg = "ArangoDB write failed: Collection 'claims' not found"
    
    # Mock workflow to raise exception
    mock_workflow = Mock()
    mock_workflow.invoke.side_effect = Exception(error_msg)
    
    # Mock job registry to track status updates
    from src.orchestrator.job_manager import _job_registry, _registry_lock
    from datetime import datetime, timezone
    
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        with patch('src.orchestrator.server.workflow_app', mock_workflow):
            with patch('src.orchestrator.server.acquire_job_slot', return_value=True):
                with patch('src.orchestrator.server.release_job_slot'):
                    # Initialize job in registry
                    with _registry_lock:
                        _job_registry[job_id] = {
                            "job_id": job_id,
                            "status": JobStatus.QUEUED,
                            "created_at": datetime.now(timezone.utc),
                        }
                    
                    # Execute async workflow
                    _run_workflow_async(job_id, initial_state)
                    
                    # Verify job status in registry
                    with _registry_lock:
                        job = _job_registry.get(job_id)
                        assert job is not None
                        assert job["status"] == JobStatus.FAILED
                        assert "error" in job
                        assert error_msg in job["error"]


def test_saver_failure_does_not_silently_succeed(mock_project_service):
    """Saver failures must not result in silent success (job must be marked FAILED)."""
    from src.orchestrator.server import _run_workflow_async
    
    job_id = "job-fail-789"
    initial_state = {
        "raw_text": "Test text",
        "project_id": "550e8400-e29b-41d4-a716-446655440000",
    }
    
    # Mock workflow to raise exception
    mock_workflow = Mock()
    mock_workflow.invoke.side_effect = Exception("DB write failed")
    
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        with patch('src.orchestrator.server.workflow_app', mock_workflow):
            with patch('src.orchestrator.server.acquire_job_slot', return_value=True):
                with patch('src.orchestrator.server.release_job_slot'):
                    with patch('src.orchestrator.server.set_job_result') as mock_set_result:
                        # Execute async workflow
                        _run_workflow_async(job_id, initial_state)
                        
                        # Critical: set_job_result should NOT be called on failure
                        mock_set_result.assert_not_called()


def test_saver_success_sets_result(mock_project_service):
    """When saver succeeds, job result is set and status is SUCCEEDED."""
    from src.orchestrator.server import _run_workflow_async
    
    job_id = "job-success-123"
    initial_state = {
        "raw_text": "Test text",
        "project_id": "550e8400-e29b-41d4-a716-446655440000",
    }
    
    # Mock successful workflow result
    workflow_result = {
        "raw_text": "Test text",
        "extracted_json": {"triples": [{"subject": "A", "predicate": "relates", "object": "B"}]},
        "critiques": [],
    }
    
    mock_workflow = Mock()
    mock_workflow.invoke.return_value = workflow_result
    
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        with patch('src.orchestrator.server.workflow_app', mock_workflow):
            with patch('src.orchestrator.server.acquire_job_slot', return_value=True):
                with patch('src.orchestrator.server.release_job_slot'):
                    with patch('src.orchestrator.server.set_job_result') as mock_set_result:
                        with patch('src.orchestrator.server.update_job_status') as mock_update_status:
                            # Execute async workflow
                            _run_workflow_async(job_id, initial_state)
                            
                            # Verify result was set
                            mock_set_result.assert_called_once_with(job_id, workflow_result)
                            
                            # Verify status was updated to SUCCEEDED (via set_job_result)
                            # Note: set_job_result internally updates status, so we verify it was called

