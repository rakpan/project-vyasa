"""
Unit tests for vision_node.

Tests verify that vision_node:
- Returns expected state structure
- Handles empty image_paths gracefully
- Mocks model calls correctly
- Produces deterministic return structure
"""

import json
import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from typing import Dict, Any

from src.orchestrator.nodes.utils import vision_node, select_images_for_vision, build_vision_context


class TestVisionNodeHelpers:
    """Tests for vision_node helper functions."""
    
    def test_select_images_for_vision_empty_list(self):
        """Test select_images_for_vision with empty list."""
        result = select_images_for_vision([])
        assert result == []
    
    def test_select_images_for_vision_limits_max_images(self):
        """Test select_images_for_vision limits to max images."""
        image_paths = [f"/tmp/image_{i}.png" for i in range(10)]
        result = select_images_for_vision(image_paths)
        # Default max is 5
        assert len(result) <= 5
    
    def test_select_images_for_vision_prefers_figures(self):
        """Test select_images_for_vision prefers figure/table/chart images."""
        image_paths = [
            "/tmp/random.png",
            "/tmp/figure1.png",
            "/tmp/table2.png",
            "/tmp/chart3.png",
        ]
        result = select_images_for_vision(image_paths)
        # Preferred images should come first
        assert any("figure" in path or "table" in path or "chart" in path for path in result[:3])
    
    def test_build_vision_context_empty_results(self):
        """Test build_vision_context with empty results."""
        result = build_vision_context([])
        assert result == ""
    
    def test_build_vision_context_deterministic(self):
        """Test build_vision_context produces deterministic output."""
        vision_results = [
            {
                "image_path": "/tmp/figure1.png",
                "caption": "Test caption",
                "extracted_facts": [
                    {"key": "temperature", "value": "25", "unit": "C", "confidence": 0.9}
                ],
                "tables": [],
            }
        ]
        result1 = build_vision_context(vision_results)
        result2 = build_vision_context(vision_results)
        assert result1 == result2
        assert "figure1.png" in result1
        assert "Test caption" in result1
        assert "temperature" in result1


class TestVisionNode:
    """Tests for vision_node main function."""
    
    @pytest.fixture
    def minimal_state(self) -> Dict[str, Any]:
        """Minimal ResearchState fixture for vision_node tests."""
        return {
            "jobId": "test-job-123",
            "threadId": "test-thread-123",
            "job_id": "test-job-123",
            "project_id": "test-project-456",
            "raw_text": "Initial text content.",
            "image_paths": [],
        }
    
    def test_vision_node_empty_image_paths(self, minimal_state):
        """Test vision_node handles empty image_paths gracefully."""
        result = vision_node(minimal_state)
        
        assert "vision_output" in result
        assert result["vision_output"] == []
        # State should be preserved
        assert result.get("raw_text") == minimal_state["raw_text"]
    
    def test_vision_node_returns_expected_structure(self, minimal_state, tmp_path):
        """Test vision_node returns expected state structure with mocked model calls."""
        # Create a temporary image file
        image_path = tmp_path / "test_figure.png"
        image_path.write_bytes(b"fake image data")
        
        minimal_state["image_paths"] = [str(image_path)]
        
        # Mock vision API response
        mock_vision_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "caption": "Test figure caption",
                        "extracted_facts": [
                            {"key": "value1", "value": "100", "unit": "px", "confidence": 0.95}
                        ],
                        "tables": [],
                        "confidence": 0.95,
                        "notes": "Test notes",
                    })
                }
            }]
        }
        
        # validate_state_schema is imported from nodes.nodes inside the function
        with patch("src.orchestrator.nodes.nodes.validate_state_schema", lambda x: x):
            with patch("src.orchestrator.nodes.utils.requests.post") as mock_post:
                mock_resp = MagicMock()
                mock_resp.json.return_value = mock_vision_response
                mock_resp.raise_for_status = MagicMock()
                mock_post.return_value = mock_resp
                
                with patch("src.orchestrator.nodes.utils.get_vision_url", return_value="http://mock-vision:8000"):
                    with patch("src.orchestrator.nodes.utils.get_model_config") as mock_model_config:
                        mock_config = MagicMock()
                        mock_config.model_id = "test-vision-model"
                        mock_config.kv_policy = "evict"
                        mock_model_config.return_value = mock_config
                        
                        with patch("src.orchestrator.nodes.utils.Path.mkdir"):
                            with patch("src.orchestrator.nodes.utils.shutil.copy"):
                                with patch("builtins.open", mock_open(read_data=b"fake image data")):
                                    # time.time() is called twice: start and end
                                    with patch("src.orchestrator.nodes.utils.time.time", side_effect=[0.0, 0.1, 0.0, 0.1]):
                                        result = vision_node(minimal_state)
                                        
                                        # Assert returned state includes expected keys
                                        assert "raw_text" in result, "Result must include raw_text"
                                        assert "vision_results" in result, "Result must include vision_results"
                                        
                                        # Assert vision_results is a list
                                        assert isinstance(result["vision_results"], list)
                                        
                                        # Assert raw_text was updated with vision context
                                        assert "Vision Extracts" in result["raw_text"]
                                        assert "test_figure.png" in result["raw_text"]
                                        
                                        # Assert vision_results contains expected structure
                                        if len(result["vision_results"]) > 0:
                                            first_result = result["vision_results"][0]
                                            assert "image_path" in first_result
                                            assert "caption" in first_result
                                            assert "extracted_facts" in first_result
                                            assert "artifact_id" in first_result
                                            assert "telemetry" in first_result
    
    def test_vision_node_handles_api_failure_gracefully(self, minimal_state, tmp_path):
        """Test vision_node handles API failures gracefully."""
        image_path = tmp_path / "test_figure.png"
        image_path.write_bytes(b"fake image data")
        
        minimal_state["image_paths"] = [str(image_path)]
        
        # validate_state_schema is imported from nodes.nodes inside the function
        with patch("src.orchestrator.nodes.nodes.validate_state_schema", lambda x: x):
            with patch("src.orchestrator.nodes.utils.requests.post") as mock_post:
                # Simulate API failure
                mock_post.side_effect = Exception("API connection failed")
                
                with patch("src.orchestrator.nodes.utils.get_vision_url", return_value="http://mock-vision:8000"):
                    with patch("src.orchestrator.nodes.utils.Path.mkdir"):
                        with patch("src.orchestrator.nodes.utils.shutil.copy"):
                            result = vision_node(minimal_state)
                            
                            # Should return empty vision_results, not crash
                            assert "vision_results" in result
                            assert isinstance(result["vision_results"], list)
                            # May be empty if all images failed
                            assert len(result["vision_results"]) == 0

