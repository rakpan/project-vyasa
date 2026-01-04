"""
Firecrawl Cloud HTTP Bridge for Project Vyasa.

HTTP-only client for Firecrawl Cloud API. No SDK imports.
Preserves AGPL boundaries by using direct HTTP requests only.

CRITICAL LICENSE BOUNDARY:
-------------------------
Firecrawl is AGPL-licensed. To preserve license boundaries, this module
MUST NEVER import Firecrawl's SDK or create a code dependency on Firecrawl.

✅ ALLOWED: HTTP requests via `requests` library
❌ FORBIDDEN: `import firecrawl`, `from firecrawl import *`, or any Firecrawl SDK usage

Firecrawl Cloud is a remote API service. This module communicates via HTTP only.
Do not add Firecrawl SDK imports to this module or any other Vyasa core code.

See: docs/CONTRIBUTING.md (License Boundary / Sidecar Rule)
See: docs/decisions/ADR-004-web-augmentation-sidecar.md
"""

import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import requests

from ...shared.config import _env
from ...shared.logger import get_logger
from ..config import WEB_AUGMENTATION_ENABLED
from .domain_policy import filter_urls_by_allowlist, default_allowlist, _extract_domain, domain_matches

logger = get_logger("orchestrator", __name__)

# Firecrawl Cloud configuration
FIRECRAWL_MODE = _env("FIRECRAWL_MODE", "cloud")
FIRECRAWL_API_KEY = _env("FIRECRAWL_API_KEY", "")
FIRECRAWL_BASE_URL = _env("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev")
FIRECRAWL_TIMEOUT = int(_env("WEB_TIMEOUT_SECONDS", "30"))

# Domain allowlist for strict filtering (before Firecrawl calls)
WEB_DOMAIN_ALLOWLIST = _env("WEB_DOMAIN_ALLOWLIST", "")
WEB_CRAWL_ENABLED = _env("WEB_CRAWL_ENABLED", "false").lower() in ("true", "1", "yes")


