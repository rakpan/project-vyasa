"""
Pytest configuration and shared fixtures for Project Vyasa tests.

**Patching Strategy: "Patch the Source, Not the Consumer"**

All mocks in this file follow the principle of patching at the source library/module,
not at downstream consumers. This prevents AttributeError crashes when modules
don't expose imported classes/functions as module-level attributes.

Examples:
- ✅ GOOD: `monkeypatch.setattr('arango.ArangoClient', ...)` - patches the source library
- ✅ GOOD: `monkeypatch.setattr('requests.get', ...)` - patches the source library
- ❌ BAD: `monkeypatch.setattr('src.orchestrator.nodes.ArangoClient', ...)` - patches downstream consumer
- ❌ BAD: `monkeypatch.setattr('src.orchestrator.collectors.sglang_metrics.requests.get', ...)` - patches downstream consumer

Exception: Patching our own functions/constants (e.g., `src.shared.config.get_arango_url`)
is acceptable because we're patching the source definition, not a consumer.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Tuple
from unittest.mock import Mock, MagicMock, patch

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

import pytest

pytest.importorskip("fastapi")

from src.shared.config import (
    ARANGODB_DB,
    ARANGODB_PASSWORD,
    ARANGODB_USER,
    MEMORY_URL,
    QDRANT_URL,
)


# Note: Autouse mocking fixtures have been moved to src/tests/unit/conftest.py
# This file now contains only shared utilities that can be used by both unit and integration tests.


# Note: mock_llm_client and mock_arango_db are now provided by src/tests/unit/conftest.py
# as autouse fixtures. They are available to unit tests automatically.
# Integration tests should use real_arango and real_qdrant from src/tests/integration/conftest.py


@pytest.fixture
def base_node_state() -> Dict[str, Any]:
    """Base state dictionary with all standard required fields for node tests.
    
    This fixture provides a complete state dictionary that satisfies
    all common node requirements, preventing KeyError and ValueError crashes.
    
    Returns:
        Dictionary with all standard required fields:
        - url: Mock source URL
        - raw_text: Dummy text for extraction
        - project_id: Test project ID
        - job_id: Test job ID
        - jobId: Test job ID (camelCase)
        - threadId: Test thread ID
        - manifest: Empty manifest dict
        - triples: Empty triples list
        - extracted_json: Empty extracted JSON structure
        - manuscript_blocks: Empty blocks list
    """
    return {
        "url": "http://mock-source.com",
        "raw_text": "dummy text for extraction",
        "project_id": "p1",
        "job_id": "j1",
        "jobId": "j1",
        "threadId": "j1",
        "manifest": {},
        "triples": [],
        "extracted_json": {"triples": []},
        "manuscript_blocks": [],
        "critiques": [],
        "revision_count": 0,
    }


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


# Note: real_arango and real_qdrant fixtures have been moved to src/tests/integration/conftest.py
# They are available to integration tests automatically.
