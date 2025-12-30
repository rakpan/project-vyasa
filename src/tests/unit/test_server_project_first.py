"""
Unit tests for Project-First async orchestrator invariants.

What's covered:
- /workflow/submit (JSON): Missing project_id -> 400, Project not found -> 404, DB unavailable -> 503
- /workflow/submit (multipart): File upload with project_id, seed_file update, project_context injection
- Initial state validation: project_id and project_context are correctly injected
- Job creation: job_id returned, status is QUEUED, async thread started

All external dependencies are mocked (ArangoDB, workflow, job_manager, process_pdf).
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
import pytest

from src.orchestrator.server import app
from src.project.types import ProjectConfig, ProjectCreate
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
def mock_job_manager():
    """Mock job manager functions."""
    with patch('src.orchestrator.server.create_job', return_value="job-123") as mock_create, \
         patch('src.orchestrator.server.update_job_status') as mock_update, \
         patch('src.orchestrator.server.set_job_result') as mock_set_result, \
         patch('src.orchestrator.server.acquire_job_slot', return_value=True) as mock_acquire, \
         patch('src.orchestrator.server.release_job_slot') as mock_release:
        yield {
            'create_job': mock_create,
            'update_job_status': mock_update,
            'set_job_result': mock_set_result,
            'acquire_job_slot': mock_acquire,
            'release_job_slot': mock_release,
        }


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


@pytest.fixture
def mock_thread():
    """Mock threading.Thread to prevent actual thread creation."""
    with patch('src.orchestrator.server.threading.Thread') as mock_thread_class:
        mock_thread_instance = Mock()
        mock_thread_class.return_value = mock_thread_instance
        yield mock_thread_instance


# ============================================
# A) /workflow/submit (JSON) Tests
# ============================================

def test_workflow_submit_json_missing_project_id(client):
    """A1: Missing project_id -> 400."""
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


def test_workflow_submit_json_project_not_found(client, mock_project_service):
    """A2: Project not found -> 404."""
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
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data
        assert "not found" in data["error"].lower()


def test_workflow_submit_json_db_unavailable(client):
    """A3: DB unavailable (ProjectService None) -> 503."""
    with patch('src.orchestrator.server.get_project_service', return_value=None):
        response = client.post(
            '/workflow/submit',
            json={
                "raw_text": "Test document text",
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
            },
            content_type='application/json',
        )
        
        assert response.status_code == 503
        data = json.loads(response.data)
        assert "error" in data
        assert "unavailable" in data["error"].lower()


def test_workflow_submit_json_success_with_project_context(
    client, mock_project_service, mock_job_manager, mock_thread
):
    """A4: Valid project_id -> 202, returns job_id, initial_state includes project_id and project_context."""
    project_id = "550e8400-e29b-41d4-a716-446655440000"
    
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        with patch('src.orchestrator.server._run_workflow_async') as mock_async:
            response = client.post(
                '/workflow/submit',
                json={
                    "raw_text": "Test document text",
                    "project_id": project_id,
                },
                content_type='application/json',
            )
            
            # Verify response
            assert response.status_code == 202
            data = json.loads(response.data)
            assert "job_id" in data
            assert data["job_id"] == "job-123"
            assert data["status"] == JobStatus.QUEUED.value
            
            # Verify async function was called with correct initial_state
            mock_async.assert_called_once()
            call_args = mock_async.call_args
            initial_state = call_args[0][1]  # Second positional arg
            
            assert initial_state["project_id"] == project_id
            assert "project_context" in initial_state
            assert initial_state["project_context"]["title"] == "Test Project"
            assert initial_state["project_context"]["thesis"] == "Test thesis statement"
            assert initial_state["project_context"]["research_questions"] == ["RQ1: What is the question?"]
            
            # Verify ProjectService was called
            mock_project_service.get_project.assert_called_once_with(project_id)
            
            # Verify job was created
            mock_job_manager['create_job'].assert_called_once()
            
            # Verify thread was started
            mock_thread.start.assert_called_once()


# ============================================
# B) /workflow/submit (multipart) Tests
# ============================================

def test_workflow_submit_multipart_missing_project_id(client):
    """B1: Missing project_id -> 400."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_file.write(b'%PDF-1.4 fake pdf content')
        tmp_path = tmp_file.name
    
    try:
        with open(tmp_path, 'rb') as f:
            response = client.post(
                '/workflow/submit',
                data={
                    'file': (f, 'test.pdf'),
                },
                content_type='multipart/form-data',
            )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "project_id" in data["error"].lower()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_workflow_submit_multipart_project_not_found(client, mock_project_service):
    """B2: Project not found -> 404."""
    mock_project_service.get_project.side_effect = ValueError("Project not found: invalid-id")
    
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_file.write(b'%PDF-1.4 fake pdf content')
        tmp_path = tmp_file.name
    
    try:
        with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
            with open(tmp_path, 'rb') as f:
                response = client.post(
                    '/workflow/submit',
                    data={
                        'file': (f, 'test.pdf'),
                        'project_id': 'invalid-id',
                    },
                    content_type='multipart/form-data',
                )
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert "error" in data
            assert "not found" in data["error"].lower()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_workflow_submit_multipart_success_calls_add_seed_file(
    client, mock_project_service, mock_job_manager, mock_thread
):
    """B3: On success, must call project_service.add_seed_file(project_id, filename)."""
    project_id = "550e8400-e29b-41d4-a716-446655440000"
    filename = "test.pdf"
    
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_file.write(b'%PDF-1.4 fake pdf content')
        tmp_path = tmp_file.name
    
    try:
        with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
            with patch('src.orchestrator.server.process_pdf') as mock_process_pdf:
                mock_process_pdf.return_value = (
                    "# Test Markdown",
                    "/tmp/images",
                    ["/tmp/images/img1.png"],
                )
                
                with patch('src.orchestrator.server._run_workflow_async') as mock_async:
                    with open(tmp_path, 'rb') as f:
                        response = client.post(
                            '/workflow/submit',
                            data={
                                'file': (f, filename),
                                'project_id': project_id,
                            },
                            content_type='multipart/form-data',
                        )
                    
                    # Verify response
                    assert response.status_code == 202
                    data = json.loads(response.data)
                    assert "job_id" in data
                    
                    # Verify add_seed_file was called
                    mock_project_service.add_seed_file.assert_called_once_with(
                        project_id,
                        filename
                    )
                    
                    # Verify get_project was called
                    mock_project_service.get_project.assert_called_once_with(project_id)
                    
                    # Verify process_pdf was called
                    mock_process_pdf.assert_called_once()
                    
                    # Verify initial_state includes extracted data
                    call_args = mock_async.call_args
                    initial_state = call_args[0][1]
                    assert initial_state["raw_text"] == "# Test Markdown"
                    assert initial_state["image_paths"] == ["/tmp/images/img1.png"]
                    assert initial_state["project_id"] == project_id
                    assert "project_context" in initial_state
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_workflow_submit_multipart_success_initial_state(
    client, mock_project_service, mock_job_manager, mock_thread
):
    """B4: On success, initial_state includes raw_text, image_paths, project_id, project_context."""
    project_id = "550e8400-e29b-41d4-a716-446655440000"
    filename = "test.pdf"
    markdown_text = "# Test Markdown\n\nThis is test content."
    image_paths = ["/tmp/images/img1.png", "/tmp/images/img2.png"]
    
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_file.write(b'%PDF-1.4 fake pdf content')
        tmp_path = tmp_file.name
    
    try:
        with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
            with patch('src.orchestrator.server.process_pdf') as mock_process_pdf:
                mock_process_pdf.return_value = (
                    markdown_text,
                    "/tmp/images",
                    image_paths,
                )
                
                with patch('src.orchestrator.server._run_workflow_async') as mock_async:
                    with open(tmp_path, 'rb') as f:
                        response = client.post(
                            '/workflow/submit',
                            data={
                                'file': (f, filename),
                                'project_id': project_id,
                            },
                            content_type='multipart/form-data',
                        )
                    
                    assert response.status_code == 202
                    
                    # Verify initial_state structure
                    call_args = mock_async.call_args
                    initial_state = call_args[0][1]
                    
                    assert initial_state["raw_text"] == markdown_text
                    assert initial_state["image_paths"] == image_paths
                    assert initial_state["project_id"] == project_id
                    assert "project_context" in initial_state
                    assert initial_state["project_context"]["title"] == "Test Project"
                    assert initial_state["pdf_path"] == filename
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_workflow_submit_multipart_invalid_file_format(client, mock_project_service):
    """Multipart with non-PDF file -> 400."""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
        tmp_file.write(b'Not a PDF')
        tmp_path = tmp_file.name
    
    try:
        with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
            with open(tmp_path, 'rb') as f:
                response = client.post(
                    '/workflow/submit',
                    data={
                        'file': (f, 'test.txt'),
                        'project_id': '550e8400-e29b-41d4-a716-446655440000',
                    },
                    content_type='multipart/form-data',
                )
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert "error" in data
            assert "pdf" in data["error"].lower()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_workflow_submit_multipart_missing_file(client, mock_project_service):
    """Multipart without file -> 400 (raw_text required)."""
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        response = client.post(
            '/workflow/submit',
            data={
                'project_id': '550e8400-e29b-41d4-a716-446655440000',
            },
            content_type='multipart/form-data',
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "raw_text" in data["error"].lower()

