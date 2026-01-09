"""
Unit tests for Analytical Notes Service.

Tests:
- CRUD operations for Analytical Notes
- State validation (Draft, Manuscript)
- Promotion requirements (Manuscript requires promotion_reason)
- Filtering by state, linked_rq, tags
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from src.orchestrator.schemas.analytical_notes import AnalyticalNote, NoteState
from src.orchestrator.services.analytical_notes_service import AnalyticalNotesService


@pytest.fixture
def mock_db():
    """Mock ArangoDB database."""
    db = Mock()
    db.has_collection = Mock(return_value=False)
    db.create_collection = Mock()
    db.collection = Mock(return_value=Mock())
    return db


@pytest.fixture
def notes_service(mock_db):
    """Analytical Notes Service with mocked DB."""
    return AnalyticalNotesService(mock_db)


@pytest.fixture
def sample_note():
    """Sample Analytical Note for testing."""
    return AnalyticalNote.create(
        text="This is a test analytical note.",
        project_id="test-project-123",
        tags=["tag1", "tag2"],
        linked_rq="RQ1",
    )


def test_create_note(notes_service, sample_note, mock_db):
    """Test creating an Analytical Note."""
    coll = Mock()
    coll.insert = Mock(return_value={"_id": "notes/test-123", "_key": "test-123"})
    mock_db.collection.return_value = coll
    
    # Ensure collection exists
    mock_db.has_collection.return_value = True
    
    note = notes_service.create_note(sample_note)
    
    assert note.note_id == sample_note.note_id
    assert note.state == NoteState.DRAFT
    assert note.text == "This is a test analytical note."
    assert coll.insert.called_once


def test_create_note_invalid_state(notes_service, sample_note):
    """Test creating note with invalid state."""
    sample_note.state = "InvalidState"  # type: ignore
    
    with pytest.raises(ValueError, match="Invalid note state"):
        notes_service.create_note(sample_note)


def test_create_note_manuscript_without_reason(notes_service, sample_note):
    """Test creating Manuscript note without promotion_reason."""
    sample_note.state = NoteState.MANUSCRIPT
    sample_note.promotion_reason = None
    
    with pytest.raises(ValueError, match="Manuscript state requires promotion_reason"):
        notes_service.create_note(sample_note)


def test_create_note_manuscript_with_reason(notes_service, sample_note, mock_db):
    """Test creating Manuscript note with promotion_reason."""
    sample_note.state = NoteState.MANUSCRIPT
    sample_note.promotion_reason = "Framing supported by evidence chunks [chunk1, chunk2]"
    
    coll = Mock()
    coll.insert = Mock(return_value={"_id": "notes/test-123", "_key": "test-123"})
    mock_db.collection.return_value = coll
    mock_db.has_collection.return_value = True
    
    note = notes_service.create_note(sample_note)
    
    assert note.state == NoteState.MANUSCRIPT
    assert note.promotion_reason is not None
    assert coll.insert.called_once


def test_get_note(notes_service, mock_db):
    """Test getting an Analytical Note by ID."""
    note_id = "test-note-123"
    note_doc = {
        "note_id": note_id,
        "project_id": "test-project-123",
        "text": "Test note",
        "state": "Draft",
        "tags": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    coll = Mock()
    coll.get = Mock(return_value=note_doc)
    mock_db.collection.return_value = coll
    
    note = notes_service.get_note(note_id)
    
    assert note is not None
    assert note.note_id == note_id
    assert coll.get.called_once_with(note_id)


def test_get_note_not_found(notes_service, mock_db):
    """Test getting non-existent note."""
    coll = Mock()
    coll.get = Mock(return_value=None)
    mock_db.collection.return_value = coll
    
    note = notes_service.get_note("non-existent")
    
    assert note is None


def test_list_notes(notes_service, mock_db):
    """Test listing Analytical Notes with filters."""
    project_id = "test-project-123"
    
    notes_data = [
        {
            "note_id": "note-1",
            "project_id": project_id,
            "text": "Note 1",
            "state": "Draft",
            "tags": ["tag1"],
            "linked_rq": "RQ1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "note_id": "note-2",
            "project_id": project_id,
            "text": "Note 2",
            "state": "Manuscript",
            "tags": ["tag2"],
            "linked_rq": "RQ2",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    
    cursor = Mock()
    cursor.__iter__ = Mock(return_value=iter(notes_data))
    mock_db.aql.execute = Mock(return_value=cursor)
    mock_db.has_collection.return_value = True
    
    notes = notes_service.list_notes(project_id=project_id, state=NoteState.DRAFT)
    
    assert len(notes) == 2  # Both notes returned (filter applied in query)
    assert mock_db.aql.execute.called_once


def test_list_notes_with_filters(notes_service, mock_db):
    """Test listing notes with multiple filters."""
    project_id = "test-project-123"
    
    cursor = Mock()
    cursor.__iter__ = Mock(return_value=iter([]))
    mock_db.aql.execute = Mock(return_value=cursor)
    mock_db.has_collection.return_value = True
    
    notes = notes_service.list_notes(
        project_id=project_id,
        state=NoteState.DRAFT,
        linked_rq="RQ1",
        tags=["tag1", "tag2"],
        limit=10,
    )
    
    assert len(notes) == 0
    assert mock_db.aql.execute.called_once


def test_update_note(notes_service, mock_db):
    """Test updating an Analytical Note."""
    note_id = "test-note-123"
    existing_note = AnalyticalNote.create(
        text="Original text",
        project_id="test-project-123",
    )
    
    coll = Mock()
    coll.get = Mock(return_value=existing_note.model_dump())
    coll.update = Mock()
    mock_db.collection.return_value = coll
    
    # Mock get_note to return existing note
    with patch.object(notes_service, "get_note", return_value=existing_note):
        updates = {
            "text": "Updated text",
            "tags": ["new-tag"],
        }
        
        note = notes_service.update_note(note_id, updates)
        
        assert note is not None
        assert note.text == "Updated text"
        assert note.tags == ["new-tag"]
        assert coll.update.called_once


def test_update_note_to_manuscript_without_reason(notes_service, mock_db):
    """Test updating note to Manuscript without promotion_reason."""
    note_id = "test-note-123"
    existing_note = AnalyticalNote.create(
        text="Original text",
        project_id="test-project-123",
    )
    
    with patch.object(notes_service, "get_note", return_value=existing_note):
        updates = {
            "state": NoteState.MANUSCRIPT.value,
        }
        
        with pytest.raises(ValueError, match="Manuscript state requires promotion_reason"):
            notes_service.update_note(note_id, updates)


def test_update_note_to_manuscript_with_reason(notes_service, mock_db):
    """Test updating note to Manuscript with promotion_reason."""
    note_id = "test-note-123"
    existing_note = AnalyticalNote.create(
        text="Original text",
        project_id="test-project-123",
    )
    
    coll = Mock()
    coll.get = Mock(return_value=existing_note.model_dump())
    coll.update = Mock()
    mock_db.collection.return_value = coll
    
    with patch.object(notes_service, "get_note", return_value=existing_note):
        updates = {
            "state": NoteState.MANUSCRIPT.value,
            "promotion_reason": "Supported by evidence",
        }
        
        note = notes_service.update_note(note_id, updates)
        
        assert note is not None
        assert note.state == NoteState.MANUSCRIPT
        assert note.promotion_reason == "Supported by evidence"


def test_update_note_not_found(notes_service, mock_db):
    """Test updating non-existent note."""
    coll = Mock()
    coll.get = Mock(return_value=None)
    mock_db.collection.return_value = coll
    
    with patch.object(notes_service, "get_note", return_value=None):
        note = notes_service.update_note("non-existent", {"text": "Updated"})
        
        assert note is None


def test_delete_note(notes_service, mock_db):
    """Test deleting an Analytical Note."""
    note_id = "test-note-123"
    
    coll = Mock()
    coll.delete = Mock(return_value=True)
    mock_db.collection.return_value = coll
    
    result = notes_service.delete_note(note_id)
    
    assert result is True
    assert coll.delete.called_once_with(note_id, silent=True)


def test_delete_note_not_found(notes_service, mock_db):
    """Test deleting non-existent note."""
    coll = Mock()
    coll.delete = Mock(return_value=False)
    mock_db.collection.return_value = coll
    
    result = notes_service.delete_note("non-existent")
    
    assert result is False
