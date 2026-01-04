"""
Unit tests for OpikEmitter.

Tests verify:
- OpikEmitter is no-op when Opik is disabled
- emit_node_start/end/validation methods work correctly
- All emissions are best-effort and never raise exceptions
- Proper payload structure and metadata extraction
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.orchestrator.telemetry.opik_emitter import OpikEmitter, get_opik_emitter


class TestOpikEmitterDisabled:
    """Tests for OpikEmitter when Opik is disabled."""
    
    @patch("src.orchestrator.telemetry.opik_emitter.OPIK_ENABLED", False)
    def test_emitter_is_noop_when_disabled(self):
        """OpikEmitter should be no-op when OPIK_ENABLED=false."""
        emitter = OpikEmitter()
        
        # Should not raise or do anything
        emitter.emit_node_start("job1", "project1", "cartographer")
        emitter.emit_node_end("job1", "project1", "cartographer")
        emitter.emit_validation("job1", "project1", "schema", {"pass": True})
    
    @patch("src.orchestrator.telemetry.opik_emitter.OPIK_ENABLED", True)
    @patch("src.orchestrator.telemetry.opik_emitter.OPIK_BASE_URL", None)
    def test_emitter_is_noop_when_no_base_url(self):
        """OpikEmitter should be no-op when OPIK_BASE_URL is None."""
        emitter = OpikEmitter()
        
        # Should not raise or do anything
        emitter.emit_node_start("job1", "project1", "cartographer")
        emitter.emit_node_end("job1", "project1", "cartographer")
        emitter.emit_validation("job1", "project1", "schema", {"pass": True})


class TestOpikEmitterEnabled:
    """Tests for OpikEmitter when Opik is enabled."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock Opik client configuration."""
        return {
            "base_url": "http://opik:8000",
            "headers": {"Content-Type": "application/json", "Authorization": "Bearer test-key"},
            "timeout": 2,
            "project": "vyasa",
        }
    
    @pytest.fixture
    def emitter(self, mock_client):
        """Create OpikEmitter with mocked client."""
        with patch("src.orchestrator.telemetry.opik_emitter.OPIK_ENABLED", True), \
             patch("src.orchestrator.telemetry.opik_emitter.OPIK_BASE_URL", "http://opik:8000"), \
             patch("src.orchestrator.telemetry.opik_emitter.OPIK_API_KEY", "test-key"), \
             patch("src.orchestrator.telemetry.opik_emitter.OPIK_PROJECT_NAME", "vyasa"), \
             patch("src.orchestrator.telemetry.opik_emitter.OPIK_TIMEOUT_SECONDS", 2):
            return OpikEmitter()
    
    def test_emit_node_start_sends_correct_payload(self, emitter, mock_client):
        """emit_node_start should send correct payload structure."""
        with patch("src.orchestrator.telemetry.opik_emitter.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            emitter.emit_node_start(
                job_id="job1",
                project_id="project1",
                node_name="cartographer",
                meta={"rigor_level": "conservative", "custom_field": "value"},
            )
            
            # Verify POST was called
            assert mock_post.called
            call_args = mock_post.call_args
            
            # Verify URL
            assert call_args[0][0] == "http://opik:8000/api/traces"
            
            # Verify payload structure
            payload = call_args[1]["json"]
            assert payload["project"] == "vyasa"
            assert payload["run_type"] == "node_start"
            assert payload["metadata"]["job_id"] == "job1"
            assert payload["metadata"]["project_id"] == "project1"
            assert payload["metadata"]["node_name"] == "cartographer"
            assert payload["metadata"]["rigor_level"] == "conservative"
            assert payload["metadata"]["custom_field"] == "value"
            assert "timestamp" in payload["metadata"]
            
            # Verify headers
            assert call_args[1]["headers"]["Content-Type"] == "application/json"
            assert "Authorization" in call_args[1]["headers"]
            
            # Verify timeout
            assert call_args[1]["timeout"] == 2
    
    def test_emit_node_start_with_none_project_id(self, emitter):
        """emit_node_start should handle None project_id."""
        with patch("src.orchestrator.telemetry.opik_emitter.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            emitter.emit_node_start(
                job_id="job1",
                project_id=None,
                node_name="cartographer",
            )
            
            payload = mock_post.call_args[1]["json"]
            assert payload["metadata"]["project_id"] is None
    
    def test_emit_node_end_extracts_counts(self, emitter):
        """emit_node_end should extract counts from metadata."""
        with patch("src.orchestrator.telemetry.opik_emitter.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            emitter.emit_node_end(
                job_id="job1",
                project_id="project1",
                node_name="cartographer",
                meta={
                    "extracted_json": {"triples": [1, 2, 3]},
                    "conflicts": [{"id": "c1"}, {"id": "c2"}],
                    "manuscript_blocks": [{"id": "b1"}],
                },
            )
            
            payload = mock_post.call_args[1]["json"]
            assert payload["run_type"] == "node_end"
            assert payload["metadata"]["counts"]["claims_count"] == 3
            assert payload["metadata"]["counts"]["conflicts_count"] == 2
            assert payload["metadata"]["counts"]["blocks_count"] == 1
    
    def test_emit_node_end_extracts_prompt_metadata(self, emitter):
        """emit_node_end should extract prompt metadata from prompt_manifest."""
        with patch("src.orchestrator.telemetry.opik_emitter.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            prompt_manifest = {
                "cartographer": {
                    "resolved_source": "opik",
                    "prompt_hash": "abc123",
                },
            }
            
            emitter.emit_node_end(
                job_id="job1",
                project_id="project1",
                node_name="cartographer",
                meta={"prompt_manifest": prompt_manifest},
            )
            
            payload = mock_post.call_args[1]["json"]
            assert payload["metadata"]["prompt_metadata"]["resolved_source"] == "opik"
            assert payload["metadata"]["prompt_metadata"]["prompt_hash"] == "abc123"
    
    def test_emit_node_end_handles_missing_metadata(self, emitter):
        """emit_node_end should handle missing metadata gracefully."""
        with patch("src.orchestrator.telemetry.opik_emitter.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            emitter.emit_node_end(
                job_id="job1",
                project_id="project1",
                node_name="cartographer",
                meta=None,
            )
            
            payload = mock_post.call_args[1]["json"]
            assert payload["metadata"]["counts"] == {}
            assert payload["metadata"]["prompt_metadata"] == {}
    
    def test_emit_validation_sends_correct_payload(self, emitter):
        """emit_validation should send correct payload structure."""
        with patch("src.orchestrator.telemetry.opik_emitter.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            emitter.emit_validation(
                job_id="job1",
                project_id="project1",
                kind="citation_integrity",
                result_meta={
                    "pass": True,
                    "findings_count": 0,
                    "errors": [],
                },
            )
            
            payload = mock_post.call_args[1]["json"]
            assert payload["project"] == "vyasa"
            assert payload["run_type"] == "validation"
            assert payload["metadata"]["job_id"] == "job1"
            assert payload["metadata"]["project_id"] == "project1"
            assert payload["metadata"]["validation_kind"] == "citation_integrity"
            assert payload["metadata"]["pass"] is True
            assert payload["metadata"]["findings_count"] == 0
            assert "timestamp" in payload["metadata"]


