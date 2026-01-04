"""
Unit tests for claim anchor API endpoint.

Ensures:
- GET /api/claims/{claim_id}/anchor returns stable source_anchor fields
- Endpoint handles missing claims gracefully
- source_anchor matches stored values from ArangoDB
"""

import pytest
from unittest.mock import MagicMock, patch
from flask import Flask

from src.orchestrator.api.claims import claims_bp


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.register_blueprint(claims_bp)
    return app


@pytest.fixture
def mock_db():
    """Mock ArangoDB database."""
    db = MagicMock()
    db.has_collection.return_value = True
    return db


@pytest.fixture
def sample_claim_with_anchor():
    """Sample claim data with source_anchor."""
    return {
        "claim_id": "test-claim-123",
        "source_anchor": {
            "doc_id": "doc-hash-abc123",
            "page_number": 5,
            "bbox": {"x": 10.0, "y": 20.0, "w": 100.0, "h": 50.0},
            "snippet": "This is a test snippet.",
        },
        "source_pointer": None,
        "file_hash": "doc-hash-abc123",
    }


@pytest.fixture
def sample_claim_with_pointer():
    """Sample claim data with source_pointer (no source_anchor)."""
    return {
        "claim_id": "test-claim-456",
        "source_anchor": None,
        "source_pointer": {
            "doc_hash": "doc-hash-def456",
            "page": 3,
            "bbox": [15.0, 25.0, 115.0, 75.0],
            "snippet": "Another test snippet.",
        },
        "file_hash": "doc-hash-def456",
    }


class TestClaimAnchorEndpoint:
    """Tests for GET /api/claims/{claim_id}/anchor endpoint."""

    @patch("src.orchestrator.api.claims.ArangoClient")
    @patch("src.orchestrator.api.claims.get_anchor_from_db")
    def test_get_claim_anchor_success_with_anchor(
        self,
        mock_get_anchor,
        mock_arango_client,
        app,
        sample_claim_with_anchor,
    ):
        """Asserts endpoint returns source_anchor when claim has anchor."""
        mock_get_anchor.return_value = sample_claim_with_anchor["source_anchor"]
        
        with app.test_client() as client:
            response = client.get("/api/claims/test-claim-123/anchor")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["claim_id"] == "test-claim-123"
        assert "source_anchor" in data
        anchor = data["source_anchor"]
        assert anchor["doc_id"] == "doc-hash-abc123"
        assert anchor["page_number"] == 5
        assert anchor["bbox"] == {"x": 10.0, "y": 20.0, "w": 100.0, "h": 50.0}
        assert anchor["snippet"] == "This is a test snippet."

    @patch("src.orchestrator.api.claims.ArangoClient")
    @patch("src.orchestrator.api.claims.get_anchor_from_db")
    def test_get_claim_anchor_success_with_pointer(
        self,
        mock_get_anchor,
        mock_arango_client,
        app,
        sample_claim_with_pointer,
    ):
        """Asserts endpoint converts source_pointer to source_anchor."""
        # get_anchor_from_db should convert source_pointer to source_anchor
        converted_anchor = {
            "doc_id": "doc-hash-def456",
            "page_number": 3,
            "bbox": {"x": 15.0, "y": 25.0, "w": 100.0, "h": 50.0},
            "snippet": "Another test snippet.",
        }
        mock_get_anchor.return_value = converted_anchor
        
        with app.test_client() as client:
            response = client.get("/api/claims/test-claim-456/anchor")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["claim_id"] == "test-claim-456"
        assert "source_anchor" in data
        anchor = data["source_anchor"]
        assert anchor["doc_id"] == "doc-hash-def456"
        assert anchor["page_number"] == 3
        assert anchor["bbox"]["x"] == 15.0
        assert anchor["bbox"]["w"] == 100.0

    @patch("src.orchestrator.api.claims.ArangoClient")
    @patch("src.orchestrator.api.claims.get_anchor_from_db")
    def test_get_claim_anchor_not_found(
        self,
        mock_get_anchor,
        mock_arango_client,
        app,
    ):
        """Asserts endpoint returns 404 when claim not found."""
        mock_get_anchor.return_value = None
        
        with app.test_client() as client:
            response = client.get("/api/claims/nonexistent-claim/anchor")
        
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert "not found" in data["error"].lower()

    @patch("src.orchestrator.api.claims.ArangoClient")
    def test_get_claim_anchor_database_unavailable(
        self,
        mock_arango_client,
        app,
    ):
        """Asserts endpoint returns 503 when database is unavailable."""
        mock_arango_client.side_effect = Exception("Connection failed")
        
        with app.test_client() as client:
            response = client.get("/api/claims/test-claim-123/anchor")
        
        assert response.status_code == 503
        data = response.get_json()
        assert "error" in data
        assert "unavailable" in data["error"].lower()

    @patch("src.orchestrator.api.claims.ArangoClient")
    @patch("src.orchestrator.api.claims.get_anchor_from_db")
    def test_get_claim_anchor_stable_fields(
        self,
        mock_get_anchor,
        mock_arango_client,
        app,
        sample_claim_with_anchor,
    ):
        """Asserts endpoint returns stable field structure."""
        mock_get_anchor.return_value = sample_claim_with_anchor["source_anchor"]
        
        with app.test_client() as client:
            response1 = client.get("/api/claims/test-claim-123/anchor")
            response2 = client.get("/api/claims/test-claim-123/anchor")
        
        # Both responses should be identical
        assert response1.status_code == 200
        assert response2.status_code == 200
        data1 = response1.get_json()
        data2 = response2.get_json()
        
        # Compare source_anchor structure
        anchor1 = data1["source_anchor"]
        anchor2 = data2["source_anchor"]
        assert anchor1 == anchor2
        assert anchor1["doc_id"] == anchor2["doc_id"]
        assert anchor1["page_number"] == anchor2["page_number"]
        if "bbox" in anchor1:
            assert anchor1["bbox"] == anchor2["bbox"]


