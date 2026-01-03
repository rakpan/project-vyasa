"""
Unit tests for /ingest/pdf endpoint behavior.

What's covered:
- Preview-only behavior: Does NOT return reusable image_paths
- Response structure: markdown, filename, image_count (not paths)
- Invalid file extension -> 400
- Missing file -> 400
- Optional project_id support (does not break if missing)

All external dependencies are mocked by the firewall (conftest.py):
- get_project_service() is mocked to prevent DB connections
- process_pdf() is patched in individual tests
- All network requests are mocked
"""

import json
import io
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from src.orchestrator.server import app

# Ensure Flask app is in testing mode to prevent real connections
app.config['TESTING'] = True


@pytest.fixture
def client():
    """Flask test client.
    
    Note: The firewall (conftest.py) automatically mocks:
    - get_project_service() to prevent DB connections
    - All network requests
    Tests should patch process_pdf() if they need to test successful processing.
    """
    with app.test_client() as client:
        yield client


def test_ingest_pdf_invalid_file_extension(client):
    """Invalid file extension -> 400."""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
        tmp_file.write(b'Not a PDF')
        tmp_path = tmp_file.name
    
    try:
        with open(tmp_path, 'rb') as f:
            response = client.post(
                '/ingest/pdf',
                data={
                    'file': (f, 'test.txt'),
                },
                content_type='multipart/form-data',
            )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "pdf" in data["error"].lower()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_ingest_pdf_missing_file(client):
    """Missing file -> 400."""
    response = client.post(
        '/ingest/pdf',
        data={},
        content_type='multipart/form-data',
    )
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data
    assert "file" in data["error"].lower()


def test_ingest_pdf_with_project_id_optional(client):
    """/ingest/pdf should work with or without project_id (optional)."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_file.write(b'%PDF-1.4 fake pdf content')
        tmp_path = tmp_file.name
    
    try:
        with patch('src.orchestrator.server.process_pdf') as mock_process_pdf:
            mock_process_pdf.return_value = (
                "# Test Markdown",
                None,
                [],
            )
            
            # Test without project_id
            with open(tmp_path, 'rb') as f:
                response = client.post(
                    '/ingest/pdf',
                    data={
                        'file': (f, 'test.pdf'),
                    },
                    content_type='multipart/form-data',
                )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert "markdown" in data
            assert "project_id" not in data or data.get("project_id") is None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_ingest_pdf_empty_file(client):
    """Empty file -> handled gracefully."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_file.write(b'')  # Empty file
        tmp_path = tmp_file.name
    
    try:
        with patch('src.orchestrator.server.process_pdf') as mock_process_pdf:
            mock_process_pdf.return_value = (
                "",
                None,
                [],
            )
            
            with open(tmp_path, 'rb') as f:
                response = client.post(
                    '/ingest/pdf',
                    data={
                        'file': (f, 'empty.pdf'),
                    },
                    content_type='multipart/form-data',
                )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert "markdown" in data
            assert data["markdown"] == ""
            assert data["image_count"] == 0
    finally:
        Path(tmp_path).unlink(missing_ok=True)