class TestOpikEmitterErrorHandling:
    """Tests for error handling in OpikEmitter."""
    
    @pytest.fixture
    def emitter(self):
        """Create OpikEmitter with Opik enabled."""
        with patch("src.orchestrator.telemetry.opik_emitter.OPIK_ENABLED", True), \
             patch("src.orchestrator.telemetry.opik_emitter.OPIK_BASE_URL", "http://opik:8000"), \
             patch("src.orchestrator.telemetry.opik_emitter.OPIK_API_KEY", "test-key"), \
             patch("src.orchestrator.telemetry.opik_emitter.OPIK_PROJECT_NAME", "vyasa"), \
             patch("src.orchestrator.telemetry.opik_emitter.OPIK_TIMEOUT_SECONDS", 2):
            return OpikEmitter()
    
    def test_emit_node_start_handles_timeout(self, emitter):
        """emit_node_start should handle timeout gracefully."""
        import requests
        with patch("src.orchestrator.telemetry.opik_emitter.requests.post") as mock_post:
            mock_post.side_effect = requests.Timeout("Connection timeout")
            
            # Should not raise
            emitter.emit_node_start("job1", "project1", "cartographer")
    
    def test_emit_node_start_handles_http_error(self, emitter):
        """emit_node_start should handle HTTP errors gracefully."""
        import requests
        with patch("src.orchestrator.telemetry.opik_emitter.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.HTTPError("500 Internal Server Error")
            mock_post.return_value = mock_response
            
            # Should not raise
            emitter.emit_node_start("job1", "project1", "cartographer")
    
    def test_emit_node_start_handles_generic_exception(self, emitter):
        """emit_node_start should handle any exception gracefully."""
        with patch("src.orchestrator.telemetry.opik_emitter.requests.post") as mock_post:
            mock_post.side_effect = Exception("Unexpected error")
            
            # Should not raise
            emitter.emit_node_start("job1", "project1", "cartographer")
    
    def test_emit_node_end_handles_exception(self, emitter):
        """emit_node_end should handle exceptions gracefully."""
        with patch("src.orchestrator.telemetry.opik_emitter.requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")
            
            # Should not raise
            emitter.emit_node_end("job1", "project1", "cartographer", meta={})
    
    def test_emit_validation_handles_exception(self, emitter):
        """emit_validation should handle exceptions gracefully."""
        with patch("src.orchestrator.telemetry.opik_emitter.requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")
            
            # Should not raise
            emitter.emit_validation("job1", "project1", "schema", {"pass": True})


class TestOpikEmitterSingleton:
    """Tests for OpikEmitter singleton pattern."""
    
    def test_get_opik_emitter_returns_singleton(self):
        """get_opik_emitter should return the same instance."""
        # Reset singleton
        import src.orchestrator.telemetry.opik_emitter as opik_module
        opik_module._opik_emitter = None
        
        emitter1 = get_opik_emitter()
        emitter2 = get_opik_emitter()
        
        assert emitter1 is emitter2
    
    def test_get_opik_emitter_works_when_disabled(self):
        """get_opik_emitter should work even when Opik is disabled."""
        with patch("src.orchestrator.telemetry.opik_emitter.OPIK_ENABLED", False):
            # Reset singleton
            import src.orchestrator.telemetry.opik_emitter as opik_module
            opik_module._opik_emitter = None
            
            emitter = get_opik_emitter()
            assert isinstance(emitter, OpikEmitter)
            # Should be no-op but still return instance
            emitter.emit_node_start("job1", "project1", "cartographer")

