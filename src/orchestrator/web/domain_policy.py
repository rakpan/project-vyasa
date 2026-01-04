"""
Domain policy filtering for web augmentation.

Filters URLs based on allowlist/blocklist configuration,
aligning with Vyasa's safety and governance principles.

Supports wildcard patterns (e.g., *.gov, *.nature.com) for flexible
domain matching while maintaining strict filtering.
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
                norm = _normalize_domain(domain)
                if norm:
                    allowlist.add(norm)
    
    if blocklist_str:
        for domain in blocklist_str.split(","):
            domain = domain.strip()
            if domain:
                norm = _normalize_domain(domain)
                if norm:
                    blocklist.add(norm)
    
    return allowlist, blocklist


def _normalize_domain(domain: str) -> str:
    """Normalize domain name (strip www., protocol, path).
    
    Args:
        domain: Domain string (may include protocol, www, path)
    
    Returns:
        Normalized domain (lowercase, no www., no protocol, no path)
    """
    # Prepend scheme if missing so urlparse can extract hostname
    candidate = domain.strip()
    if not candidate:
        return ""
    if "://" not in candidate:
        candidate = f"//{candidate}"
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    # Allow only hostname characters (letters, digits, dots, hyphens)
    if not re.fullmatch(r"[a-z0-9.-]+", host):
        return ""
    return host


def _extract_domain(url: str) -> str:
    """Extract normalized domain from URL.
    
    Args:
        url: Full URL
    
    Returns:
        Normalized domain string
    """
    try:
        parsed = urlparse(url if "://" in url else f"//{url}")
        domain = parsed.hostname or ""
        return _normalize_domain(domain)
    except Exception as e:
        logger.warning(f"Failed to parse URL {url}: {e}")
        # Fallback: try to extract domain manually
        return _normalize_domain(url)


def domain_matches(pattern: str, domain: str) -> bool:
    """Check if a domain matches a pattern (supports wildcard prefix).
    
    Supports:
    - Wildcard prefix: `*.gov` matches `fda.gov`, `www.fda.gov`, `cdc.gov`
    - Exact match: `nature.com` matches only `nature.com` (not `www.nature.com` unless pattern is `*.nature.com`)
    
    Args:
        pattern: Pattern string (may start with `*.` for wildcard)
        domain: Normalized domain string to match
    
    Returns:
        True if domain matches pattern, False otherwise
    """
    if not pattern or not domain:
        return False
    
    pattern = pattern.strip().lower()
    domain = domain.lower()
    
    # Wildcard prefix pattern (e.g., *.gov, *.nature.com)
    if pattern.startswith("*."):
        # Remove wildcard prefix
        suffix = pattern[2:]  # Remove "*."
        # Match if domain ends with suffix (with optional leading dot)
        # Examples: *.gov matches fda.gov, www.fda.gov, cdc.gov
        #           *.nature.com matches www.nature.com, nature.com (if normalized)
        if domain == suffix or domain.endswith("." + suffix):
            return True
    
    # Exact match
    if pattern == domain:
        return True
    
    return False


def default_allowlist() -> List[str]:
    """Return default Tier 1 domain allowlist for high-fidelity sources.
    
    Returns:
        List of domain patterns (wildcard or exact) for Tier 1 sources
    """
    return [
        # Academic and research institutions
        "*.edu",
        "*.ac.uk",
        "*.ac.jp",
        # Government sources
        "*.gov",
        "*.gov.uk",
        "*.europa.eu",
        # Scientific publishers
        "*.nature.com",
        "*.science.org",
        "*.cell.com",
        "*.elsevier.com",
        "*.springer.com",
        "*.ieee.org",
        "*.acm.org",
        "*.arxiv.org",
        # Medical and health
        "*.nih.gov",
        "*.who.int",
        "*.cdc.gov",
        "*.fda.gov",
        # International organizations
        "*.un.org",
        "*.unesco.org",
        "*.oecd.org",
        "*.worldbank.org",
    ]


def filter_urls_by_allowlist(
    urls: List[str],
    allowlist_patterns: List[str],
) -> List[str]:
    """Strictly filter URLs by allowlist patterns (only allowlisted domains pass).
    
    This is a strict filter: any URL not matching an allowlist pattern is dropped.
    Preserves deterministic ordering (stable sort by original position).
    
    Args:
        urls: List of URLs to filter
        allowlist_patterns: List of domain patterns (wildcard or exact)
    
    Returns:
        Filtered list of URLs (preserves original order, only allowlisted domains)
    """
    if not urls:
        return []
    
    if not allowlist_patterns:
        # Empty allowlist means no URLs allowed (strict mode)
        return []
    
    filtered: List[str] = []
    
    for url in urls:
        if not url or not isinstance(url, str):
            continue
        
        domain = _extract_domain(url)
        if not domain:
            continue
        
        # Check if domain matches any allowlist pattern
        matched = False
        for pattern in allowlist_patterns:
            if domain_matches(pattern, domain):
                matched = True
                break
        
        if matched:
            filtered.append(url)
        else:
            logger.debug(f"Filtered URL (not in allowlist): {url} (domain: {domain})")
    
    return filtered


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
    
    Note: This function uses exact domain matching. For wildcard patterns,
    use `filter_urls_by_allowlist()` instead.
    
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
