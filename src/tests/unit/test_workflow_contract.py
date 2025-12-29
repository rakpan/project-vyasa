"""
Contract tests for orchestrator /workflow/process API.

These tests ensure the response always includes extracted_json.triples and
handles missing/empty inputs gracefully.
"""

import json

import pytest

from ...orchestrator import server
from ...orchestrator.job_manager import create_job, set_job_result
from ...orchestrator.state import JobStatus
from ...orchestrator.normalize import normalize_extracted_json


@pytest.fixture
def client(monkeypatch):
    """Flask test client with workflow invocation mocked."""
    return server.app.test_client()


def test_workflow_process_requires_raw_text(client):
    resp = client.post("/workflow/process", json={})
    assert resp.status_code == 400
    assert "raw_text" in resp.get_json().get("error", "").lower()


def test_workflow_result_normalizes_triples(monkeypatch, client):
    """Result endpoint should always contain extracted_json.triples."""
    # Create a fake job and set result without triples
    initial_state = {"raw_text": "Test"}
    job_id = create_job(initial_state)
    raw_result = {"extracted_json": {"relations": [{"subject": "A", "predicate": "rel", "object": "B"}]}}
    set_job_result(job_id, raw_result)

    resp = client.get(f"/workflow/result/{job_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "result" in data
    assert "extracted_json" in data["result"]
    assert "triples" in data["result"]["extracted_json"]
    assert len(data["result"]["extracted_json"]["triples"]) == 1


def test_workflow_result_returns_202_when_running(client):
    initial_state = {"raw_text": "Test"}
    job_id = create_job(initial_state)
    # Mark job as running
    from ...orchestrator.job_manager import update_job_status
    update_job_status(job_id, JobStatus.RUNNING, progress=0.5)

    resp = client.get(f"/workflow/result/{job_id}")
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["status"] in (JobStatus.RUNNING.value, "RUNNING")
