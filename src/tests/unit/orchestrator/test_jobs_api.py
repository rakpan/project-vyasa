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
        def get_side_effect(job_id):
            return job_records.get(job_id)  # Returns None if not found, but our test job_ids should all be present
        mock_collection.get.side_effect = get_side_effect
        
        # Create mock DB with proper collection handling
        mock_db = Mock()
        
        # Ensure has_collection returns True for jobs collection (so _ensure_collection doesn't try to create it)
        def has_collection_side_effect(name):
            return name == JOBS_COLLECTION
        mock_db.has_collection.side_effect = has_collection_side_effect
        
        # Mock create_collection to do nothing (so _ensure_collection doesn't fail)
        mock_db.create_collection = Mock(return_value=None)
        
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
    
    def test_job_version_without_cycle(self, monkeypatch):
        """Test normal job version calculation without cycles.
        
        This test verifies that _get_job_version correctly calculates job versions
        by traversing the parent_job_id chain. The mock ensures get_job_record()
        returns the test job records without falling back to _mem_store.
        """
        # Setup job chain: job1 -> job2 -> job3
        job_records = {
            "job-1": {"job_id": "job-1", "job_version": 1},  # Original job
            "job-2": {"job_id": "job-2", "parent_job_id": "job-1"},  # Reprocessed job
            "job-3": {"job_id": "job-3", "parent_job_id": "job-2"},  # Reprocessed again
        }
        # Configure mocks BEFORE calling the function
        # This overrides the firewall's default ArangoClient mock
        self._configure_job_records(monkeypatch, job_records)
        
        # Verify the mock is working by checking get_job_record directly
        from src.orchestrator.job_store import get_job_record
        test_record = get_job_record("job-1")
        assert test_record is not None, "Mock should return job record, not None"
        assert test_record.get("job_version") == 1, f"Expected job_version=1, got {test_record}"
        
        # Test version calculation
        # Each call to _get_job_version will call get_job_record, which calls _get_db()
        # The mock should handle this correctly
        version1 = _get_job_version("job-1")
        assert version1 == 1, f"Expected version 1 for job-1, got {version1}"
        
        version2 = _get_job_version("job-2")
        assert version2 == 2, f"Expected version 2 for job-2, got {version2}. Job record: {job_records.get('job-2')}"
        
        version3 = _get_job_version("job-3")
        assert version3 == 3, f"Expected version 3 for job-3, got {version3}"
    
    @patch("src.orchestrator.api.jobs.logger")
    def test_job_version_cycle_detection(self, mock_logger, monkeypatch):
        """Test that cycles are detected and handled safely."""
        # Setup cycle: job1 -> job2 -> job1 (cycle)
        job_records = {
            "job-1": {"job_id": "job-1", "parent_job_id": "job-2"},
            "job-2": {"job_id": "job-2", "parent_job_id": "job-1"},
        }
        self._configure_job_records(monkeypatch, job_records)
        
        # Get version for job-1 (should detect cycle and return safe fallback)
        version = _get_job_version("job-1")
        
        # Should return safe fallback (1) instead of infinite recursion
        assert version == 1
        
        # Verify warning was logged
        assert mock_logger.warning.called
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Cycle detected" in warning_call
    
    @patch("src.orchestrator.api.jobs.logger")
    def test_job_version_max_depth_protection(self, mock_logger, monkeypatch):
        """Test that max depth (10) is enforced to prevent runaway recursion."""
        # Setup long chain: job1 -> job2 -> ... -> job12 (exceeds max depth)
        MAX_DEPTH = 10
        
        job_records = {}
        for job_num in range(1, MAX_DEPTH + 3):
            job_id = f"job-{job_num}"
            if job_num <= MAX_DEPTH + 2:
                # Create parent link (job-N -> job-(N+1))
                job_records[job_id] = {"job_id": job_id, "parent_job_id": f"job-{job_num + 1}"}
            else:
                job_records[job_id] = {"job_id": job_id}  # No parent (end of chain)
        
        self._configure_job_records(monkeypatch, job_records)
        
        # Get version for job-1 (should hit max depth and return safe fallback)
        version = _get_job_version("job-1")
        
        # Should return safe fallback (1) instead of continuing recursion
        assert version == 1
        
        # Verify warning was logged
        assert mock_logger.warning.called
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Max depth" in warning_call or "exceeded" in warning_call.lower()
    
    def test_job_version_with_explicit_version(self, monkeypatch):
        """Test that explicitly stored job_version is used (no recursion needed)."""
        job_records = {"job-1": {"job_id": "job-1", "job_version": 5}}
        self._configure_job_records(monkeypatch, job_records)
        
        version = _get_job_version("job-1")
        
        assert version == 5
        # No recursion needed since job_version is explicitly stored
    
    def test_job_version_defaults_to_one(self, monkeypatch):
        """Test that jobs without version or parent default to version 1."""
        job_records = {"job-1": {"job_id": "job-1"}}  # No version, no parent
        self._configure_job_records(monkeypatch, job_records)
        
        version = _get_job_version("job-1")
        
        assert version == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

