"""
Unit tests for rigor toggle API endpoint.
Tests: PATCH updates rigor_level, GET returns current rigor
"""

import pytest
from unittest.mock import Mock, patch
from flask import Flask

from src.orchestrator.server import app


@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestRigorToggle:
    """Tests for rigor toggle endpoint."""
    
    @patch("src.orchestrator.server.get_project_service")
    def test_get_rigor_level(self, mock_get_service, client):
        """Test GET returns current rigor level."""
        mock_service = Mock()
        mock_project = Mock()
        mock_project.rigor_level = "conservative"
        mock_service.get_project.return_value = mock_project
        mock_get_service.return_value = mock_service
        
        response = client.get("/api/projects/test_project_123/rigor")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["project_id"] == "test_project_123"
        assert data["rigor_level"] == "conservative"
    
    @patch("src.orchestrator.server.get_project_service")
    def test_patch_updates_rigor_level(self, mock_get_service, client):
        """Test PATCH updates rigor level."""
        mock_service = Mock()
        mock_project = Mock()
        mock_project.rigor_level = "exploratory"
        mock_service.get_project.return_value = mock_project
        mock_service.db.collection.return_value = Mock()
        mock_get_service.return_value = mock_service
        
        response = client.patch(
            "/api/projects/test_project_123/rigor",
            json={"rigor_level": "conservative"},
            content_type="application/json",
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["project_id"] == "test_project_123"
        assert data["rigor_level"] == "conservative"
        
        # Verify update was called
        collection = mock_service.db.collection.return_value
        collection.update.assert_called_once()
        update_args = collection.update.call_args[0][0]
        assert update_args["_key"] == "test_project_123"
        assert update_args["rigor_level"] == "conservative"
    
    @patch("src.orchestrator.server.get_project_service")
    def test_patch_invalid_rigor_level(self, mock_get_service, client):
        """Test PATCH with invalid rigor level returns 400."""
        mock_service = Mock()
        mock_project = Mock()
        mock_project.rigor_level = "exploratory"
        mock_service.get_project.return_value = mock_project
        mock_get_service.return_value = mock_service
        
        response = client.patch(
            "/api/projects/test_project_123/rigor",
            json={"rigor_level": "invalid"},
            content_type="application/json",
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "rigor_level must be" in data["error"]
    
    @patch("src.orchestrator.server.get_project_service")
    def test_patch_project_not_found(self, mock_get_service, client):
        """Test PATCH with non-existent project returns 404."""
        mock_service = Mock()
        mock_service.get_project.side_effect = ValueError("Project not found")
        mock_get_service.return_value = mock_service
        
        response = client.patch(
            "/api/projects/nonexistent/rigor",
            json={"rigor_level": "conservative"},
            content_type="application/json",
        )
        
        assert response.status_code == 404
    
    @patch("src.orchestrator.server.get_project_service")
    def test_patch_updates_last_updated(self, mock_get_service, client):
        """Test PATCH updates last_updated timestamp."""
        mock_service = Mock()
        mock_project = Mock()
        mock_project.rigor_level = "exploratory"
        mock_service.get_project.return_value = mock_project
        mock_collection = Mock()
        mock_service.db.collection.return_value = mock_collection
        mock_get_service.return_value = mock_service
        
        response = client.patch(
            "/api/projects/test_project_123/rigor",
            json={"rigor_level": "conservative"},
            content_type="application/json",
        )
        
        assert response.status_code == 200
        update_args = mock_collection.update.call_args[0][0]
        assert "_key" in update_args
        assert "rigor_level" in update_args
        assert "last_updated" in update_args

