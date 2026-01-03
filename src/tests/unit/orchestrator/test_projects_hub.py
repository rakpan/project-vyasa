"""
Tests for Project Hub backend contract.

Verifies:
1. list_projects_hub always returns required fields with defaults
2. Status is derived server-side (not frontend heuristics)
3. Tags default to empty array
4. manifest_summary is either null or has stable shape
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from flask import Flask

from src.orchestrator.server import app
from src.project.service import ProjectService
from src.project.hub_types import ProjectHubSummary, ManifestSummary, ProjectGrouping

# Ensure Flask app is in testing mode
app.config['TESTING'] = True


class TestProjectsHubContract:
    """Test that list_projects_hub guarantees required fields."""
    
    def _configure_project_collection(self, monkeypatch, projects):
        """Helper to configure mocked ArangoDB projects collection."""
        from unittest.mock import Mock, MagicMock
        
        # Create mock collection
        mock_collection = MagicMock()
        
        # Create mock DB
        mock_db = Mock()
        mock_db.has_collection.return_value = True
        mock_db.create_collection.return_value = mock_collection
        
        # Mock AQL execute to return projects
        def aql_execute_side_effect(query, bind_vars=None):
            # Return projects as cursor
            mock_cursor = Mock()
            mock_cursor.__iter__ = Mock(return_value=iter(projects))
            return mock_cursor
        
        mock_db.aql.execute.side_effect = aql_execute_side_effect
        mock_db.collection.return_value = mock_collection
        
        # Create mock client
        mock_client = Mock()
        mock_client.db = Mock(return_value=mock_db)
        
        # Patch at library level (Golden Rule)
        def mock_client_factory(hosts):
            return mock_client
        
        monkeypatch.setattr("arango.ArangoClient", mock_client_factory)
        return mock_db, mock_collection
    
    def test_list_projects_hub_guarantees_required_fields(self, monkeypatch):
        """Test that all projects have required fields with defaults."""
        projects = [
            {
                "_key": "project-1",
                "title": "Test Project 1",
                "tags": ["security"],  # Has tags
                "rigor_level": "conservative",
                "created_at": "2024-01-01T00:00:00Z",
            },
            {
                "_key": "project-2",
                "title": "Test Project 2",
                # No tags field (should default to [])
                "rigor_level": "exploratory",
                "created_at": "2024-01-02T00:00:00Z",
            },
        ]
        
        mock_db, mock_collection = self._configure_project_collection(monkeypatch, projects)
        
        # Mock job store methods
        def mock_list_jobs_by_project(project_id, limit=1):
            return []  # No jobs
        
        monkeypatch.setattr("src.orchestrator.job_store.list_jobs_by_project", mock_list_jobs_by_project)
        
        project_service = ProjectService(mock_db)
        grouping = project_service.list_projects_hub()
        
        # Verify all projects have required fields
        all_projects = grouping.active_research + grouping.archived_insights
        
        for project in all_projects:
            # Required fields must exist
            assert hasattr(project, "project_id")
            assert hasattr(project, "title")
            assert hasattr(project, "tags")
            assert hasattr(project, "rigor_level")
            assert hasattr(project, "last_updated")
            assert hasattr(project, "status")
            assert hasattr(project, "open_flags_count")
            assert hasattr(project, "manifest_summary")
            
            # Tags must be a list (default empty)
            assert isinstance(project.tags, list)
            
            # Status must be one of the allowed values
            assert project.status in ("Idle", "Processing", "AttentionNeeded")
            
            # rigor_level must be valid
            assert project.rigor_level in ("exploratory", "conservative")
            
            # open_flags_count must be an integer
            assert isinstance(project.open_flags_count, int)
            assert project.open_flags_count >= 0
    
    def test_list_projects_hub_tags_default_to_empty(self, monkeypatch):
        """Test that projects without tags field get empty array."""
        projects = [
            {
                "_key": "project-1",
                "title": "Test Project",
                # No tags field
                "rigor_level": "exploratory",
                "created_at": "2024-01-01T00:00:00Z",
            },
        ]
        
        mock_db, mock_collection = self._configure_project_collection(monkeypatch, projects)
        
        def mock_list_jobs_by_project(project_id, limit=1):
            return []
        
        monkeypatch.setattr("src.orchestrator.job_store.list_jobs_by_project", mock_list_jobs_by_project)
        
        project_service = ProjectService(mock_db)
        grouping = project_service.list_projects_hub()
        
        all_projects = grouping.active_research + grouping.archived_insights
        assert len(all_projects) > 0
        
        # Verify tags is empty array (not None, not undefined)
        project = all_projects[0]
        assert isinstance(project.tags, list)
        assert len(project.tags) == 0
    
    def test_list_projects_hub_status_derived_server_side(self, monkeypatch):
        """Test that status is derived server-side, not frontend heuristics."""
        projects = [
            {
                "_key": "project-1",
                "title": "Test Project",
                "tags": [],
                "rigor_level": "exploratory",
                "created_at": "2024-01-01T00:00:00Z",
            },
        ]
        
        mock_db, mock_collection = self._configure_project_collection(monkeypatch, projects)
        
        # Mock job with QUEUED status -> should be "Processing"
        def mock_list_jobs_by_project(project_id, limit=1):
            return [{
                "job_id": "job-1",
                "status": "QUEUED",
                "created_at": "2024-01-02T00:00:00Z",
            }]
        
        monkeypatch.setattr("src.project.service.list_jobs_by_project", mock_list_jobs_by_project)
        
        # Mock get_job_record to return job record
        def mock_get_job_record(job_id):
            return {
                "job_id": job_id,
                "status": "QUEUED",
            }
        
        from src.orchestrator.job_store import get_job_record
        monkeypatch.setattr("src.orchestrator.job_store.get_job_record", mock_get_job_record)
        
        project_service = ProjectService(mock_db)
        grouping = project_service.list_projects_hub()
        
        all_projects = grouping.active_research + grouping.archived_insights
        assert len(all_projects) > 0
        
        # Verify status is derived server-side
        project = all_projects[0]
        assert project.status == "Processing"  # Derived from QUEUED job
    
    def test_list_projects_hub_manifest_summary_stable_shape(self, monkeypatch):
        """Test that manifest_summary is either null or has stable shape."""
        projects = [
            {
                "_key": "project-1",
                "title": "Test Project",
                "tags": [],
                "rigor_level": "exploratory",
                "created_at": "2024-01-01T00:00:00Z",
            },
        ]
        
        mock_db, mock_collection = self._configure_project_collection(monkeypatch, projects)
        
        # Mock job with SUCCEEDED status and manifest
        def mock_list_jobs_by_project(project_id, limit=1):
            return [{
                "job_id": "job-1",
                "status": "SUCCEEDED",
                "created_at": "2024-01-02T00:00:00Z",
            }]
        
        monkeypatch.setattr("src.project.service.list_jobs_by_project", mock_list_jobs_by_project)
        
        # Mock get_job_record to return job with manifest
        def mock_get_job_record(job_id):
            return {
                "job_id": job_id,
                "status": "SUCCEEDED",
                "result": {
                    "artifact_manifest": {
                        "metrics": {
                            "total_words": 5000,
                            "total_claims": 150,
                            "claims_per_100_words": 3.0,
                            "citation_count": 25,
                        },
                        "totals": {
                            "words": 5000,
                            "tables": 3,
                            "figures": 2,
                            "citations": 25,
                        },
                        "blocks": [],
                        "tables": [],
                        "figures": [],
                    }
                }
            }
        
        from src.orchestrator.job_store import get_job_record
        monkeypatch.setattr("src.orchestrator.job_store.get_job_record", mock_get_job_record)
        
        project_service = ProjectService(mock_db)
        grouping = project_service.list_projects_hub(include_manifest=True)
        
        all_projects = grouping.active_research + grouping.archived_insights
        assert len(all_projects) > 0
        
        project = all_projects[0]
        
        # manifest_summary should be either None or ManifestSummary with stable shape
        if project.manifest_summary is not None:
            manifest = project.manifest_summary
            # Verify stable shape
            assert hasattr(manifest, "words")
            assert hasattr(manifest, "claims")
            assert hasattr(manifest, "density")
            assert hasattr(manifest, "citations")
            assert hasattr(manifest, "tables")
            assert hasattr(manifest, "figures")
            assert hasattr(manifest, "flags_count_by_type")
            
            # Verify types
            assert isinstance(manifest.words, int)
            assert isinstance(manifest.claims, int)
            assert isinstance(manifest.density, (int, float))
            assert isinstance(manifest.citations, int)
            assert isinstance(manifest.tables, int)
            assert isinstance(manifest.figures, int)
            assert isinstance(manifest.flags_count_by_type, dict)
    
    def test_list_projects_hub_filters_by_status(self, monkeypatch):
        """Test that status filter works correctly."""
        projects = [
            {
                "_key": "project-1",
                "title": "Test Project 1",
                "tags": [],
                "rigor_level": "exploratory",
                "created_at": "2024-01-01T00:00:00Z",
            },
            {
                "_key": "project-2",
                "title": "Test Project 2",
                "tags": [],
                "rigor_level": "exploratory",
                "created_at": "2024-01-02T00:00:00Z",
            },
        ]
        
        mock_db, mock_collection = self._configure_project_collection(monkeypatch, projects)
        
        # Mock jobs: first project has QUEUED (Processing), second has no jobs (Idle)
        call_count = [0]
        def mock_list_jobs_by_project(project_id, limit=1):
            call_count[0] += 1
            if call_count[0] == 1:  # First project
                return [{"job_id": "job-1", "status": "QUEUED", "created_at": "2024-01-02T00:00:00Z"}]
            return []  # Second project
        
        monkeypatch.setattr("src.project.service.list_jobs_by_project", mock_list_jobs_by_project)
        
        def mock_get_job_record(job_id):
            return {"job_id": job_id, "status": "QUEUED"}
        
        from src.orchestrator.job_store import get_job_record
        monkeypatch.setattr("src.orchestrator.job_store.get_job_record", mock_get_job_record)
        
        project_service = ProjectService(mock_db)
        
        # Filter by Processing
        grouping_processing = project_service.list_projects_hub(status="Processing")
        all_processing = grouping_processing.active_research + grouping_processing.archived_insights
        assert len(all_processing) == 1
        assert all_processing[0].status == "Processing"
        
        # Filter by Idle
        call_count[0] = 0  # Reset counter
        grouping_idle = project_service.list_projects_hub(status="Idle")
        all_idle = grouping_idle.active_research + grouping_idle.archived_insights
        assert len(all_idle) == 1
        assert all_idle[0].status == "Idle"

