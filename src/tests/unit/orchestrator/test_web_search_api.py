"""
Unit tests for Web Search API endpoints.

Tests verify:
- Search endpoint calls Google API correctly
- Queue endpoint filters unsafe URLs and creates ReviewTasks
- Error handling for missing configuration
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

from src.orchestrator.api.web_search import web_search_bp


@pytest.fixture
def app():
    """Create Flask app with web_search blueprint."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(web_search_bp)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestWebSearchSearch:
    """Tests for POST /api/web-search/search endpoint."""
    
    @patch("src.orchestrator.api.web_search.WORKBENCH_WEB_SEARCH_ENABLED", True)
    @patch("src.orchestrator.api.web_search.GOOGLE_SEARCH_API_KEY", "test-key")
    @patch("src.orchestrator.api.web_search.GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    @patch("src.orchestrator.api.web_search.requests.get")
    @patch("src.orchestrator.api.web_search.filter_urls_by_allowlist")
    @patch("src.orchestrator.api.web_search._extract_domain")
    @patch("src.orchestrator.api.web_search._compute_domain_quality_tier")
    @patch("src.orchestrator.api.web_search._compute_domain_quality_score")
    def test_search_success_with_allowlist(
        self, mock_quality_score, mock_quality_tier, mock_extract_domain, mock_filter, mock_get, client
    ):
        """Test successful search returns allowlisted results with quality scores."""
        # Mock Google API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "title": "Test Result",
                    "link": "https://fda.gov/page",
                    "snippet": "Test snippet",
                    "displayLink": "fda.gov",
                }
            ],
            "searchInformation": {
                "totalResults": "100",
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Mock allowlist filtering (fda.gov passes)
        mock_filter.return_value = ["https://fda.gov/page"]
        mock_extract_domain.return_value = "fda.gov"
        mock_quality_tier.return_value = "high"
        mock_quality_score.return_value = 0.9
        
        response = client.post(
            "/api/web-search/search",
            json={"query": "test query", "project_id": "test-project"},
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["title"] == "Test Result"
        assert data["results"][0]["quality_tier"] == "high"
        assert data["results"][0]["quality_score"] == 0.9
        assert data["total_results"] == 100
        
        # Verify allowlist filtering was applied
        mock_filter.assert_called_once()
        
        # Verify Google API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://www.googleapis.com/customsearch/v1"
        assert call_args[1]["params"]["key"] == "test-key"
        assert call_args[1]["params"]["cx"] == "test-cx"
        assert call_args[1]["params"]["q"] == "test query"
    
    @patch("src.orchestrator.api.web_search.WORKBENCH_WEB_SEARCH_ENABLED", True)
    @patch("src.orchestrator.api.web_search.GOOGLE_SEARCH_API_KEY", "test-key")
    @patch("src.orchestrator.api.web_search.GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    @patch("src.orchestrator.api.web_search.requests.get")
    @patch("src.orchestrator.api.web_search.filter_urls_by_allowlist")
    def test_search_no_allowlisted_results(self, mock_filter, mock_get, client):
        """Test search returns empty results with reason when no allowlisted results."""
        # Mock Google API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "title": "Test Result",
                    "link": "https://example.com",
                    "snippet": "Test snippet",
                    "displayLink": "example.com",
                }
            ],
            "searchInformation": {
                "totalResults": "100",
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Mock allowlist filtering (all filtered)
        mock_filter.return_value = []
        
        response = client.post(
            "/api/web-search/search",
            json={"query": "test query", "project_id": "test-project"},
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert "results" in data
        assert len(data["results"]) == 0
        assert data["reason"] == "no_allowlisted_results"
        assert "message" in data
        assert "approved domains" in data["message"].lower()
    
    @patch("src.orchestrator.api.web_search.WORKBENCH_WEB_SEARCH_ENABLED", False)
    def test_search_disabled(self, client):
        """Test search returns error when feature is disabled."""
        response = client.post(
            "/api/web-search/search",
            json={"query": "test query"},
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "disabled" in data["error"].lower()
    
    @patch("src.orchestrator.api.web_search.WORKBENCH_WEB_SEARCH_ENABLED", True)
    @patch("src.orchestrator.api.web_search.GOOGLE_SEARCH_API_KEY", "")
    def test_search_missing_config(self, client):
        """Test search returns error when API key is missing."""
        response = client.post(
            "/api/web-search/search",
            json={"query": "test query"},
        )
        
        assert response.status_code == 503
        data = response.get_json()
        assert "error" in data
        assert "not configured" in data["error"].lower()
    
    @patch("src.orchestrator.api.web_search.WORKBENCH_WEB_SEARCH_ENABLED", True)
    @patch("src.orchestrator.api.web_search.GOOGLE_SEARCH_API_KEY", "test-key")
    @patch("src.orchestrator.api.web_search.GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    @patch("src.orchestrator.api.web_search.requests.get")
    def test_search_missing_query(self, mock_get, client):
        """Test search returns error when query is missing."""
        response = client.post(
            "/api/web-search/search",
            json={},
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "query" in data["error"].lower()


class TestWebSearchQueue:
    """Tests for POST /api/web-search/queue endpoint."""
    
    @patch("src.orchestrator.api.web_search.WORKBENCH_WEB_SEARCH_ENABLED", True)
    @patch("src.orchestrator.api.web_search.WEB_AUGMENTATION_ENABLED", True)
    @patch("src.orchestrator.api.web_search.AugmentationOrchestrator")
    @patch("src.orchestrator.api.web_search.filter_urls_by_allowlist")
    def test_queue_success_with_allowlist(
        self,
        mock_filter,
        mock_orchestrator,
        client,
    ):
        """Test successful queue creates ReviewTask with allowlist filtering."""
        # Mock allowlist filtering (fda.gov passes)
        mock_filter.return_value = ["https://fda.gov/page"]
        
        # Mock orchestrator
        from src.orchestrator.schemas.review import ReviewTask, ReviewStatus
        from src.orchestrator.schemas.claims import Claim
        
        mock_review_task = MagicMock(spec=ReviewTask)
        mock_review_task.review_id = "review-123"
        mock_review_task.status = ReviewStatus.PENDING
        mock_review_task.reason = None
        
        mock_orch = MagicMock()
        mock_orch.run.return_value = mock_review_task
        mock_orch.discovery_service = MagicMock()
        mock_orchestrator.return_value = mock_orch
        
        response = client.post(
            "/api/web-search/queue",
            json={
                "urls": ["https://fda.gov/page"],
                "project_id": "test-project",
                "query": "test query",
            },
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert "review_task_id" in data
        assert data["review_task_id"] == "review-123"
        assert data["status"] == "PENDING"
        assert data["urls_queued"] == 1
        
        # Verify allowlist filtering was applied
        mock_filter.assert_called_once()
        
        # Verify orchestrator was called
        mock_orch.run.assert_called_once()
    
    @patch("src.orchestrator.api.web_search.WORKBENCH_WEB_SEARCH_ENABLED", True)
    @patch("src.orchestrator.api.web_search.WEB_AUGMENTATION_ENABLED", True)
    @patch("src.orchestrator.api.web_search.filter_urls_by_allowlist")
    def test_queue_filters_non_allowlisted_urls(self, mock_filter, client):
        """Test queue filters non-allowlisted URLs."""
        # Mock allowlist filtering (all filtered)
        mock_filter.return_value = []
        
        response = client.post(
            "/api/web-search/queue",
            json={
                "urls": ["https://example.com"],
                "project_id": "test-project",
            },
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "allowlist" in data["error"].lower()
        assert "message" in data
    
    @patch("src.orchestrator.api.web_search.WORKBENCH_WEB_SEARCH_ENABLED", False)
    def test_queue_disabled(self, client):
        """Test queue returns error when feature is disabled."""
        response = client.post(
            "/api/web-search/queue",
            json={"urls": ["https://example.com"], "project_id": "test-project"},
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "disabled" in data["error"].lower()
    
    @patch("src.orchestrator.api.web_search.WORKBENCH_WEB_SEARCH_ENABLED", True)
    @patch("src.orchestrator.api.web_search.WEB_AUGMENTATION_ENABLED", False)
    def test_queue_augmentation_disabled(self, client):
        """Test queue returns error when augmentation is disabled."""
        response = client.post(
            "/api/web-search/queue",
            json={"urls": ["https://example.com"], "project_id": "test-project"},
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "augmentation" in data["error"].lower()
    
    @patch("src.orchestrator.api.web_search.WORKBENCH_WEB_SEARCH_ENABLED", True)
    @patch("src.orchestrator.api.web_search.WEB_AUGMENTATION_ENABLED", True)
    def test_queue_missing_urls(self, client):
        """Test queue returns error when URLs are missing."""
        response = client.post(
            "/api/web-search/queue",
            json={"project_id": "test-project"},
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "urls" in data["error"].lower()
    
    @patch("src.orchestrator.api.web_search.WORKBENCH_WEB_SEARCH_ENABLED", True)
    @patch("src.orchestrator.api.web_search.WEB_AUGMENTATION_ENABLED", True)
    @patch("src.orchestrator.api.web_search.AugmentationOrchestrator")
    @patch("src.orchestrator.api.web_search.filter_urls_by_allowlist")
    def test_queue_quota_exceeded_returns_failed(
        self, mock_filter, mock_orchestrator, client
    ):
        """Test queue returns FAILED when quota is exceeded."""
        # Mock allowlist filtering (fda.gov passes)
        mock_filter.return_value = ["https://fda.gov/page"]
        
        # Mock orchestrator returning FAILED ReviewTask
        from src.orchestrator.schemas.review import ReviewTask, ReviewStatus
        
        mock_review_task = MagicMock(spec=ReviewTask)
        mock_review_task.review_id = "review-123"
        mock_review_task.status = ReviewStatus.FAILED
        mock_review_task.reason = "quota_exceeded"
        
        mock_orch = MagicMock()
        mock_orch.run.return_value = mock_review_task
        mock_orch.discovery_service = MagicMock()
        mock_orchestrator.return_value = mock_orch
        
        response = client.post(
            "/api/web-search/queue",
            json={
                "urls": ["https://fda.gov/page"],
                "project_id": "test-project",
            },
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "FAILED"
        assert data["reason"] == "quota_exceeded"
        assert "message" in data

