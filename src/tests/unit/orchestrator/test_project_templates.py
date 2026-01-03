"""
Unit tests for project templates endpoint.

Tests:
- GET /api/projects/templates returns list of templates
- Templates have required fields
- Templates are valid JSON
"""

import json
from unittest.mock import patch, MagicMock
import pytest

from src.orchestrator.server import app


@pytest.fixture
def client():
    """Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_list_templates_returns_list(client):
    """GET /api/projects/templates returns a list of templates."""
    response = client.get("/api/projects/templates")
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) > 0


def test_templates_have_required_fields(client):
    """Each template has all required fields."""
    response = client.get("/api/projects/templates")
    
    assert response.status_code == 200
    templates = json.loads(response.data)
    
    required_fields = ["id", "name", "description", "suggested_rqs", "suggested_anti_scope", "suggested_rigor"]
    
    for template in templates:
        for field in required_fields:
            assert field in template, f"Template {template.get('id', 'unknown')} missing field: {field}"


def test_templates_have_valid_structure(client):
    """Templates have correct data types for each field."""
    response = client.get("/api/projects/templates")
    
    assert response.status_code == 200
    templates = json.loads(response.data)
    
    for template in templates:
        assert isinstance(template["id"], str)
        assert isinstance(template["name"], str)
        assert isinstance(template["description"], str)
        assert isinstance(template["suggested_rqs"], list)
        assert isinstance(template["suggested_anti_scope"], list)
        assert isinstance(template["suggested_rigor"], str)
        assert template["suggested_rigor"] in ("exploratory", "conservative")
        
        # Validate RQs are strings
        for rq in template["suggested_rqs"]:
            assert isinstance(rq, str)
        
        # Validate anti-scope are strings
        for scope in template["suggested_anti_scope"]:
            assert isinstance(scope, str)
        
        # example_thesis is optional but should be string if present
        if "example_thesis" in template:
            assert isinstance(template["example_thesis"], str)


def test_templates_include_known_templates(client):
    """Response includes expected default templates."""
    response = client.get("/api/projects/templates")
    
    assert response.status_code == 200
    templates = json.loads(response.data)
    
    template_ids = [t["id"] for t in templates]
    
    # Check for some expected templates
    expected_templates = ["security-analysis", "performance-optimization", "ml-model-evaluation"]
    for expected_id in expected_templates:
        assert expected_id in template_ids, f"Expected template {expected_id} not found"


def test_templates_endpoint_handles_errors_gracefully(client):
    """Endpoint handles errors without crashing."""
    # Mock get_all_templates to raise an exception
    with patch("src.project.templates.get_all_templates", side_effect=Exception("Test error")):
        # The endpoint should catch the exception and return 500
        response = client.get("/api/projects/templates")
        
        # Should return error response
        assert response.status_code == 500
        data = json.loads(response.data)
        assert "error" in data


def test_templates_are_json_serializable(client):
    """Templates can be serialized to JSON without errors."""
    response = client.get("/api/projects/templates")
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Try to serialize back to JSON (should not raise)
    json_str = json.dumps(data)
    assert isinstance(json_str, str)
    assert len(json_str) > 0

