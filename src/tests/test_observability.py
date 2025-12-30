"""
Unit tests for observability features: health endpoint and structured logging.

What's covered:
- GET /health: Returns 200 and expected JSON schema
- GET /health?deep=true: Mocks ArangoDB and Worker health checks
- GET /health?deep=true: Returns 503 if dependency is down
- Structured Logger: JSON format output with context binding
- Structured Logger: project_id promotion to top-level JSON

All external dependencies are mocked (ArangoDB, requests, environment variables).
"""

import json
import os
import sys
from io import StringIO
from unittest.mock import Mock, patch, MagicMock
import pytest

from src.orchestrator.server import app
from src.shared.logger import get_logger


@pytest.fixture
def client():
    """Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_project_service():
    """Mock ProjectService instance."""
    service = Mock()
    service.get_project = Mock()
    return service


def test_health_endpoint_quick_check(client):
    """GET /health returns 200 and expected JSON schema."""
    response = client.get('/health')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert "status" in data
    assert data["status"] == "healthy"
    assert "service" in data
    assert data["service"] == "orchestrator"
    assert "version" in data


def test_health_endpoint_deep_check_all_healthy(client, mock_project_service):
    """GET /health?deep=true returns 200 when all dependencies are healthy."""
    # Mock ArangoDB connection
    mock_db = Mock()
    mock_db.version.return_value = "3.11.0"
    mock_client = Mock()
    mock_client.db.return_value = mock_db
    
    # Mock Worker health check
    mock_response = Mock()
    mock_response.status_code = 200
    
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        with patch('src.orchestrator.server.ArangoClient', return_value=mock_client):
            with patch('src.orchestrator.server.requests.get', return_value=mock_response):
                response = client.get('/health?deep=true')
                
                assert response.status_code == 200
                data = json.loads(response.data)
                
                assert "status" in data
                assert data["status"] == "healthy"
                assert "dependencies" in data
                assert data["dependencies"]["arango"] == "ok"
                assert data["dependencies"]["worker"] == "ok"


def test_health_endpoint_deep_check_arango_down(client):
    """GET /health?deep=true returns 503 when ArangoDB is down."""
    # Mock ArangoDB connection failure
    mock_client = Mock()
    mock_client.db.side_effect = Exception("Connection refused")
    
    # Mock Worker health check (healthy)
    mock_response = Mock()
    mock_response.status_code = 200
    
    with patch('src.orchestrator.server.get_project_service', return_value=None):
        with patch('src.orchestrator.server.ArangoClient', return_value=mock_client):
            with patch('src.orchestrator.server.requests.get', return_value=mock_response):
                response = client.get('/health?deep=true')
                
                assert response.status_code == 503
                data = json.loads(response.data)
                
                assert "status" in data
                assert data["status"] == "unhealthy"
                assert "dependencies" in data
                assert data["dependencies"]["arango"] == "error"
                assert data["dependencies"]["worker"] == "ok"


def test_health_endpoint_deep_check_worker_down(client, mock_project_service):
    """GET /health?deep=true returns 503 when Worker is down."""
    # Mock ArangoDB connection (healthy)
    mock_db = Mock()
    mock_db.version.return_value = "3.11.0"
    mock_client = Mock()
    mock_client.db.return_value = mock_db
    
    # Mock Worker health check failure
    with patch('src.orchestrator.server.get_project_service', return_value=mock_project_service):
        with patch('src.orchestrator.server.ArangoClient', return_value=mock_client):
            with patch('src.orchestrator.server.requests.get', side_effect=Exception("Connection refused")):
                response = client.get('/health?deep=true')
                
                assert response.status_code == 503
                data = json.loads(response.data)
                
                assert "status" in data
                assert data["status"] == "unhealthy"
                assert "dependencies" in data
                assert data["dependencies"]["arango"] == "ok"
                assert data["dependencies"]["worker"] == "error"


def test_health_endpoint_deep_check_both_down(client):
    """GET /health?deep=true returns 503 when both dependencies are down."""
    # Mock ArangoDB connection failure
    mock_client = Mock()
    mock_client.db.side_effect = Exception("Connection refused")
    
    # Mock Worker health check failure
    with patch('src.orchestrator.server.get_project_service', return_value=None):
        with patch('src.orchestrator.server.ArangoClient', return_value=mock_client):
            with patch('src.orchestrator.server.requests.get', side_effect=Exception("Connection refused")):
                response = client.get('/health?deep=true')
                
                assert response.status_code == 503
                data = json.loads(response.data)
                
                assert "status" in data
                assert data["status"] == "unhealthy"
                assert "dependencies" in data
                assert data["dependencies"]["arango"] == "error"
                assert data["dependencies"]["worker"] == "error"


def test_structured_logger_json_format():
    """Structured logger outputs valid JSON when LOG_FORMAT=json."""
    # Set environment variable
    with patch.dict(os.environ, {"LOG_FORMAT": "json"}):
        # Reload logger module to pick up new format
        import importlib
        import src.shared.logger
        importlib.reload(src.shared.logger)
        
        # Capture stdout
        captured_output = StringIO()
        logger = src.shared.logger.get_logger("test_service", "test_logger")
        
        # Replace handler's stream
        for handler in logger.handlers:
            handler.stream = captured_output
        
        # Log with context
        logger.info(
            "Test event",
            extra={
                "payload": {
                    "project_id": "test_1",
                    "data": "test_data"
                }
            }
        )
        
        # Verify output is valid JSON
        output = captured_output.getvalue().strip()
        log_data = json.loads(output)
        
        assert "timestamp" in log_data
        assert "service" in log_data
        assert log_data["service"] == "test_service"
        assert "level" in log_data
        assert log_data["level"] == "INFO"
        assert "message" in log_data
        assert log_data["message"] == "Test event"
        
        # Verify context binding: project_id promoted to top-level
        assert "project_id" in log_data
        assert log_data["project_id"] == "test_1"
        assert "data" in log_data
        assert log_data["data"] == "test_data"


def test_structured_logger_project_id_promotion():
    """Structured logger promotes project_id to top-level JSON field."""
    with patch.dict(os.environ, {"LOG_FORMAT": "json"}):
        import importlib
        import src.shared.logger
        importlib.reload(src.shared.logger)
        
        captured_output = StringIO()
        logger = src.shared.logger.get_logger("test_service", "test_logger")
        
        for handler in logger.handlers:
            handler.stream = captured_output
        
        # Log with project_id directly in extra
        logger.info(
            "Job started",
            extra={
                "project_id": "test_2",
                "job_id": "job-123",
                "duration_ms": 150
            }
        )
        
        output = captured_output.getvalue().strip()
        log_data = json.loads(output)
        
        # Verify promotion to top-level
        assert "project_id" in log_data
        assert log_data["project_id"] == "test_2"
        assert "job_id" in log_data
        assert log_data["job_id"] == "job-123"
        assert "duration_ms" in log_data
        assert log_data["duration_ms"] == 150


def test_structured_logger_text_format():
    """Structured logger outputs text when LOG_FORMAT=text."""
    with patch.dict(os.environ, {"LOG_FORMAT": "text"}):
        import importlib
        import src.shared.logger
        importlib.reload(src.shared.logger)
        
        captured_output = StringIO()
        logger = src.shared.logger.get_logger("test_service", "test_logger")
        
        for handler in logger.handlers:
            handler.stream = captured_output
        
        logger.info("Test event", extra={"project_id": "test_3"})
        
        output = captured_output.getvalue().strip()
        
        # Verify text format (not JSON)
        assert output.startswith("20")  # Timestamp
        assert "test_service" in output
        assert "INFO" in output
        assert "Test event" in output
        assert not output.startswith("{")  # Not JSON


def test_structured_logger_exception_handling():
    """Structured logger includes exception info in JSON format."""
    with patch.dict(os.environ, {"LOG_FORMAT": "json"}):
        import importlib
        import src.shared.logger
        importlib.reload(src.shared.logger)
        
        captured_output = StringIO()
        logger = src.shared.logger.get_logger("test_service", "test_logger")
        
        for handler in logger.handlers:
            handler.stream = captured_output
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.error("Error occurred", exc_info=True)
        
        output = captured_output.getvalue().strip()
        log_data = json.loads(output)
        
        assert "exception" in log_data
        assert "ValueError" in log_data["exception"]
        assert "Test exception" in log_data["exception"]

