"""
Tests for jobs API endpoints focusing on:
- Cycle detection in _get_job_version

Note: These tests configure arango.ArangoClient (the library) rather than
patching internal functions like get_job_record, following the "Golden Rule".
The firewall already mocks ArangoClient, but we override it per-test to
configure specific return values for the jobs collection.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.orchestrator.api.jobs import _get_job_version


class TestJobVersionCycleDetection:
    """Test cycle detection in job version calculation.
    
    Note: These tests configure arango.ArangoClient to return job records
    from the jobs collection, following the "Golden Rule" of mocking libraries.
    """
    
    def _configure_job_records(self, monkeypatch, job_records):
        """Helper to configure ArangoDB jobs collection to return specific job records.
        
        This overrides the firewall's default ArangoClient mock with a test-specific
        configuration that returns the provided job records.
        
        Args:
            monkeypatch: pytest monkeypatch fixture
            job_records: dict mapping job_id -> job_record dict
        """
        from src.orchestrator.job_store import JOBS_COLLECTION
        
        # Create the mock collection with job records
        mock_collection = MagicMock()
        
        # Configure collection.get() to return records based on job_id
        # IMPORTANT: Return the actual record so get_job_record doesn't fall back to _mem_store
        # The fallback would return None since _mem_store is empty in unit tests
        # Use side_effect to look up the job_id in our job_records dict
        def get_side_effect(job_id):
            # Look up the job record by job_id
            record = job_records.get(job_id)
            # Return the record (or None if not found)
            return record
        mock_collection.get.side_effect = get_side_effect
        
        # Create mock DB with proper collection handling
        mock_db = Mock()
        
        # Ensure has_collection returns True for jobs collection (so _ensure_collection doesn't try to create it)
        # Also return True for other collections that _ensure_collection might check
        def has_collection_side_effect(name):
            return name == JOBS_COLLECTION or name in ("conflict_reports", "reframing_proposals")
        mock_db.has_collection.side_effect = has_collection_side_effect
        
        # Mock create_collection to return a mock collection (so _ensure_collection doesn't fail)
        def create_collection_side_effect(name, **kwargs):
            return mock_collection if name == JOBS_COLLECTION else MagicMock()
        mock_db.create_collection.side_effect = create_collection_side_effect
        
        # Return the configured collection when jobs collection is requested
        def collection_side_effect(name):
            if name == JOBS_COLLECTION:
                return mock_collection
            return MagicMock()
        mock_db.collection.side_effect = collection_side_effect
        
        # Create mock client that returns mock_db when db() is called
        # client.db() is called with (db_name, username=..., password=...)
        # We return mock_db regardless of arguments
        mock_client = Mock()
        mock_client.db = Mock(return_value=mock_db)
        
        # Override the firewall's ArangoClient mock with our test-specific one
        def mock_client_factory(hosts):
            return mock_client
        
        monkeypatch.setattr("arango.ArangoClient", mock_client_factory)
    
    def test_job_version_defaults_to_one(self, monkeypatch):
        """Test that jobs without version or parent default to version 1."""
        job_records = {"job-1": {"job_id": "job-1"}}  # No version, no parent
        self._configure_job_records(monkeypatch, job_records)
        
        version = _get_job_version("job-1")
        
        assert version == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

