"""
Pytest configuration and shared fixtures for Project Vyasa tests.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, patch

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from src.shared.config import (
    ARANGODB_DB,
    ARANGODB_PASSWORD,
    ARANGODB_USER,
    MEMORY_URL,
    QDRANT_URL,
)


@pytest.fixture
def mock_pdf_path(tmp_path: Path) -> Path:
    """Create a dummy PDF file for testing.
    
    Uses reportlab to generate a minimal PDF with some text content.
    The PDF is created in a temporary directory and cleaned up after tests.
    
    Args:
        tmp_path: Pytest temporary directory fixture.
        
    Returns:
        Path to the generated PDF file.
    """
    pdf_path = tmp_path / "test_document.pdf"
    
    # Create a simple PDF with reportlab
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    
    # Add some text to the PDF
    c.drawString(100, height - 100, "Test Document for Project Vyasa")
    c.drawString(100, height - 150, "This is a sample PDF for testing PDF parsing.")
    c.drawString(100, height - 200, "SQL injection is a vulnerability.")
    c.drawString(100, height - 250, "Input validation mitigates SQL injection.")
    
    c.save()
    
    return pdf_path


@pytest.fixture
def mock_brain():
    """Mock Brain (Logic) API responses.
    
    Brain returns high-level reasoning and JSON planning responses.
    Intercepts calls to http://cortex-brain:30000.
    
    Returns:
        Mock function that can be used to patch requests.post.
    """
    def _mock_response(*args, **kwargs):
        """Create a mock response for Brain service."""
        mock_resp = Mock()
        url = args[0] if args else kwargs.get('url', '')
        
        # Check if this is a Brain URL
        if 'cortex-brain' in url or ':30000' in url or '/v1/chat/completions' in url:
            json_data = kwargs.get('json', {})
            messages = json_data.get('messages', [])
            
            # Find system/user message
            content = ""
            for msg in messages:
                if msg.get('role') in ('user', 'system'):
                    content += msg.get('content', '')
            
            # Brain returns high-level reasoning/planning JSON
            if 'routing' in content.lower() or 'next_step' in content.lower():
                mock_resp.json.return_value = {
                    "choices": [{
                        "message": {
                            "content": json.dumps({
                                "next_step": "QUERY_MEMORY",
                                "reasoning": "User needs information from knowledge graph"
                            })
                        }
                    }]
                }
            else:
                # Default planning response
                mock_resp.json.return_value = {
                    "choices": [{
                        "message": {
                            "content": json.dumps({
                                "plan": "extract_and_validate",
                                "steps": ["extract", "validate", "save"]
                            })
                        }
                    }]
                }
        else:
            mock_resp.json.return_value = {"text": "{}"}
        
        mock_resp.raise_for_status = Mock()
        mock_resp.status_code = 200
        return mock_resp
    
    return _mock_response


@pytest.fixture
def mock_worker():
    """Mock Worker (Extraction) API responses.
    
    Worker returns strict JSON extraction (triples, entities).
    Intercepts calls to http://cortex-worker:30001.
    
    Returns:
        Mock function that can be used to patch requests.post.
    """
    def _mock_response(*args, **kwargs):
        """Create a mock response for Worker service."""
        mock_resp = Mock()
        url = args[0] if args else kwargs.get('url', '')
        
        # Check if this is a Worker URL
        if 'cortex-worker' in url or ':30001' in url or '/v1/chat/completions' in url:
            json_data = kwargs.get('json', {})
            messages = json_data.get('messages', [])
            
            # Find user message
            user_content = ""
            for msg in messages:
                if msg.get('role') == 'user':
                    user_content = msg.get('content', '')
                    break
            
            # Worker returns strict JSON extraction
            if 'SQL injection' in user_content or 'vulnerability' in user_content.lower():
                mock_resp.json.return_value = {
                    "choices": [{
                        "message": {
                            "content": json.dumps({
                                "triples": [
                                    {
                                        "subject": "Input validation",
                                        "predicate": "mitigates",
                                        "object": "SQL injection",
                                        "confidence": 0.9,
                                        "evidence": "Input validation mitigates SQL injection."
                                    }
                                ],
                                "entities": [
                                    {"name": "SQL injection", "type": "Vulnerability"},
                                    {"name": "Input validation", "type": "Mechanism"}
                                ]
                            })
                        }
                    }]
                }
            elif 'validate' in user_content.lower() or 'critique' in user_content.lower():
                # Validation response
                mock_resp.json.return_value = {
                    "choices": [{
                        "message": {
                            "content": json.dumps({
                                "status": "pass",
                                "critiques": []
                            })
                        }
                    }]
                }
            else:
                # Default empty extraction
                mock_resp.json.return_value = {
                    "choices": [{
                        "message": {
                            "content": json.dumps({
                                "triples": [],
                                "entities": []
                            })
                        }
                    }]
                }
        else:
            mock_resp.json.return_value = {"text": "{}"}
        
        mock_resp.raise_for_status = Mock()
        mock_resp.status_code = 200
        return mock_resp
    
    return _mock_response


@pytest.fixture
def mock_vision():
    """Mock Vision (Eye) API responses.
    
    Vision returns descriptions and data points with confidence scores.
    Intercepts calls to http://cortex-vision:30002.
    
    Returns:
        Mock function that can be used to patch requests.post.
    """
    def _mock_response(*args, **kwargs):
        """Create a mock response for Vision service."""
        mock_resp = Mock()
        url = args[0] if args else kwargs.get('url', '')
        
        # Check if this is a Vision URL
        if 'cortex-vision' in url or ':30002' in url or '/v1/chat/completions' in url:
            # Vision returns description + data points
            mock_resp.json.return_value = {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "description": "Extracted knowledge graph with security vulnerabilities and mitigations",
                            "data_points": [
                                {
                                    "type": "triple",
                                    "subject": "Input validation",
                                    "predicate": "mitigates",
                                    "object": "SQL injection",
                                    "confidence_score": 0.9
                                },
                                {
                                    "type": "triple",
                                    "subject": "Weak password",
                                    "predicate": "causes",
                                    "object": "Account breach",
                                    "confidence_score": 0.3  # Low confidence - should be filtered
                                },
                                {
                                    "type": "entity",
                                    "name": "SQL injection",
                                    "confidence_score": 0.85
                                }
                            ]
                        })
                    }
                }]
            }
        else:
            mock_resp.json.return_value = {"text": "{}"}
        
        mock_resp.raise_for_status = Mock()
        mock_resp.status_code = 200
        return mock_resp
    
    return _mock_response


@pytest.fixture
def mock_cortex(mock_worker):
    """Legacy fixture for backward compatibility.
    
    Returns mock_worker by default (most common use case).
    """
    return mock_worker


@pytest.fixture
def real_arango():
    """Fixture for real ArangoDB connection (requires running database).
    
    This fixture connects to a real ArangoDB instance using environment
    variables from deploy/.env. Mark tests using this with @pytest.mark.integration.
    
    Yields:
        ArangoDB database connection object.
        
    Raises:
        pytest.skip: If ArangoDB is not available or credentials are missing.
        
    Example:
        ```python
        @pytest.mark.integration
        def test_arango_write(real_arango):
            db = real_arango
            # Test code
        ```
    """
    try:
        from arango import ArangoClient
        
        # Get connection details from environment
        url = os.getenv("MEMORY_URL", MEMORY_URL)
        db_name = os.getenv("ARANGODB_DB", ARANGODB_DB)
        username = os.getenv("ARANGODB_USER", ARANGODB_USER)
        password = os.getenv("ARANGODB_PASSWORD", ARANGODB_PASSWORD) or os.getenv("ARANGO_ROOT_PASSWORD", "")
        
        if not password:
            pytest.skip("ArangoDB password not configured (set ARANGODB_PASSWORD or ARANGO_ROOT_PASSWORD)")
        
        client = ArangoClient(hosts=url)
        
        # Try to connect
        try:
            db = client.db(db_name, username=username, password=password)
            # Test connection with a simple query
            db.version()
            yield db
        except Exception as e:
            pytest.skip(f"ArangoDB not available: {e}")
    except ImportError:
        pytest.skip("python-arango not installed")
    except Exception as e:
        pytest.skip(f"ArangoDB connection failed: {e}")


@pytest.fixture
def real_qdrant():
    """Fixture for real Qdrant connection (requires running database).
    
    This fixture connects to a real Qdrant instance using environment
    variables. Mark tests using this with @pytest.mark.integration.
    
    Yields:
        QdrantClient instance.
        
    Raises:
        pytest.skip: If Qdrant is not available.
        
    Example:
        ```python
        @pytest.mark.integration
        def test_qdrant_collection(real_qdrant):
            client = real_qdrant
            # Test code
        ```
    """
    try:
        from qdrant_client import QdrantClient
        
        url = os.getenv("QDRANT_URL", QDRANT_URL)
        api_key = os.getenv("QDRANT_API_KEY", "")
        
        try:
            client = QdrantClient(url=url, api_key=api_key if api_key else None)
            # Test connection
            client.get_collections()
            yield client
        except Exception as e:
            pytest.skip(f"Qdrant not available: {e}")
    except ImportError:
        pytest.skip("qdrant-client not installed")
    except Exception as e:
        pytest.skip(f"Qdrant connection failed: {e}")

