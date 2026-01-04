"""
Web augmentation services for Project Vyasa.

Provides web discovery and scraping capabilities via Firecrawl sidecar.
"""

from .discovery import WebDiscoveryService
from .domain_policy import filter_urls, parse_domain_lists
from .firecrawl import FirecrawlBridge
from .normalizer import EvidenceNormalizer
from .augmentation_orchestrator import AugmentationOrchestrator

__all__ = [
    "WebDiscoveryService",
    "filter_urls",
    "parse_domain_lists",
    "FirecrawlBridge",
    "EvidenceNormalizer",
    "AugmentationOrchestrator",
]

