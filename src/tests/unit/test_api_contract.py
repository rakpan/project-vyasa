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


@pytest.fixture
def client():
    """Flask test client for API contract tests."""
    return server.app.test_client()


def test_upload_validation_rejects_non_pdf(client):
    """Uploading non-PDF file should return 400 immediately (validation happens before processing).
    
    This is a UNIT TEST that verifies the endpoint's validation logic.
    The endpoint validates file extension early (line 356) and should return 400
    without attempting to process the file or connect to the database.
    
    Note: The firewall (conftest.py) mocks get_project_service() to prevent
    database connections, but this test should not reach that code path since
    validation happens first.
    """
    data = {
        "file": (io.BytesIO(b"hello"), "test.txt"),
    }
    # The endpoint should validate file extension and return 400 immediately
    # It should NOT attempt to process the file or connect to the database
    resp = client.post("/ingest/pdf", data=data, content_type="multipart/form-data")
    # Validation should catch non-PDF and return 400 (not 500 from processing)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "pdf" in data["error"].lower() or "format" in data["error"].lower()


def test_workflow_process_missing_payload(client):
    resp = client.post("/workflow/process", json={})
    # Endpoint requires raw_text -> 400
    assert resp.status_code == 400
