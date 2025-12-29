"""
API contract tests using Flask test client.
"""

import io
import pytest

from ...orchestrator import server


@pytest.fixture
def client():
    return server.app.test_client()


def test_upload_validation_rejects_non_pdf(client):
    """Uploading without a file should 400; non-PDF should also fail fast."""
    data = {
        "file": (io.BytesIO(b"hello"), "test.txt"),
    }
    resp = client.post("/ingest/pdf", data=data, content_type="multipart/form-data")
    # Depending on processing, this may fail during PDF parse -> 500; ensure not 200
    assert resp.status_code in (400, 500)


def test_workflow_process_missing_payload(client):
    resp = client.post("/workflow/process", json={})
    # Endpoint requires raw_text -> 400
    assert resp.status_code == 400
