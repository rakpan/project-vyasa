"""
Unit tests for manuscript block forking API.
Tests: fork creates read-only variant, accept persists version
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

from src.orchestrator.api.manuscript import manuscript_bp, _get_block_by_id, _get_triples_by_claim_ids


@pytest.fixture
def app():
    """Create Flask app with manuscript blueprint."""
    app = Flask(__name__)
    app.register_blueprint(manuscript_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def mock_db():
    """Mock ArangoDB database."""
    db = Mock()
    db.has_collection.return_value = True
    db.collection.return_value = Mock()
    return db


@pytest.fixture
def mock_block():
    """Sample block data."""
    return {
        "block_id": "intro_001",
        "section_title": "Introduction",
        "content": "Original content",
        "claim_ids": ["claim_123", "claim_456"],
        "citation_keys": ["smith2023"],
        "version": 1,
        "project_id": "project_123",
    }


class TestForkBlock:
    """Tests for block forking endpoint."""
    
    @patch("src.orchestrator.api.manuscript._get_db")
    @patch("src.orchestrator.api.manuscript._get_block_by_id")
    @patch("src.orchestrator.api.manuscript._get_triples_by_claim_ids")
    @patch("src.orchestrator.api.manuscript.route_to_expert")
    @patch("src.orchestrator.api.manuscript.call_expert_with_fallback")
    def test_fork_block_creates_read_only_variant(
        self,
        mock_call_expert,
        mock_route_expert,
        mock_get_triples,
        mock_get_block,
        mock_get_db,
        app,
        mock_db,
        mock_block,
    ):
        """Test that forking a block creates a read-only variant."""
        mock_get_db.return_value = mock_db
        mock_get_block.return_value = mock_block
        mock_get_triples.return_value = [
            {"claim_id": "claim_123", "subject": "A", "predicate": "relates", "object": "B"},
            {"claim_id": "claim_456", "subject": "C", "predicate": "causes", "object": "D"},
        ]
        mock_route_expert.return_value = ("http://worker:8000", "Worker", "model_id")
        mock_call_expert.return_value = (
            {
                "choices": [
                    {
                        "message": {
                            "content": "Forked content with conservative rigor"
                        }
                    }
                ]
            },
            {"path": "primary"},
        )
        
        with app.test_client() as client:
            response = client.post(
                "/api/projects/project_123/blocks/intro_001/fork",
                json={"rigor_level": "conservative", "job_id": "job_123"},
            )
        
        assert response.status_code == 200
        data = response.get_json()
        assert "forked_block" in data
        assert data["forked_block"]["block_id"] == "intro_001"
        assert data["forked_block"]["rigor_level"] == "conservative"
        assert data["forked_block"]["content"] == "Forked content with conservative rigor"
        assert data["forked_block"]["claim_ids"] == ["claim_123", "claim_456"]
        assert data["forked_block"]["citation_keys"] == ["smith2023"]
    
    @patch("src.orchestrator.api.manuscript._get_db")
    def test_fork_block_not_found(self, mock_get_db, app, mock_db):
        """Test forking a non-existent block returns 404."""
        mock_get_db.return_value = mock_db
        
        with patch("src.orchestrator.api.manuscript._get_block_by_id", return_value=None):
            with app.test_client() as client:
                response = client.post(
                    "/api/projects/project_123/blocks/nonexistent/fork",
                    json={"rigor_level": "exploratory"},
                )
        
        assert response.status_code == 404
    
    @patch("src.orchestrator.api.manuscript._get_db")
    def test_fork_block_invalid_rigor(self, mock_get_db, app, mock_db):
        """Test forking with invalid rigor level returns 400."""
        mock_get_db.return_value = mock_db
        
        with app.test_client() as client:
            response = client.post(
                "/api/projects/project_123/blocks/intro_001/fork",
                json={"rigor_level": "invalid"},
            )
        
        assert response.status_code == 400


class TestAcceptFork:
    """Tests for accepting a forked block."""
    
    @patch("src.orchestrator.api.manuscript._get_db")
    @patch("src.orchestrator.api.manuscript._get_block_by_id")
    @patch("src.orchestrator.api.manuscript.ManuscriptService")
    def test_accept_fork_persists_version(
        self,
        mock_manuscript_service_class,
        mock_get_block,
        mock_get_db,
        app,
        mock_db,
        mock_block,
    ):
        """Test that accepting a fork creates a new block version."""
        mock_get_db.return_value = mock_db
        mock_get_block.return_value = mock_block
        
        # Mock ManuscriptService
        mock_service = Mock()
        mock_saved_block = Mock()
        mock_saved_block.version = 2
        mock_saved_block.model_dump.return_value = {
            "block_id": "intro_001",
            "version": 2,
            "content": "Forked content",
        }
        mock_service.save_block.return_value = mock_saved_block
        mock_manuscript_service_class.return_value = mock_service
        
        with app.test_client() as client:
            response = client.post(
                "/api/projects/project_123/blocks/intro_001/accept-fork",
                json={
                    "content": "Forked content",
                    "section_title": "Introduction",
                    "rigor_level": "conservative",
                },
            )
        
        assert response.status_code == 200
        data = response.get_json()
        assert "block" in data
        assert data["version"] == 2
        mock_service.save_block.assert_called_once()
    
    @patch("src.orchestrator.api.manuscript._get_db")
    def test_accept_fork_missing_content(self, mock_get_db, app, mock_db):
        """Test accepting fork without content returns 400."""
        mock_get_db.return_value = mock_db
        
        with app.test_client() as client:
            response = client.post(
                "/api/projects/project_123/blocks/intro_001/accept-fork",
                json={"rigor_level": "conservative"},
            )
        
        assert response.status_code == 400