class FirecrawlBridge:
    """HTTP-only bridge to Firecrawl Cloud API.
    
    Provides web scraping and crawling capabilities via Firecrawl Cloud
    without SDK imports, preserving AGPL boundaries.
    
    Requires API key authentication. Supports only scrape and crawl endpoints.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        allowlist_patterns: Optional[List[str]] = None,
    ):
        """Initialize FirecrawlBridge.
        
        Args:
            api_key: Firecrawl Cloud API key (defaults to env var, required if WEB_AUGMENTATION_ENABLED=true)
            base_url: Firecrawl Cloud base URL (defaults to env var or https://api.firecrawl.dev)
            timeout: Request timeout in seconds (defaults to env var or 30)
            allowlist_patterns: List of domain patterns for strict filtering (defaults to env var or default_allowlist)
        
        Raises:
            ValueError: If API key is missing when WEB_AUGMENTATION_ENABLED=true
        """
        self.api_key = api_key or FIRECRAWL_API_KEY
        self.base_url = (base_url or FIRECRAWL_BASE_URL).rstrip("/")
        self.timeout = timeout or FIRECRAWL_TIMEOUT
        
        # Validate API key if web augmentation is enabled
        if WEB_AUGMENTATION_ENABLED and not self.api_key:
            raise ValueError(
                "FIRECRAWL_API_KEY is required when WEB_AUGMENTATION_ENABLED=true. "
                "Set FIRECRAWL_API_KEY in environment variables or pass api_key parameter."
            )
        
        # Firecrawl Cloud API endpoints
        self.scrape_endpoint = f"{self.base_url}/v0/scrape"
        self.crawl_endpoint = f"{self.base_url}/v0/crawl"
        
        # Domain allowlist for strict filtering (safety check before Firecrawl calls)
        if allowlist_patterns is not None:
            self.allowlist_patterns = allowlist_patterns
        else:
            # Parse from env or use default
            allowlist_str = WEB_DOMAIN_ALLOWLIST
            if not allowlist_str or not allowlist_str.strip():
                self.allowlist_patterns = default_allowlist()
            else:
                self.allowlist_patterns = [
                    pattern.strip() for pattern in allowlist_str.split(",") if pattern.strip()
                ]
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Firecrawl Cloud API requests.
        
        Returns:
            Dictionary with Authorization header and Content-Type
        """
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def scrape(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Scrape URLs via Firecrawl and return structured results.
        
        Scrapes each URL independently. Failures for individual URLs
        are recorded but do not abort the entire batch.
        
        **Security**: Before making Firecrawl calls, enforces strict allowlist filtering
        to prevent accidental spend on low-quality sources.
        
        Connection errors (Firecrawl unavailable) are handled gracefully:
        - Returns structured error results for each URL
        - Does not raise uncaught exceptions
        - Logs connection errors once (not per-URL)
        
        Args:
            urls: List of URLs to scrape
        
        Returns:
            List of result dictionaries, one per URL:
            - url: Original URL
            - domain: Extracted domain
            - title: Page title (if available)
            - retrieved_at: ISO timestamp
            - markdown: Scraped content in markdown format
            - error: Error message if scraping failed (None if successful)
            - error_type: Error type if failed ("connection_error", "timeout", "http_error", "invalid_response", "not_allowlisted", "other")
        """
        if not urls:
            return []
        
        # Security: Enforce strict allowlist filtering before Firecrawl calls
        original_count = len(urls)
        allowlisted_urls = filter_urls_by_allowlist(urls, self.allowlist_patterns)
        rejected_count = original_count - len(allowlisted_urls)
        
        if rejected_count > 0:
            logger.warning(
                f"Rejected {rejected_count} URL(s) not in allowlist before Firecrawl call "
                f"({len(allowlisted_urls)} will be scraped)"
            )
        
        # Create set for fast lookup
        allowlisted_set = set(allowlisted_urls)
        
        if not allowlisted_urls:
            logger.warning("All URLs were rejected by allowlist; no Firecrawl calls will be made")
            # Return error results for all URLs in original order
            results: List[Dict[str, Any]] = []
            for url in urls:
                if url and isinstance(url, str):
                    domain = _extract_domain(url)
                    results.append(self._create_error_result(
                        url,
                        f"Domain not in allowlist: {domain}",
                        "not_allowlisted"
                    ))
            return results
        
        connection_error_logged = False
        results: List[Dict[str, Any]] = []
        
        # Process URLs in original order
        for url in urls:
            if not url or not isinstance(url, str):
                logger.warning(f"Skipping invalid URL: {url}")
                results.append(self._create_error_result(url, "Invalid URL format", "invalid_url"))
                continue
            
            # Check if URL is allowlisted (safety check)
            if url not in allowlisted_set:
                domain = _extract_domain(url)
                results.append(self._create_error_result(
                    url,
                    f"Domain not in allowlist: {domain}",
                    "not_allowlisted"
                ))
                continue
            
            try:
                result = self._scrape_single_url(url)
                results.append(result)
            except requests.exceptions.ConnectionError as e:
                # Firecrawl Cloud API is unreachable
                if not connection_error_logged:
                    logger.error(
                        f"Firecrawl Cloud API unreachable at {self.base_url}: {e}",
                        extra={"payload": {"base_url": self.base_url, "error": str(e)}},
                    )
                    connection_error_logged = True
                results.append(self._create_error_result(url, f"Firecrawl Cloud API unreachable: {e}", "connection_error"))
            except requests.exceptions.Timeout as e:
                # Request timeout
                logger.warning(f"Firecrawl Cloud request timeout for {url}: {e}")
                results.append(self._create_error_result(url, f"Request timeout: {e}", "timeout"))
            except requests.exceptions.HTTPError as e:
                # HTTP error (4xx, 5xx)
                status_code = e.response.status_code if hasattr(e, 'response') else None
                error_msg = f"HTTP error {status_code}: {e}" if status_code else f"HTTP error: {e}"
                logger.warning(f"Firecrawl Cloud HTTP error for {url}: {error_msg}")
                results.append(self._create_error_result(url, error_msg, "http_error"))
            except (ValueError, KeyError, TypeError) as e:
                # Invalid response format
                logger.warning(f"Invalid Firecrawl Cloud response for {url}: {e}")
                results.append(self._create_error_result(url, f"Invalid response: {e}", "invalid_response"))
            except Exception as e:
                # Other unexpected errors
                logger.warning(f"Unexpected error scraping {url}: {e}", exc_info=True)
                results.append(self._create_error_result(url, f"Unexpected error: {e}", "other"))
        
        return results
    
    def _scrape_single_url(self, url: str) -> Dict[str, Any]:
        """Scrape a single URL via Firecrawl Cloud API.
        
        Args:
            url: URL to scrape
        
        Returns:
            Result dictionary with url, domain, title, retrieved_at, markdown, error
        
        Raises:
            requests.RequestException: If HTTP request fails
            ValueError: If response is invalid
        """
        # Extract domain from URL
        domain = _extract_domain(url)
        
        # Prepare request payload for Firecrawl Cloud API
        payload = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
            "waitFor": 1000,  # Wait 1 second for page load
        }
        
        try:
            response = requests.post(
                self.scrape_endpoint,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract markdown content (Firecrawl Cloud API format)
            markdown = ""
            if "data" in data and isinstance(data["data"], dict):
                markdown = data["data"].get("markdown", "")
            elif "markdown" in data:
                markdown = data["markdown"]
            
            # Extract title
            title = None
            if "data" in data and isinstance(data["data"], dict):
                title = data["data"].get("title")
            elif "title" in data:
                title = data["title"]
            
            return {
                "url": url,
                "domain": domain,
                "title": title,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "markdown": markdown,
                "error": None,
            }
            
        except requests.exceptions.RequestException as e:
            # Re-raise to be caught by scrape() method for structured error handling
            raise
        except (KeyError, ValueError, TypeError) as e:
            # Re-raise to be caught by scrape() method for structured error handling
            raise ValueError(f"Invalid API response: {e}") from e
    
    def crawl(
        self,
        root_url: str,
        max_pages: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Crawl a website starting from root URL (bounded crawl).
        
        Only enabled if WEB_CRAWL_ENABLED=true. If disabled, returns error
        without calling Firecrawl Cloud.
        
        Args:
            root_url: Root URL to start crawling from
            max_pages: Maximum number of pages to crawl (defaults to WEB_MAX_PAGES)
            max_depth: Maximum crawl depth (defaults to 3)
        
        Returns:
            List of result dictionaries, one per crawled page:
            - url: Page URL
            - domain: Extracted domain
            - title: Page title (if available)
            - retrieved_at: ISO timestamp
            - markdown: Scraped content in markdown format
            - error: Error message if crawling failed (None if successful)
            - error_type: Error type if failed
        
        Raises:
            ValueError: If crawl is disabled or root_url is not allowlisted
        """
        if not WEB_CRAWL_ENABLED:
            raise ValueError(
                "Crawl is disabled. Set WEB_CRAWL_ENABLED=true to enable crawling. "
                "Crawling is disabled by default to prevent excessive API usage."
            )
        
        if not root_url or not isinstance(root_url, str):
            raise ValueError(f"Invalid root URL: {root_url}")
        
        # Enforce allowlist for root URL
        root_domain = _extract_domain(root_url)
        matched = False
        for pattern in self.allowlist_patterns:
            if domain_matches(pattern, root_domain):
                matched = True
                break
        
        if not matched:
            raise ValueError(
                f"Root URL domain '{root_domain}' is not in allowlist. "
                "Crawling is restricted to allowlisted domains only."
            )
        
        # Use defaults if not specified
        max_pages = max_pages or int(_env("WEB_MAX_PAGES", "25"))
        max_depth = max_depth or 3
        
        # Prepare request payload for Firecrawl Cloud crawl API
        payload = {
            "url": root_url,
            "crawlerOptions": {
                "maxDepth": max_depth,
                "maxPages": max_pages,
            },
            "formats": ["markdown"],
            "onlyMainContent": True,
        }
        
        try:
            response = requests.post(
                self.crawl_endpoint,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout * 2,  # Crawl may take longer
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract crawled pages from response
            pages: List[Dict[str, Any]] = []
            if "data" in data and isinstance(data["data"], list):
                for page_data in data["data"]:
                    if isinstance(page_data, dict):
                        pages.append({
                            "url": page_data.get("url", root_url),
                            "domain": _extract_domain(page_data.get("url", root_url)),
                            "title": page_data.get("title"),
                            "retrieved_at": datetime.now(timezone.utc).isoformat(),
                            "markdown": page_data.get("markdown", ""),
                            "error": None,
                        })
            elif "data" in data and isinstance(data["data"], dict):
                # Single page response
                pages.append({
                    "url": data["data"].get("url", root_url),
                    "domain": _extract_domain(data["data"].get("url", root_url)),
                    "title": data["data"].get("title"),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "markdown": data["data"].get("markdown", ""),
                    "error": None,
                })
            
            logger.info(f"Crawled {len(pages)} pages from {root_url}")
            return pages
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Firecrawl Cloud crawl request failed for {root_url}: {e}")
            raise
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Invalid Firecrawl Cloud crawl response for {root_url}: {e}")
            raise ValueError(f"Invalid API response: {e}") from e
    
    
    def _create_error_result(self, url: str, error_message: str, error_type: str = "other") -> Dict[str, Any]:
        """Create an error result dictionary.
        
        Args:
            url: URL that failed
            error_message: Error message
            error_type: Error type ("connection_error", "timeout", "http_error", "invalid_response", "invalid_url", "not_allowlisted", "other")
        
        Returns:
            Result dictionary with error information
        """
        return {
            "url": url,
            "domain": _extract_domain(url),
            "title": None,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "markdown": "",
            "error": error_message,
            "error_type": error_type,
        }
