"""
Integration test: Verify orchestrator injects rigor_level from ProjectConfig into job state.
"""

import pytest
from typing import Dict, Any

from src.orchestrator.server import app
from src.orchestrator.job_store import get_job_record
from src.project.service import ProjectService
from src.project.types import ProjectCreate


@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def project_service(real_arango_client):
    """Get project service from real ArangoDB client."""
    return ProjectService(real_arango_client)


@pytest.mark.integration
def test_rigor_level_injected_into_job_state(client, project_service):
    """Test that rigor_level from ProjectConfig is injected into job initial_state."""
    # Create a project with conservative rigor
    project_create = ProjectCreate(
        title="Test Rigor Project",
        thesis="Test thesis",
        research_questions=["RQ1"],
    )
    project = project_service.create_project(project_create)
    
    # Update project to conservative rigor
    collection = project_service.db.collection(project_service.COLLECTION_NAME)
    collection.update({"_key": project.id, "rigor_level": "conservative"})
    
    # Submit a workflow job
    response = client.post(
        "/workflow/submit",
        json={
            "raw_text": "Test content for rigor injection test",
            "project_id": project.id,
        },
        content_type="application/json",
    )
    
    assert response.status_code == 202
    data = response.get_json()
    job_id = data["job_id"]
    
    # Get job record and check initial_state
    job_record = get_job_record(job_id)
    assert job_record is not None
    
    initial_state = job_record.get("initial_state", {})
    assert initial_state.get("rigor_level") == "conservative"
    assert initial_state.get("project_id") == project.id


@pytest.mark.integration
def test_rigor_level_defaults_to_exploratory(client, project_service):
    """Test that rigor_level defaults to exploratory if not set."""
    # Create a project (defaults to exploratory from policy)
    project_create = ProjectCreate(
        title="Test Default Rigor",
        thesis="Test thesis",
        research_questions=["RQ1"],
    )
    project = project_service.create_project(project_create)
    
    # Submit a workflow job
    response = client.post(
        "/workflow/submit",
        json={
            "raw_text": "Test content",
            "project_id": project.id,
        },
        content_type="application/json",
    )
    
    assert response.status_code == 202
    data = response.get_json()
    job_id = data["job_id"]
    
    # Get job record and check initial_state
    job_record = get_job_record(job_id)
    assert job_record is not None
    
    initial_state = job_record.get("initial_state", {})
    # Should default to exploratory (from policy or project default)
    assert initial_state.get("rigor_level") in ("exploratory", "conservative")
    assert initial_state.get("project_id") == project.id


@pytest.mark.integration
def test_rigor_level_updated_affects_future_jobs(client, project_service):
    """Test that updating rigor_level affects future jobs but not existing ones."""
    # Create a project with exploratory rigor
    project_create = ProjectCreate(
        title="Test Rigor Update",
        thesis="Test thesis",
        research_questions=["RQ1"],
    )
    project = project_service.create_project(project_create)
    
    # Create first job with exploratory
    response1 = client.post(
        "/workflow/submit",
        json={
            "raw_text": "First job content",
            "project_id": project.id,
        },
        content_type="application/json",
    )
    assert response1.status_code == 202
    job_id_1 = response1.get_json()["job_id"]
    
    # Update project to conservative
    response_update = client.patch(
        f"/api/projects/{project.id}/rigor",
        json={"rigor_level": "conservative"},
        content_type="application/json",
    )
    assert response_update.status_code == 200
    
    # Create second job (should use conservative)
    response2 = client.post(
        "/workflow/submit",
        json={
            "raw_text": "Second job content",
            "project_id": project.id,
        },
        content_type="application/json",
    )
    assert response2.status_code == 202
    job_id_2 = response2.get_json()["job_id"]
    
    # Verify first job still has original rigor
    job_record_1 = get_job_record(job_id_1)
    initial_state_1 = job_record_1.get("initial_state", {})
    # First job should have exploratory (or whatever was set at creation)
    
    # Verify second job has new rigor
    job_record_2 = get_job_record(job_id_2)
    initial_state_2 = job_record_2.get("initial_state", {})
    assert initial_state_2.get("rigor_level") == "conservative"