class TestGetClaimAnchorFromDB:
    """Tests for get_claim_anchor function in storage/arango.py."""

    @patch("src.orchestrator.storage.arango.SourceAnchor")
    def test_get_claim_anchor_from_extractions_with_anchor(
        self,
        mock_source_anchor,
        mock_db,
        sample_claim_with_anchor,
    ):
        """Asserts get_claim_anchor returns source_anchor from extractions."""
        from src.orchestrator.storage.arango import get_claim_anchor
        
        # Mock AQL query result
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = lambda self: iter([sample_claim_with_anchor])
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_claim_anchor(mock_db, "test-claim-123")
        
        assert result is not None
        assert result["doc_id"] == "doc-hash-abc123"
        assert result["page_number"] == 5
        assert "bbox" in result

    @patch("src.orchestrator.storage.arango.SourceAnchor")
    def test_get_claim_anchor_converts_pointer_to_anchor(
        self,
        mock_source_anchor,
        mock_db,
        sample_claim_with_pointer,
    ):
        """Asserts get_claim_anchor converts source_pointer to source_anchor."""
        from src.orchestrator.storage.arango import get_claim_anchor
        
        # Mock AQL query result
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = lambda self: iter([sample_claim_with_pointer])
        mock_db.aql.execute.return_value = mock_cursor
        
        # Mock SourceAnchor validation
        mock_anchor_instance = MagicMock()
        mock_anchor_instance.model_dump.return_value = {
            "doc_id": "doc-hash-def456",
            "page_number": 3,
            "bbox": {"x": 15.0, "y": 25.0, "w": 100.0, "h": 50.0},
            "snippet": "Another test snippet.",
        }
        mock_source_anchor.return_value = mock_anchor_instance
        
        result = get_claim_anchor(mock_db, "test-claim-456")
        
        assert result is not None
        assert result["doc_id"] == "doc-hash-def456"
        assert result["page_number"] == 3
        assert "bbox" in result

    def test_get_claim_anchor_not_found(self, mock_db):
        """Asserts get_claim_anchor returns None when claim not found."""
        from src.orchestrator.storage.arango import get_claim_anchor
        
        # Mock empty AQL query result
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = lambda self: iter([])
        mock_db.aql.execute.return_value = mock_cursor
        
        result = get_claim_anchor(mock_db, "nonexistent-claim")
        
        assert result is None

