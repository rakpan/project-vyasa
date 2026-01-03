"""
API contract tests using Flask test client.

These tests verify API contract behavior (status codes, error messages) without
requiring real database connections or file processing. All external I/O is
mocked by the unit test firewall (src/tests/unit/conftest.py).
"""

import io
import pytest
from unittest.mock import patch

from ...orchestrator import server

# Ensure Flask app is in testing mode to prevent real connections
server.app.config['TESTING'] = True


@pytest.fixture
def client():
    """Flask test client for API contract tests.
    
    Note: The firewall (conftest.py) automatically mocks:
    - get_project_service() to prevent DB connections
    - process_pdf() is not called in this test (validation happens first)
    - All network requests are mocked
    """
    return server.app.test_client()


def test_workflow_process_missing_payload(client):
    resp = client.post("/workflow/process", json={})
    # Endpoint requires raw_text -> 400
    assert resp.status_code == 400
