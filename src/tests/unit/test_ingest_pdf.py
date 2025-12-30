"""
Unit tests for /ingest/pdf endpoint behavior.

What's covered:
- Preview-only behavior: Does NOT return reusable image_paths
- Response structure: markdown, filename, image_count (not paths)
- Invalid file extension -> 400
- Missing file -> 400
- Optional project_id support (does not break if missing)

All external dependencies are mocked (process_pdf).
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from src.orchestrator.server import app


@pytest.fixture
def client():
    """Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_ingest_pdf_preview_only_no_image_paths(client):
    """/ingest/pdf should return preview data without reusable image_paths."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_file.write(b'%PDF-1.4 fake pdf content')
        tmp_path = tmp_file.name
    
    try:
        with patch('src.orchestrator.server.process_pdf') as mock_process_pdf:
            mock_process_pdf.return_value = (
                "# Test Markdown",
                "/tmp/images",
                ["/tmp/images/img1.png", "/tmp/images/img2.png"],  # These should NOT be in response
            )
            
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
            
            # Verify response structure
            assert "markdown" in data
            assert data["markdown"] == "# Test Markdown"
            assert "filename" in data
            assert data["filename"] == "test.pdf"
            assert "image_count" in data
            assert data["image_count"] == 2
            
            # Critical: Should NOT return image_paths (temporary files are deleted)
            assert "image_paths" not in data
            assert "images_dir" not in data
            
            # Verify note about preview-only
            assert "note" in data
            assert "preview" in data["note"].lower()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


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

