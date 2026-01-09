"""
Unit tests for Analytical Notes API endpoints.

Tests:
- GET /api/projects/:project_id/notes (list notes)
- POST /api/projects/:project_id/notes (create note)
- GET /api/notes/:note_id (get note)
- PATCH /api/notes/:note_id (update note)
- DELETE /api/notes/:note_id (delete note)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

from src.orchestrator.api.notes import notes_bp, _get_notes_service
from src.orchestrator.services.analytical_notes_service import AnalyticalNotesService
from src.orchestrator.schemas.analytical_notes import AnalyticalNote, NoteState


@pytest.fixture
def app():
    """Flask test app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(notes_bp)
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def mock_notes_service():
    """Mock AnalyticalNotesService."""
    service = Mock(spec=AnalyticalNotesService)
    return service


def test_list_notes_success(client, mock_notes_service):
    """Test listing notes successfully."""
    project_id = "test-project-123"
    
    notes = [
        AnalyticalNote.create(
            text="Note 1",
            project_id=project_id,
            state=NoteState.DRAFT,
        ),
        AnalyticalNote.create(
            text="Note 2",
            project_id=project_id,
            state=NoteState.MANUSCRIPT,
            promotion_reason="Supported by evidence",
        ),
    ]
    mock_notes_service.list_notes.return_value = notes
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.get(f'/api/projects/{project_id}/notes')
    
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2
    assert data[0]["text"] == "Note 1"
    assert data[1]["text"] == "Note 2"
    mock_notes_service.list_notes.assert_called_once()


def test_list_notes_with_filters(client, mock_notes_service):
    """Test listing notes with query parameters."""
    project_id = "test-project-123"
    
    notes = [
        AnalyticalNote.create(
            text="Note 1",
            project_id=project_id,
            state=NoteState.DRAFT,
            linked_rq="RQ1",
            tags=["tag1"],
        ),
    ]
    mock_notes_service.list_notes.return_value = notes
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.get(
            f'/api/projects/{project_id}/notes',
            query_string={
                "state": "Draft",
                "linked_rq": "RQ1",
                "tags": "tag1,tag2",
                "limit": "10",
            }
        )
    
    assert response.status_code == 200
    mock_notes_service.list_notes.assert_called_once()
    call_kwargs = mock_notes_service.list_notes.call_args[1]
    assert call_kwargs["state"] == NoteState.DRAFT
    assert call_kwargs["linked_rq"] == "RQ1"
    assert call_kwargs["tags"] == ["tag1", "tag2"]
    assert call_kwargs["limit"] == 10


def test_list_notes_invalid_state(client, mock_notes_service):
    """Test listing notes with invalid state."""
    project_id = "test-project-123"
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.get(
            f'/api/projects/{project_id}/notes',
            query_string={"state": "InvalidState"}
        )
    
    assert response.status_code == 400
    data = response.get_json()
    assert "Invalid state" in data["error"]


def test_create_note_success(client, mock_notes_service):
    """Test creating a note successfully."""
    project_id = "test-project-123"
    
    note = AnalyticalNote.create(
        text="New note",
        project_id=project_id,
    )
    mock_notes_service.create_note.return_value = note
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.post(
            f'/api/projects/{project_id}/notes',
            json={
                "text": "New note",
                "tags": ["tag1"],
                "linked_rq": "RQ1",
            }
        )
    
    assert response.status_code == 201
    data = response.get_json()
    assert data["text"] == "New note"
    assert data["state"] == "Draft"
    mock_notes_service.create_note.assert_called_once()


def test_create_note_empty_text(client, mock_notes_service):
    """Test creating note with empty text."""
    project_id = "test-project-123"
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.post(
            f'/api/projects/{project_id}/notes',
            json={"text": ""}
        )
    
    assert response.status_code == 400
    data = response.get_json()
    assert "text is required" in data["error"].lower()


def test_create_note_manuscript_without_reason(client, mock_notes_service):
    """Test creating Manuscript note without promotion_reason."""
    project_id = "test-project-123"
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.post(
            f'/api/projects/{project_id}/notes',
            json={
                "text": "New note",
                "state": "Manuscript",
            }
        )
    
    assert response.status_code == 400
    data = response.get_json()
    assert "promotion_reason" in data["error"].lower()


def test_get_note_success(client, mock_notes_service):
    """Test getting a note successfully."""
    note_id = "test-note-123"
    
    note = AnalyticalNote.create(
        text="Test note",
        project_id="test-project-123",
    )
    mock_notes_service.get_note.return_value = note
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.get(f'/api/notes/{note_id}')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["note_id"] == note_id
    mock_notes_service.get_note.assert_called_once_with(note_id)


def test_get_note_not_found(client, mock_notes_service):
    """Test getting non-existent note."""
    note_id = "non-existent"
    
    mock_notes_service.get_note.return_value = None
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.get(f'/api/notes/{note_id}')
    
    assert response.status_code == 404
    data = response.get_json()
    assert "not found" in data["error"].lower()


def test_update_note_success(client, mock_notes_service):
    """Test updating a note successfully."""
    note_id = "test-note-123"
    
    existing_note = AnalyticalNote.create(
        text="Original text",
        project_id="test-project-123",
    )
    
    updated_note = AnalyticalNote.create(
        text="Updated text",
        project_id="test-project-123",
        tags=["new-tag"],
    )
    
    mock_notes_service.get_note.return_value = existing_note
    mock_notes_service.update_note.return_value = updated_note
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.patch(
            f'/api/notes/{note_id}',
            json={
                "text": "Updated text",
                "tags": ["new-tag"],
            }
        )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["text"] == "Updated text"
    mock_notes_service.update_note.assert_called_once()


def test_update_note_to_manuscript_without_reason(client, mock_notes_service):
    """Test updating note to Manuscript without promotion_reason."""
    note_id = "test-note-123"
    
    existing_note = AnalyticalNote.create(
        text="Original text",
        project_id="test-project-123",
    )
    
    mock_notes_service.get_note.return_value = existing_note
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.patch(
            f'/api/notes/{note_id}',
            json={"state": "Manuscript"}
        )
    
    assert response.status_code == 400
    data = response.get_json()
    assert "promotion_reason" in data["error"].lower()


def test_update_note_not_found(client, mock_notes_service):
    """Test updating non-existent note."""
    note_id = "non-existent"
    
    mock_notes_service.get_note.return_value = None
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.patch(
            f'/api/notes/{note_id}',
            json={"text": "Updated text"}
        )
    
    assert response.status_code == 404
    data = response.get_json()
    assert "not found" in data["error"].lower()


def test_delete_note_success(client, mock_notes_service):
    """Test deleting a note successfully."""
    note_id = "test-note-123"
    
    mock_notes_service.delete_note.return_value = True
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.delete(f'/api/notes/{note_id}')
    
    assert response.status_code == 204
    mock_notes_service.delete_note.assert_called_once_with(note_id)


def test_delete_note_not_found(client, mock_notes_service):
    """Test deleting non-existent note."""
    note_id = "non-existent"
    
    mock_notes_service.delete_note.return_value = False
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=mock_notes_service):
        response = client.delete(f'/api/notes/{note_id}')
    
    assert response.status_code == 404
    data = response.get_json()
    assert "not found" in data["error"].lower()


def test_list_notes_db_unavailable(client):
    """Test listing notes when DB is unavailable."""
    project_id = "test-project-123"
    
    with patch('src.orchestrator.api.notes._get_notes_service', return_value=None):
        response = client.get(f'/api/projects/{project_id}/notes')
    
    assert response.status_code == 503
    data = response.get_json()
    assert "unavailable" in data["error"].lower()
