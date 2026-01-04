"""
Firecrawl HTTP Bridge for Project Vyasa.

HTTP-only client for Firecrawl sidecar service. No SDK imports.
Preserves AGPL boundaries by using direct HTTP requests only.
"""

import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import requests

from ...shared.config import _env
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

# Firecrawl service configuration
FIRECRAWL_SERVICE_URL = _env("FIRECRAWL_SERVICE_URL", "http://firecrawl:3002")
FIRECRAWL_TIMEOUT = int(_env("WEB_TIMEOUT_SECONDS", "30"))


class FirecrawlBridge:
    """HTTP-only bridge to Firecrawl sidecar service.
    
    Provides web scraping capabilities via Firecrawl without SDK imports,
    preserving AGPL boundaries.
    """
    
    def __init__(
        self,
        service_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """Initialize FirecrawlBridge.
        
        Args:
            service_url: Firecrawl service URL (defaults to env var)
            timeout: Request timeout in seconds (defaults to env var or 30)
        """
        self.service_url = (service_url or FIRECRAWL_SERVICE_URL).rstrip("/")
        self.timeout = timeout or FIRECRAWL_TIMEOUT
        
        # Firecrawl API endpoint
        self.scrape_endpoint = f"{self.service_url}/v0/scrape"
    
    def scrape(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Scrape URLs via Firecrawl and return structured results.
        
        Scrapes each URL independently. Failures for individual URLs
        are recorded but do not abort the entire batch.
        
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
        """
        if not urls:
            return []
        
        results: List[Dict[str, Any]] = []
        
        for url in urls:
            if not url or not isinstance(url, str):
                logger.warning(f"Skipping invalid URL: {url}")
                results.append(self._create_error_result(url, "Invalid URL format"))
                continue
            
            try:
                result = self._scrape_single_url(url)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to scrape {url}: {e}", exc_info=True)
                results.append(self._create_error_result(url, str(e)))
        
        return results
    
    def _scrape_single_url(self, url: str) -> Dict[str, Any]:
        """Scrape a single URL via Firecrawl API.
        
        Args:
            url: URL to scrape
        
        Returns:
            Result dictionary with url, domain, title, retrieved_at, markdown, error
        
        Raises:
            requests.RequestException: If HTTP request fails
            ValueError: If response is invalid
        """
        # Extract domain from URL
        domain = self._extract_domain(url)
        
        # Prepare request payload
        payload = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
            "waitFor": 1000,  # Wait 1 second for page load
        }
        
        headers = {
            "Content-Type": "application/json",
        }
        
        try:
            response = requests.post(
                self.scrape_endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract markdown content
            markdown = ""
            if "data" in data:
                markdown = data["data"].get("markdown", "")
            elif "markdown" in data:
                markdown = data["markdown"]
            
            # Extract title
            title = None
            if "data" in data:
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
            logger.error(f"Firecrawl API request failed for {url}: {e}")
            raise
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Invalid Firecrawl API response for {url}: {e}")
            raise ValueError(f"Invalid API response: {e}") from e
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL.
        
        Args:
            url: Full URL
        
        Returns:
            Domain string (normalized, no www.)
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split("/")[0]
            # Remove port if present
            if ":" in domain:
                domain = domain.split(":")[0]
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain.lower()
        except Exception as e:
            logger.warning(f"Failed to extract domain from {url}: {e}")
            return "unknown"
    
    def _create_error_result(self, url: str, error_message: str) -> Dict[str, Any]:
        """Create an error result dictionary.
        
        Args:
            url: URL that failed
            error_message: Error message
        
        Returns:
            Result dictionary with error information
        """
        return {
            "url": url,
            "domain": self._extract_domain(url),
            "title": None,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "markdown": "",
            "error": error_message,
        }
