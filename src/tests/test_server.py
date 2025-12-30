"""
Unit tests for Orchestrator API server (src/orchestrator/server.py).

Tests API endpoints with project_id support and middleware context injection.
All external dependencies (ArangoDB, workflow) are mocked.

Coverage Checklist:
- [x] POST /workflow/submit (JSON): Success with project_id
- [x] POST /workflow/submit (JSON): Missing project_id -> 400
- [x] POST /workflow/submit (JSON): Project not found -> 404 (FIXED: was 202, now 404)
- [x] POST /workflow/submit (JSON): Missing raw_text -> 400
- [x] POST /ingest/pdf: With project_id calls add_seed_file
- [x] POST /ingest/pdf: Without project_id works (optional)
- [x] POST /ingest/pdf: Invalid file format -> 400
- [x] POST /api/projects: Create project
- [x] POST /api/projects: Validation error -> 400
- [x] GET /api/projects/<id>: Get project
- [x] GET /api/projects/<id>: Not found -> 404
- [x] GET /api/projects: List projects

Missing (covered in test_server_project_first.py):
- [ ] POST /workflow/submit (JSON): DB unavailable -> 503
- [ ] POST /workflow/submit (multipart): All cases
- [ ] Polling endpoints (covered in test_workflow_polling_contract.py)
- [ ] Saver reliability (covered in test_saver_reliability.py)
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
import pytest

from src.orchestrator.server import app
from src.orchestrator.state import JobStatus
from src.project.types import ProjectConfig, ProjectCreate


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
    
    # Default project config
    project_id = "550e8400-e29b-41d4-a716-446655440000"
    project_config = ProjectConfig(
        id=project_id,
        title="Test Project",
        thesis="Test thesis statement",
        research_questions=["RQ1: What is the question?"],
        seed_files=[],
        created_at="2024-01-15T10:30:00Z",
    )
    
    service.get_project.return_value = project_config
    service.add_seed_file = Mock()
    service.create_project = Mock(return_value=project_config)
    service.list_projects = Mock(return_value=[])
    
    return service


@pytest.fixture
def mock_workflow():
    """Mock LangGraph workflow."""
    workflow = Mock()
    workflow.invoke = Mock(return_value={
        "raw_text": "Test text",
        "extracted_json": {"triples": []},
        "critiques": [],
    })
    return workflow


def test_workflow_submit_success_with_project_id(client, mock_project_service, mock_workflow):
    """POST /workflow/submit with valid project_id should inject project_context."""
    # Setup: Mock ProjectService and workflow
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        with patch('src.orchestrator.server.workflow_app', mock_workflow):
            with patch('src.orchestrator.server._run_workflow_async') as mock_async:
                # Execute
                response = client.post(
                    '/workflow/submit',
                    json={
                        "raw_text": "Test document text",
                        "project_id": "550e8400-e29b-41d4-a716-446655440000",
                    },
                    content_type='application/json',
                )
                
                # Verify
                assert response.status_code == 202
                data = json.loads(response.data)
                assert "job_id" in data
                assert data["status"] == "QUEUED"
                
                # Verify async function was called with project_context
                mock_async.assert_called_once()
                call_args = mock_async.call_args
                initial_state = call_args[0][1]  # Second positional arg
                
                assert initial_state["project_id"] == "550e8400-e29b-41d4-a716-446655440000"
                assert "project_context" in initial_state
                assert initial_state["project_context"]["title"] == "Test Project"
                assert initial_state["project_context"]["thesis"] == "Test thesis statement"
                
                # Verify ProjectService was called
                mock_project_service.get_project.assert_called_once_with("550e8400-e29b-41d4-a716-446655440000")


def test_workflow_submit_failure_missing_project_id(client):
    """POST /workflow/submit without project_id should return 400 (required)."""
    response = client.post(
        '/workflow/submit',
        json={
            "raw_text": "Test document text",
        },
        content_type='application/json',
    )
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data
    assert "project_id" in data["error"].lower()


def test_workflow_submit_failure_missing_raw_text(client):
    """POST /workflow/submit without raw_text should return 400."""
    response = client.post(
        '/workflow/submit',
        json={},
        content_type='application/json',
    )
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data
    assert "raw_text" in data["error"].lower()


def test_workflow_submit_failure_project_not_found(client, mock_project_service):
    """POST /workflow/submit with invalid project_id should return 404."""
    mock_project_service.get_project.side_effect = ValueError("Project not found: invalid-id")
    
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        response = client.post(
            '/workflow/submit',
            json={
                "raw_text": "Test document text",
                "project_id": "invalid-id",
            },
            content_type='application/json',
        )
        
        # Should return 404 (Project-First invariant)
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data
        assert "not found" in data["error"].lower()


def test_ingest_pdf_with_project_id_calls_add_seed_file(client, mock_project_service):
    """POST /ingest/pdf with project_id should call add_seed_file."""
    # Create a dummy PDF file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_file.write(b'%PDF-1.4 fake pdf content')
        tmp_path = tmp_file.name
    
    try:
        with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
            with patch('src.orchestrator.server.process_pdf') as mock_process_pdf:
                mock_process_pdf.return_value = (
                    "# Test Markdown",
                    None,
                    [],
                )
                
                # Execute
                with open(tmp_path, 'rb') as f:
                    response = client.post(
                        '/ingest/pdf',
                        data={
                            'file': (f, 'test.pdf'),
                            'project_id': '550e8400-e29b-41d4-a716-446655440000',
                        },
                        content_type='multipart/form-data',
                    )
                
                # Verify
                assert response.status_code == 200
                data = json.loads(response.data)
                assert "markdown" in data
                assert data.get("project_id") == "550e8400-e29b-41d4-a716-446655440000"
                assert "project_context" in data
                
                # Verify add_seed_file was called
                mock_project_service.add_seed_file.assert_called_once_with(
                    "550e8400-e29b-41d4-a716-446655440000",
                    "test.pdf"
                )
                
                # Verify get_project was called
                mock_project_service.get_project.assert_called_once_with(
                    "550e8400-e29b-41d4-a716-446655440000"
                )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_ingest_pdf_without_project_id_works(client):
    """POST /ingest/pdf without project_id should work (optional)."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_file.write(b'%PDF-1.4 fake pdf content')
        tmp_path = tmp_file.name
    
    try:
        with patch('src.orchestrator.server.process_pdf') as mock_process_pdf:
            mock_process_pdf.return_value = (
                "# Test Markdown",
                None,
                [],
            )
            
            with open(tmp_path, 'rb') as f:
                response = client.post(
                    '/ingest/pdf',
                    data={
                        'file': (f, 'test.pdf'),
                    },
                    content_type='multipart/form-data',
                )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert "markdown" in data
            assert "project_id" not in data or data.get("project_id") is None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_ingest_pdf_invalid_file_format(client):
    """POST /ingest/pdf with non-PDF file should return 400."""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
        tmp_file.write(b'Not a PDF')
        tmp_path = tmp_file.name
    
    try:
        with open(tmp_path, 'rb') as f:
            response = client.post(
                '/ingest/pdf',
                data={
                    'file': (f, 'test.txt'),
                },
                content_type='multipart/form-data',
            )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "pdf" in data["error"].lower()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_create_project_endpoint(client, mock_project_service):
    """POST /api/projects should create a project."""
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        response = client.post(
            '/api/projects',
            json={
                "title": "New Project",
                "thesis": "Test thesis",
                "research_questions": ["RQ1"],
            },
            content_type='application/json',
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["title"] == "New Project"
        assert data["thesis"] == "Test thesis"
        assert "id" in data
        assert "created_at" in data
        
        mock_project_service.create_project.assert_called_once()


def test_create_project_endpoint_validation_error(client, mock_project_service):
    """POST /api/projects with invalid data should return 400."""
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        response = client.post(
            '/api/projects',
            json={
                "title": "",  # Empty title
                "thesis": "Test thesis",
                "research_questions": ["RQ1"],
            },
            content_type='application/json',
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data


def test_get_project_endpoint(client, mock_project_service):
    """GET /api/projects/<project_id> should return project config."""
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        response = client.get('/api/projects/550e8400-e29b-41d4-a716-446655440000')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert data["title"] == "Test Project"
        
        mock_project_service.get_project.assert_called_once_with("550e8400-e29b-41d4-a716-446655440000")


def test_get_project_endpoint_not_found(client, mock_project_service):
    """GET /api/projects/<project_id> with invalid ID should return 404."""
    mock_project_service.get_project.side_effect = ValueError("Project not found: invalid-id")
    
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        response = client.get('/api/projects/invalid-id')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data


def test_list_projects_endpoint(client, mock_project_service):
    """GET /api/projects should return list of project summaries."""
    from src.project.types import ProjectSummary
    
    summaries = [
        ProjectSummary(
            id="id1",
            title="Project 1",
            created_at="2024-01-01T00:00:00Z",
        ),
        ProjectSummary(
            id="id2",
            title="Project 2",
            created_at="2024-01-02T00:00:00Z",
        ),
    ]
    mock_project_service.list_projects.return_value = summaries
    
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        response = client.get('/api/projects')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["title"] == "Project 1"
        
        mock_project_service.list_projects.assert_called_once()


def test_jobs_status_maps_active_step_to_progress(client):
    """GET /jobs/<id>/status maps active node to progress/label."""
    fake_job = {
        "job_id": "job-123",
        "status": JobStatus.RUNNING,
        "current_step": "cartographer",
        "progress": 0.12,
        "error": None,
    }
    with patch("src.orchestrator.server.get_job", return_value=fake_job):
        response = client.get("/jobs/job-123/status")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "running"
    assert data["progress"] == 30
    assert "Extracting" in data["step"]
