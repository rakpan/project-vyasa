"""
Test that rigor_level is atomic at project creation and flows into job state.

Verifies:
1. Project creation with rigor_level="conservative" persists correctly
2. Workflow submission for that project includes rigor_level in initial_state
3. No flaky timing assertions, no LLM calls
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from flask import Flask

from src.orchestrator.server import app
from src.project.types import ProjectCreate, ProjectConfig
from src.project.service import ProjectService

# Ensure Flask app is in testing mode
app.config['TESTING'] = True


class TestRigorAtomicCreation:
    """Test rigor_level atomic creation and job state injection."""
    
    def _configure_project_collection(self, monkeypatch, project_record=None):
        """Helper to configure mocked ArangoDB projects collection."""
        from unittest.mock import Mock, MagicMock
        
        # Create mock collection
        mock_collection = MagicMock()
        if project_record:
            # For get operations
            mock_collection.get.return_value = project_record
            # For insert operations, return the inserted document
            def insert_side_effect(doc):
                # Return the document with _key set
                return doc
            mock_collection.insert.side_effect = insert_side_effect
        
        # Create mock DB
        mock_db = Mock()
        mock_db.has_collection.return_value = True
        mock_db.create_collection.return_value = mock_collection
        mock_db.collection.return_value = mock_collection
        
        # Create mock client
        mock_client = Mock()
        mock_client.db = Mock(return_value=mock_db)
        
        # Patch at library level (Golden Rule)
        def mock_client_factory(hosts):
            return mock_client
        
        monkeypatch.setattr("arango.ArangoClient", mock_client_factory)
        return mock_db, mock_collection
    
    def test_create_project_with_conservative_rigor(self, monkeypatch):
        """Test that project creation with rigor_level='conservative' persists correctly."""
        mock_db, mock_collection = self._configure_project_collection(monkeypatch)
        
        # Create project service
        project_service = ProjectService(mock_db)
        
        # Create project with conservative rigor
        project_create = ProjectCreate(
            title="Test Project",
            thesis="Test thesis",
            research_questions=["RQ1"],
            rigor_level="conservative",
        )
        
        project = project_service.create_project(project_create)
        
        # Verify rigor_level is set correctly
        assert project.rigor_level == "conservative"
        assert project.id is not None
        
        # Verify insert was called with correct rigor_level
        insert_calls = mock_collection.insert.call_args_list
        assert len(insert_calls) > 0
        inserted_doc = insert_calls[0][0][0]  # First call, first arg (doc dict)
        assert inserted_doc["rigor_level"] == "conservative"
    
    def test_workflow_submit_includes_rigor_in_initial_state(self, monkeypatch):
        """Test that workflow submission includes rigor_level in initial_state."""
        from src.orchestrator.state import ResearchState
        
        # Configure project collection with conservative project
        project_id = "test-project-123"
        project_record = {
            "_key": project_id,
            "title": "Test Project",
            "thesis": "Test thesis",
            "research_questions": ["RQ1"],
            "rigor_level": "conservative",
            "created_at": "2024-01-01T00:00:00Z",
            "seed_files": [],
        }
        mock_db, mock_collection = self._configure_project_collection(monkeypatch, project_record)
        
        # Mock job store to capture created jobs
        mock_job_store = {}
        job_id = "test-job-456"
        
        def mock_create_job(initial_state: ResearchState, idempotency_key=None):
            mock_job_store[job_id] = {
                "job_id": job_id,
                "initial_state": initial_state,
                "status": "QUEUED",
            }
            return job_id
        
        # Patch create_job at the module level
        monkeypatch.setattr("src.orchestrator.server.create_job", mock_create_job)
        
        # Mock project service
        project_service = ProjectService(mock_db)
        monkeypatch.setattr("src.orchestrator.server.get_project_service", lambda: project_service)
        
        # Mock ingestion store (for non-file workflows)
        mock_ingestion_store = MagicMock()
        mock_ingestion_record = MagicMock()
        mock_ingestion_record.ingestion_id = "test-ingestion-789"
        mock_ingestion_store.create_ingestion.return_value = mock_ingestion_record
        monkeypatch.setattr("src.orchestrator.server.IngestionStore", lambda db: mock_ingestion_store)
        
        # Submit workflow
        with app.test_client() as client:
            response = client.post(
                "/workflow/submit",
                json={
                    "project_id": project_id,
                    "raw_text": "Test content",
                },
                content_type="application/json",
            )
            
            assert response.status_code == 202
            data = response.get_json()
            assert "job_id" in data
            assert "ingestion_id" in data
            
            # Verify job was created with rigor_level in initial_state
            assert job_id in mock_job_store
            job_record = mock_job_store[job_id]
            initial_state = job_record["initial_state"]
            
            # Assert rigor_level is in initial_state
            assert "rigor_level" in initial_state
            assert initial_state["rigor_level"] == "conservative"
    
    def test_create_project_defaults_to_exploratory(self, monkeypatch):
        """Test that project creation defaults to 'exploratory' if rigor_level not provided."""
        mock_db, mock_collection = self._configure_project_collection(monkeypatch)
        
        project_service = ProjectService(mock_db)
        
        # Create project without rigor_level
        project_create = ProjectCreate(
            title="Test Project",
            thesis="Test thesis",
            research_questions=["RQ1"],
            # rigor_level not provided
        )
        
        project = project_service.create_project(project_create)
        
        # Verify defaults to exploratory
        assert project.rigor_level == "exploratory"
        
        # Verify insert was called with exploratory
        insert_calls = mock_collection.insert.call_args_list
        assert len(insert_calls) > 0
        inserted_doc = insert_calls[0][0][0]
        assert inserted_doc["rigor_level"] == "exploratory"
    
    def test_create_project_rejects_invalid_rigor(self, monkeypatch):
        """Test that project creation rejects invalid rigor_level values."""
        mock_db, mock_collection = self._configure_project_collection(monkeypatch)
        
        project_service = ProjectService(mock_db)
        
        # Try to create project with invalid rigor_level
        project_create = ProjectCreate(
            title="Test Project",
            thesis="Test thesis",
            research_questions=["RQ1"],
            rigor_level="invalid",  # Invalid value
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Invalid rigor_level"):
            project_service.create_project(project_create)

