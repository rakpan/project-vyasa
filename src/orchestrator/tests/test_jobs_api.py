"""
Tests for jobs API endpoints focusing on:
- Cycle detection in _get_job_version
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.orchestrator.api.jobs import _get_job_version
from src.orchestrator.job_store import get_job_record


class TestJobVersionCycleDetection:
    """Test cycle detection in job version calculation."""
    
    @patch("src.orchestrator.api.jobs.get_job_record")
    def test_job_version_without_cycle(self, mock_get_job_record):
        """Test normal job version calculation without cycles."""
        # Setup job chain: job1 -> job2 -> job3
        def side_effect(job_id):
            if job_id == "job-1":
                return {"job_id": "job-1", "job_version": 1}  # Original job
            elif job_id == "job-2":
                return {"job_id": "job-2", "parent_job_id": "job-1"}  # Reprocessed job
            elif job_id == "job-3":
                return {"job_id": "job-3", "parent_job_id": "job-2"}  # Reprocessed again
            return {}
        
        mock_get_job_record.side_effect = side_effect
        
        # Test version calculation
        version1 = _get_job_version("job-1")
        assert version1 == 1
        
        version2 = _get_job_version("job-2")
        assert version2 == 2
        
        version3 = _get_job_version("job-3")
        assert version3 == 3
    
    @patch("src.orchestrator.api.jobs.get_job_record")
    @patch("src.orchestrator.api.jobs.logger")
    def test_job_version_cycle_detection(self, mock_logger, mock_get_job_record):
        """Test that cycles are detected and handled safely."""
        # Setup cycle: job1 -> job2 -> job1 (cycle)
        def side_effect(job_id):
            if job_id == "job-1":
                return {"job_id": "job-1", "parent_job_id": "job-2"}
            elif job_id == "job-2":
                return {"job_id": "job-2", "parent_job_id": "job-1"}
            return {}
        
        mock_get_job_record.side_effect = side_effect
        
        # Get version for job-1 (should detect cycle and return safe fallback)
        version = _get_job_version("job-1")
        
        # Should return safe fallback (1) instead of infinite recursion
        assert version == 1
        
        # Verify warning was logged
        assert mock_logger.warning.called
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Cycle detected" in warning_call
    
    @patch("src.orchestrator.api.jobs.get_job_record")
    @patch("src.orchestrator.api.jobs.logger")
    def test_job_version_max_depth_protection(self, mock_logger, mock_get_job_record):
        """Test that max depth (10) is enforced to prevent runaway recursion."""
        # Setup long chain: job1 -> job2 -> ... -> job12 (exceeds max depth)
        MAX_DEPTH = 10
        
        def side_effect(job_id):
            job_num = int(job_id.split("-")[1])
            if job_num <= MAX_DEPTH + 2:
                # Create parent link (job-N -> job-(N+1))
                return {"job_id": job_id, "parent_job_id": f"job-{job_num + 1}"}
            return {"job_id": job_id}  # No parent (end of chain)
        
        mock_get_job_record.side_effect = side_effect
        
        # Get version for job-1 (should hit max depth and return safe fallback)
        version = _get_job_version("job-1")
        
        # Should return safe fallback (1) instead of continuing recursion
        assert version == 1
        
        # Verify warning was logged
        assert mock_logger.warning.called
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Max depth" in warning_call or "exceeded" in warning_call.lower()
    
    @patch("src.orchestrator.api.jobs.get_job_record")
    def test_job_version_with_explicit_version(self, mock_get_job_record):
        """Test that explicitly stored job_version is used (no recursion needed)."""
        mock_get_job_record.return_value = {"job_id": "job-1", "job_version": 5}
        
        version = _get_job_version("job-1")
        
        assert version == 5
        # Should only call get_job_record once (no recursion)
        assert mock_get_job_record.call_count == 1
    
    @patch("src.orchestrator.api.jobs.get_job_record")
    def test_job_version_defaults_to_one(self, mock_get_job_record):
        """Test that jobs without version or parent default to version 1."""
        mock_get_job_record.return_value = {"job_id": "job-1"}  # No version, no parent
        
        version = _get_job_version("job-1")
        
        assert version == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

