"""
Web Discovery Service for Project Vyasa.

Converts DisputeContext into search queries, calls Google Custom Search API,
and returns filtered candidate URLs for web augmentation.
"""

import os
from typing import List, Optional, Set
import requests

from ...shared.config import _env
from ...shared.logger import get_logger
from ..schemas.disputes import DisputeContext, TriggerSourceType
from .domain_policy import (
    filter_urls,
    filter_urls_by_allowlist,
    parse_domain_lists,
    default_allowlist,
)

logger = get_logger("orchestrator", __name__)

# Google Custom Search API configuration
GOOGLE_SEARCH_API_KEY = _env("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = _env("GOOGLE_SEARCH_ENGINE_ID", "")
GOOGLE_SEARCH_API_URL = "https://www.googleapis.com/customsearch/v1"

# Domain policy configuration
WEB_DOMAIN_ALLOWLIST = _env("WEB_DOMAIN_ALLOWLIST", "")
WEB_DOMAIN_BLOCKLIST = _env("WEB_DOMAIN_BLOCKLIST", "")


class WebDiscoveryService:
    """Service for discovering web URLs via Google Custom Search API.
    
    Converts DisputeContext into search queries, executes searches,
    and returns filtered candidate URLs based on domain policy.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        engine_id: Optional[str] = None,
        allowlist: Optional[str] = None,
        blocklist: Optional[str] = None,
    ):
        """Initialize Web Discovery Service.
        
        Args:
            api_key: Google Custom Search API key (defaults to env var)
            engine_id: Google Custom Search Engine ID (defaults to env var)
            allowlist: Comma-separated allowed domains (defaults to env var, or default_allowlist if empty)
            blocklist: Comma-separated blocked domains (defaults to env var)
        """
        self.api_key = api_key or GOOGLE_SEARCH_API_KEY
        self.engine_id = engine_id or GOOGLE_SEARCH_ENGINE_ID
        
        # Parse allowlist/blocklist
        allowlist_str = allowlist or WEB_DOMAIN_ALLOWLIST
        # If allowlist is empty, use default Tier 1 allowlist
        if not allowlist_str or not allowlist_str.strip():
            allowlist_str = ",".join(default_allowlist())
        
        self.allowlist, self.blocklist = parse_domain_lists(
            allowlist_str,
            blocklist or WEB_DOMAIN_BLOCKLIST,
        )
        
        # Store allowlist patterns for strict filtering (supports wildcards)
        self.allowlist_patterns = [
            pattern.strip() for pattern in allowlist_str.split(",") if pattern.strip()
        ] if allowlist_str else default_allowlist()
        
        # Check if API is configured
        self._api_enabled = bool(self.api_key and self.engine_id)
        if not self._api_enabled:
            logger.warning(
                "Google Custom Search API not configured. "
                "Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID to enable web discovery."
            )
    
    def build_queries(self, dispute: DisputeContext) -> List[str]:
        """Build 3-5 search query variants from DisputeContext.
        
        Generates query variants based on:
        - Disagreement summary
        - Required evidence type
        - Trigger source type
        
        Args:
            dispute: DisputeContext with disagreement summary and metadata
        
        Returns:
            List of 3-5 search query strings
        """
        queries: List[str] = []
        
        # Base query from disagreement summary
        base_query = dispute.disagreement_summary.strip()
        if not base_query:
            logger.warning(f"Dispute {dispute.dispute_id} has empty disagreement_summary")
            return []
        
        # Query 1: Direct disagreement summary
        queries.append(base_query)
        
        # Query 2: Add evidence type if specified
        if dispute.required_evidence_type:
            queries.append(f"{base_query} {dispute.required_evidence_type}")
        
        # Query 3: Add context based on trigger source type
        if dispute.trigger_source_type == TriggerSourceType.RQ:
            queries.append(f"{base_query} research")
        elif dispute.trigger_source_type == TriggerSourceType.CLAIM:
            queries.append(f"{base_query} evidence")
        elif dispute.trigger_source_type == TriggerSourceType.BLOCK:
            queries.append(f"{base_query} analysis")
        
        # Query 4: Add priority context for high-priority disputes
        if dispute.priority.value == "HIGH":
            queries.append(f"{base_query} authoritative source")
        
        # Query 5: Simplified version (if we have fewer than 5)
        if len(queries) < 5:
            # Extract key terms (simple heuristic: first 5-7 words)
            words = base_query.split()[:7]
            if len(words) > 3:
                queries.append(" ".join(words))
        
        # Ensure we have 3-5 queries
        queries = queries[:5]  # Cap at 5
        if len(queries) < 3:
            # If we have fewer than 3, duplicate the base query with variations
            while len(queries) < 3:
                queries.append(base_query)
        
        return queries[:5]  # Return up to 5 queries
    
    def search(self, queries: List[str]) -> List[str]:
        """Execute Google Custom Search for each query and return deduplicated URLs.
        
        Args:
            queries: List of search query strings
        
        Returns:
            Deduplicated list of URLs (preserves order, first occurrence wins)
        """
        if not self._api_enabled:
            logger.warning("Google Custom Search API not enabled, returning empty results")
            return []
        
        if not queries:
            return []
        
        all_urls: List[str] = []
        seen_urls: Set[str] = set()
        
        for query in queries:
            if not query or not query.strip():
                continue
            
            try:
                urls = self._execute_search(query.strip())
                for url in urls:
                    # Deduplicate by exact URL match
                    if url not in seen_urls:
                        seen_urls.add(url)
                        all_urls.append(url)
            except Exception as e:
                logger.warning(f"Search failed for query '{query}': {e}", exc_info=True)
                continue
        
        return all_urls
    
    def _execute_search(self, query: str) -> List[str]:
        """Execute a single Google Custom Search API request.
        
        Args:
            query: Search query string
        
        Returns:
            List of URLs from search results
        
        Raises:
            requests.RequestException: If API request fails
            ValueError: If API response is invalid
        """
        params = {
            "key": self.api_key,
            "cx": self.engine_id,
            "q": query,
            "num": 10,  # Max results per query
        }
        
        try:
            response = requests.get(GOOGLE_SEARCH_API_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract URLs from search results
            urls: List[str] = []
            items = data.get("items", [])
            
            for item in items:
                link = item.get("link")
                if link and isinstance(link, str):
                    urls.append(link)
            
            return urls
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Google Custom Search API request failed: {e}")
            raise
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Invalid Google Custom Search API response: {e}")
            raise ValueError(f"Invalid API response: {e}") from e
    
    def discover(self, dispute: DisputeContext) -> List[str]:
        """Discover candidate URLs for a dispute (full pipeline).
        
        Pipeline:
        1. Build queries from dispute context
        2. Execute searches
        3. Filter URLs by domain policy
        4. Return ranked URLs
        
        Args:
            dispute: DisputeContext triggering web augmentation
        
        Returns:
            List of filtered, ranked candidate URLs
        """
        if not self._api_enabled:
            logger.warning(
                f"Web discovery disabled for dispute {dispute.dispute_id}. "
                "Google Custom Search API not configured."
            )
            return []
        
        # Build queries
        queries = self.build_queries(dispute)
        if not queries:
            logger.warning(f"No queries generated for dispute {dispute.dispute_id}")
            return []
        
        logger.info(
            f"Discovering URLs for dispute {dispute.dispute_id} "
            f"with {len(queries)} queries"
        )
        
        # Execute searches
        urls = self.search(queries)
        
        if not urls:
            logger.info(f"No URLs found for dispute {dispute.dispute_id}")
            return []
        
        # Apply strict allowlist filtering (after Google search, before Firecrawl)
        original_count = len(urls)
        filtered_urls = filter_urls_by_allowlist(urls, self.allowlist_patterns)
        dropped_count = original_count - len(filtered_urls)
        
        if dropped_count > 0:
            logger.info(
                f"Filtered {dropped_count} URL(s) not in allowlist for dispute {dispute.dispute_id} "
                f"({len(filtered_urls)} remain)"
            )
        
        if not filtered_urls:
            logger.info(
                f"No allowlisted URLs found for dispute {dispute.dispute_id} "
                f"(all {original_count} results were filtered)"
            )
            return []  # Return empty list with implicit reason "no_allowlisted_results"
        
        logger.info(
            f"Discovered {len(filtered_urls)} allowlisted URLs for dispute {dispute.dispute_id} "
            f"(filtered from {original_count} total)"
        )
        
        return filtered_urls

