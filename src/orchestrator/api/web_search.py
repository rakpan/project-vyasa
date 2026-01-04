"""
Web Search API endpoints for Project Vyasa Workbench.

Provides server-side Google Custom Search JSON API integration and
URL queueing into the governance review flow (Firecrawl scrape → extract → ReviewTask).
"""

import uuid
from typing import List, Dict, Any, Optional
from flask import Blueprint, request, jsonify
import requests

from ...shared.config import (
    _env,
    get_memory_url,
    get_arango_password,
    ARANGODB_DB,
    ARANGODB_USER,
)
from ...shared.logger import get_logger
from ..web.firecrawl import FirecrawlBridge
from ..web.augmentation_orchestrator import AugmentationOrchestrator, _compute_domain_quality_score
from ..web.discovery import WebDiscoveryService
from ..web.domain_policy import filter_urls_by_allowlist, default_allowlist, _extract_domain
from ..schemas.disputes import DisputeContext, TriggerSourceType, DisputePriority
from ..schemas.review import ReviewTask, ReviewStatus
from ..config import WEB_AUGMENTATION_ENABLED

logger = get_logger("orchestrator", __name__)

web_search_bp = Blueprint("web_search", __name__)

# Configuration
WORKBENCH_WEB_SEARCH_ENABLED = _env("WORKBENCH_WEB_SEARCH_ENABLED", "false").lower() in ("true", "1", "yes")
GOOGLE_SEARCH_API_KEY = _env("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = _env("GOOGLE_SEARCH_ENGINE_ID", "")  # PSE cx id
WEB_MAX_SEARCH_RESULTS = int(_env("WEB_MAX_SEARCH_RESULTS", "10"))

# Google Custom Search JSON API endpoint
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

def _compute_domain_quality_tier(domain: str) -> str:
    """Compute quality tier for domain (simple mapping).
    
    Args:
        domain: Domain string (normalized, no www.)
    
    Returns:
        Quality tier: "high", "medium", or "low"
    """
    domain_lower = domain.lower()
    
    if domain_lower.endswith(".gov") or domain_lower.endswith(".edu"):
        return "high"
    elif domain_lower.endswith(".org") or any(
        journal in domain_lower for journal in ["nature.com", "science.org", "ieee.org", "acm.org"]
    ):
        return "high"
    elif domain_lower.endswith(".com") or domain_lower.endswith(".net"):
        return "medium"
    else:
        return "low"


@web_search_bp.route("/api/web-search/search", methods=["POST"])
def search():
    """Search the web using Google Custom Search JSON API.
    
    Request body (JSON):
        {
            "query": str (required),
            "project_id": str (optional, for context)
        }
    
    Response:
        {
            "results": [
                {
                    "title": str,
                    "link": str,
                    "snippet": str,
                    "displayLink": str
                },
                ...
            ],
            "total_results": int (approximate)
        }
    
    Errors:
        400: Missing query or feature disabled
        503: Google API unavailable or misconfigured
    """
    if not WORKBENCH_WEB_SEARCH_ENABLED:
        return jsonify({"error": "Web search is disabled"}), 400
    
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        return jsonify({
            "error": "Google Search API not configured",
            "hint": "Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID in deploy/.env"
        }), 503
    
    try:
        payload = request.json or {}
        query = payload.get("query", "").strip()
        project_id = payload.get("project_id")
        
        if not query:
            return jsonify({"error": "query is required"}), 400
        
        # Call Google Custom Search JSON API
        params = {
            "key": GOOGLE_SEARCH_API_KEY,
            "cx": GOOGLE_SEARCH_ENGINE_ID,
            "q": query,
            "num": min(WEB_MAX_SEARCH_RESULTS, 10),  # Google API max is 10 per request
        }
        
        response = requests.get(GOOGLE_SEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract results
        items = data.get("items", [])
        all_urls = [item.get("link", "") for item in items if item.get("link")]
        
        # Apply strict allowlist filtering
        allowlist_patterns = default_allowlist()
        allowlisted_urls = filter_urls_by_allowlist(all_urls, allowlist_patterns)
        filtered_count = len(all_urls) - len(allowlisted_urls)
        
        if filtered_count > 0:
            logger.info(
                f"Filtered {filtered_count} URL(s) not in allowlist for query '{query}'"
            )
        
        # Build results with quality scores
        results = []
        for item in items:
            url = item.get("link", "")
            if url in allowlisted_urls:
                domain = _extract_domain(url)
                quality_tier = _compute_domain_quality_tier(domain)
                quality_score = _compute_domain_quality_score(domain)
                
                results.append({
                    "title": item.get("title", ""),
                    "link": url,
                    "snippet": item.get("snippet", ""),
                    "displayLink": item.get("displayLink", ""),
                    "quality_tier": quality_tier,
                    "quality_score": quality_score,
                })
        
        total_results = int(data.get("searchInformation", {}).get("totalResults", 0))
        
        # If no allowlisted results, return empty with reason
        if not results:
            logger.info(
                f"No allowlisted results for query '{query}' (all {len(all_urls)} results filtered)"
            )
            return jsonify({
                "results": [],
                "total_results": total_results,
                "reason": "no_allowlisted_results",
                "message": "No results found in approved domains. Results are restricted to high-fidelity sources.",
            }), 200
        
        logger.info(
            f"Web search completed: query='{query}', allowlisted_results={len(results)} (filtered {filtered_count})",
            extra={
                "payload": {
                    "query": query,
                    "project_id": project_id,
                    "result_count": len(results),
                    "filtered_count": filtered_count,
                }
            },
        )
        
        return jsonify({
            "results": results,
            "total_results": total_results,
        }), 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Google Search API error: {e}", exc_info=True)
        return jsonify({
            "error": "Google Search API unavailable",
            "details": str(e)
        }), 503
    except Exception as e:
        logger.error(f"Web search error: {e}", exc_info=True)
        return jsonify({
            "error": "Web search failed",
            "details": str(e)
        }), 500


@web_search_bp.route("/api/web-search/queue", methods=["POST"])
def queue_urls():
    """Queue selected URLs into the governance review flow.
    
    Request body (JSON):
        {
            "urls": List[str] (required),
            "project_id": str (required),
            "query": str (optional, for context)
        }
    
    Response:
        {
            "review_task_id": str,
            "status": "PENDING" | "FAILED",
            "urls_queued": int,
            "urls_failed": int,
            "message": str
        }
    
    Errors:
        400: Missing required fields or feature disabled
        503: Firecrawl unavailable or augmentation disabled
    """
    if not WORKBENCH_WEB_SEARCH_ENABLED:
        return jsonify({"error": "Web search is disabled"}), 400
    
    if not WEB_AUGMENTATION_ENABLED:
        return jsonify({
            "error": "Web augmentation is disabled",
            "hint": "Set WEB_AUGMENTATION_ENABLED=true in deploy/.env"
        }), 400
    
    try:
        payload = request.json or {}
        urls = payload.get("urls", [])
        project_id = payload.get("project_id", "").strip()
        query = payload.get("query", "").strip()
        
        if not urls:
            return jsonify({"error": "urls is required and must not be empty"}), 400
        if not project_id:
            return jsonify({"error": "project_id is required"}), 400
        
        # Apply strict allowlist filtering
        allowlist_patterns = default_allowlist()
        allowlisted_urls = filter_urls_by_allowlist(urls, allowlist_patterns)
        filtered_count = len(urls) - len(allowlisted_urls)
        
        if not allowlisted_urls:
            return jsonify({
                "error": "All URLs were filtered by allowlist",
                "filtered_count": filtered_count,
                "message": "No URLs match approved domains. Results are restricted to high-fidelity sources.",
            }), 400
        
        if filtered_count > 0:
            logger.info(
                f"Filtered {filtered_count} URL(s) not in allowlist for queue operation"
            )
        
        # Generate job_id for this queue operation
        job_id = str(uuid.uuid4())
        
        # Create DisputeContext for the queue operation
        # Use MANUAL_SEARCH to bypass priority gate (explicit user intent)
        dispute_context = DisputeContext.create(
            project_id=project_id,
            job_id=job_id,
            trigger_source_type=TriggerSourceType.MANUAL_SEARCH,
            trigger_source_id="workbench-web-search",
            disagreement_summary=f"Web search results for query: {query}" if query else "Web search results from workbench",
            required_evidence_type=None,
            priority=DisputePriority.MEDIUM,  # MEDIUM is OK for MANUAL_SEARCH
        )
        
        # Use AugmentationOrchestrator to process URLs
        # This enforces quota, allowlist, and creates ReviewTask properly
        orchestrator = AugmentationOrchestrator()
        
        # Override discovery service to return our URLs directly
        # We'll create a custom discovery service that returns the allowlisted URLs
        class DirectURLDiscoveryService:
            def __init__(self, urls: List[str]):
                self.urls = urls
            
            def discover(self, dispute: DisputeContext) -> List[str]:
                return self.urls
        
        orchestrator.discovery_service = DirectURLDiscoveryService(allowlisted_urls)
        
        # Run orchestrator (enforces quota, allowlist, creates ReviewTask)
        # Note: orchestrator will check quota, apply allowlist again (safety check),
        # scrape URLs, extract claims, and create ReviewTask
        review_task = orchestrator.run(dispute_context)
        
        # ReviewTask is already created and persisted by orchestrator
        # Extract status and counts from review_task
        status_str = "PENDING" if review_task.status == ReviewStatus.PENDING else "FAILED"
        
        # Count URLs that were successfully processed
        # Note: orchestrator may have filtered some URLs, so we report what was actually queued
        urls_queued = len(allowlisted_urls) if review_task.status == ReviewStatus.PENDING else 0
        urls_failed = filtered_count  # URLs filtered by allowlist
        
        # Build message
        if review_task.status == ReviewStatus.FAILED:
            message = f"Queue failed: {review_task.reason or 'unknown error'}"
        else:
            message = f"Queued {urls_queued} URL(s) for review"
        
        logger.info(
            f"Queue operation completed: review_task_id={review_task.review_id}, status={status_str}",
            extra={
                "payload": {
                    "review_task_id": review_task.review_id,
                    "project_id": project_id,
                    "status": status_str,
                    "urls_queued": urls_queued,
                    "urls_failed": urls_failed,
                    "reason": review_task.reason,
                }
            },
        )
        
        return jsonify({
            "review_task_id": review_task.review_id,
            "status": status_str,
            "urls_queued": urls_queued,
            "urls_failed": urls_failed,
            "message": message,
            "reason": review_task.reason,  # Include reason for FAILED status
        }), 200
        
    except Exception as e:
        logger.error(f"Queue URLs error: {e}", exc_info=True)
        return jsonify({
            "error": "Failed to queue URLs",
            "details": str(e)
        }), 500

