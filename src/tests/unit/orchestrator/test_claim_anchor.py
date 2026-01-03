"""
Unit tests for claim anchor functionality.

Tests ensure:
1. Extracted claims have source_anchor
2. Anchor endpoint returns stable shape
3. source_pointer to source_anchor conversion works correctly
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.orchestrator.utils.source_anchor import (
    source_pointer_to_anchor,
    add_source_anchor_to_triple,
    add_source_anchor_to_triples,
)
from src.orchestrator.api.claims import get_claim_anchor


class TestSourceAnchorConversion:
    """Test source_pointer to source_anchor conversion."""
    
    def test_source_pointer_to_anchor_with_bbox(self):
        """Test conversion with bbox."""
        source_pointer = {
            "doc_hash": "abc123def456",
            "page": 5,
            "bbox": [100, 200, 300, 400],
            "snippet": "Some evidence text",
        }
        
        anchor = source_pointer_to_anchor(source_pointer)
        
        assert anchor is not None
        assert anchor["doc_id"] == "abc123def456"
        assert anchor["page_number"] == 5
        assert "bbox" in anchor
        assert anchor["bbox"]["x"] == 100.0
        assert anchor["bbox"]["y"] == 200.0
        assert anchor["bbox"]["w"] == 200.0  # 300 - 100
        assert anchor["bbox"]["h"] == 200.0  # 400 - 200
        assert "span" in anchor
        assert anchor["span"]["start"] == 0
        assert anchor["span"]["end"] == len("Some evidence text")
        assert anchor["snippet"] == "Some evidence text"
    
    def test_source_pointer_to_anchor_without_bbox(self):
        """Test conversion without bbox."""
        source_pointer = {
            "doc_hash": "xyz789",
            "page": 10,
            "snippet": "Evidence",
        }
        
        anchor = source_pointer_to_anchor(source_pointer)
        
        assert anchor is not None
        assert anchor["doc_id"] == "xyz789"
        assert anchor["page_number"] == 10
        assert "bbox" not in anchor
        assert "span" in anchor
    
    def test_source_pointer_to_anchor_invalid(self):
        """Test conversion with invalid source_pointer."""
        # Missing doc_hash
        assert source_pointer_to_anchor({"page": 1}) is None
        
        # Missing page
        assert source_pointer_to_anchor({"doc_hash": "abc123"}) is None
        
        # None input
        assert source_pointer_to_anchor(None) is None
    
    def test_add_source_anchor_to_triple(self):
        """Test adding source_anchor to a triple."""
        triple = {
            "subject": "A",
            "predicate": "relates",
            "object": "B",
            "source_pointer": {
                "doc_hash": "abc123",
                "page": 1,
                "bbox": [0, 0, 100, 100],
                "snippet": "Evidence",
            },
        }
        
        result = add_source_anchor_to_triple(triple)
        
        assert "source_anchor" in result
        assert result["source_anchor"]["doc_id"] == "abc123"
        assert result["source_anchor"]["page_number"] == 1
    
    def test_add_source_anchor_to_triple_no_pointer(self):
        """Test adding source_anchor when source_pointer is missing."""
        triple = {
            "subject": "A",
            "predicate": "relates",
            "object": "B",
        }
        
        result = add_source_anchor_to_triple(triple)
        
        # Should not add source_anchor if source_pointer is missing
        assert "source_anchor" not in result
    
    def test_add_source_anchor_to_triples(self):
        """Test adding source_anchor to multiple triples."""
        triples = [
            {
                "subject": "A",
                "predicate": "relates",
                "object": "B",
                "source_pointer": {
                    "doc_hash": "abc123",
                    "page": 1,
                    "bbox": [0, 0, 100, 100],
                },
            },
            {
                "subject": "C",
                "predicate": "causes",
                "object": "D",
                # No source_pointer
            },
        ]
        
        result = add_source_anchor_to_triples(triples)
        
        assert len(result) == 2
        assert "source_anchor" in result[0]
        assert "source_anchor" not in result[1]


class TestClaimAnchorEndpoint:
    """Test GET /api/claims/{claim_id}/anchor endpoint."""
    
    @patch("src.orchestrator.api.claims.ArangoClient")
    def test_get_claim_anchor_from_canonical(self, mock_arango_client):
        """Test getting anchor from canonical_knowledge."""
        from src.orchestrator.api.claims import claims_bp
        
        # Mock database
        mock_client = Mock()
        mock_db = Mock()
        mock_client.db.return_value = mock_db
        mock_arango_client.return_value = mock_client
        
        mock_db.has_collection.return_value = True
        mock_db.aql.execute.return_value = [
            {
                "claim_id": "claim_123",
                "source_pointers": [
                    {
                        "doc_hash": "abc123",
                        "page": 5,
                        "bbox": [100, 200, 300, 400],
                        "snippet": "Evidence",
                    }
                ],
            }
        ]
        
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(claims_bp)
        
        with app.test_client() as client:
            response = client.get("/api/claims/claim_123/anchor")
        
        assert response.status_code == 200
        data = response.get_json()
        assert "claim_id" in data
        assert "source_anchor" in data
        assert data["source_anchor"]["doc_id"] == "abc123"
        assert data["source_anchor"]["page_number"] == 5
    
    @patch("src.orchestrator.api.claims.ArangoClient")
    def test_get_claim_anchor_not_found(self, mock_arango_client):
        """Test getting anchor for non-existent claim."""
        from src.orchestrator.api.claims import claims_bp
        
        mock_client = Mock()
        mock_db = Mock()
        mock_client.db.return_value = mock_db
        mock_arango_client.return_value = mock_client
        
        mock_db.has_collection.return_value = True
        mock_db.aql.execute.return_value = []  # No results
        
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(claims_bp)
        
        with app.test_client() as client:
            response = client.get("/api/claims/nonexistent/anchor")
        
        assert response.status_code == 404

