"""
Domain policy filtering for web augmentation.

Filters URLs based on allowlist/blocklist configuration,
aligning with Vyasa's safety and governance principles.
"""

import re
from typing import List, Set, Optional
from urllib.parse import urlparse

from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)


def parse_domain_lists(
    allowlist_str: Optional[str] = None,
    blocklist_str: Optional[str] = None,
) -> tuple[Set[str], Set[str]]:
    """Parse comma-separated domain lists from environment variables.
    
    Args:
        allowlist_str: Comma-separated list of allowed domains (empty = allow all except blocklist)
        blocklist_str: Comma-separated list of blocked domains
    
    Returns:
        Tuple of (allowlist_set, blocklist_set) with normalized domains
    """
    allowlist: Set[str] = set()
    blocklist: Set[str] = set()
    
    if allowlist_str:
        for domain in allowlist_str.split(","):
            domain = domain.strip()
            if domain:
                allowlist.add(_normalize_domain(domain))
    
    if blocklist_str:
        for domain in blocklist_str.split(","):
            domain = domain.strip()
            if domain:
                blocklist.add(_normalize_domain(domain))
    
    return allowlist, blocklist


def _normalize_domain(domain: str) -> str:
    """Normalize domain name (strip www., protocol, path).
    
    Args:
        domain: Domain string (may include protocol, www, path)
    
    Returns:
        Normalized domain (lowercase, no www., no protocol, no path)
    """
    # Remove protocol if present
    if "://" in domain:
        domain = domain.split("://", 1)[1]
    
    # Remove path if present
    if "/" in domain:
        domain = domain.split("/", 1)[0]
    
    # Remove port if present
    if ":" in domain:
        domain = domain.split(":", 1)[0]
    
    # Remove www. prefix
    domain = domain.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    
    return domain


def _extract_domain(url: str) -> str:
    """Extract normalized domain from URL.
    
    Args:
        url: Full URL
    
    Returns:
        Normalized domain string
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        return _normalize_domain(domain)
    except Exception as e:
        logger.warning(f"Failed to parse URL {url}: {e}")
        # Fallback: try to extract domain manually
        return _normalize_domain(url)


def filter_urls(
    urls: List[str],
    allowlist: Optional[Set[str]] = None,
    blocklist: Optional[Set[str]] = None,
) -> List[str]:
    """Filter URLs based on domain allowlist/blocklist policy.
    
    Filtering logic:
    1. Remove URLs from blocklisted domains
    2. If allowlist is present and non-empty, only allow URLs from allowlisted domains
    3. If allowlist is empty/None, allow all except blocklisted
    
    Args:
        urls: List of URLs to filter
        allowlist: Set of allowed domains (None or empty = allow all except blocklist)
        blocklist: Set of blocked domains
    
    Returns:
        Filtered list of URLs (preserves original order)
    """
    if not urls:
        return []
    
    allowlist = allowlist or set()
    blocklist = blocklist or set()
    
    filtered: List[str] = []
    
    for url in urls:
        if not url or not isinstance(url, str):
            continue
        
        domain = _extract_domain(url)
        
        # Check blocklist first
        if blocklist and domain in blocklist:
            logger.debug(f"Blocked URL (blocklist): {url} (domain: {domain})")
            continue
        
        # Check allowlist (if present and non-empty)
        if allowlist:
            if domain not in allowlist:
                logger.debug(f"Blocked URL (not in allowlist): {url} (domain: {domain})")
                continue
        
        filtered.append(url)
    
    return filtered

