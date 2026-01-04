"""
Unit tests for domain policy filtering.

Tests verify:
- Wildcard pattern matching (*.gov, *.nature.com)
- Exact domain matching
- Strict allowlist filtering
- Stable ordering preservation
"""

import pytest
from src.orchestrator.web.domain_policy import (
    domain_matches,
    filter_urls_by_allowlist,
    default_allowlist,
    _extract_domain,
)


class TestDomainMatching:
    """Tests for domain_matches() function."""
    
    def test_wildcard_gov_matches_fda_gov(self):
        """Test that *.gov matches fda.gov."""
        assert domain_matches("*.gov", "fda.gov") is True
    
    def test_wildcard_gov_matches_www_fda_gov(self):
        """Test that *.gov matches www.fda.gov (normalized to fda.gov)."""
        # Note: _extract_domain normalizes www.fda.gov to fda.gov
        domain = _extract_domain("https://www.fda.gov/page")
        assert domain_matches("*.gov", domain) is True
    
    def test_wildcard_gov_matches_cdc_gov(self):
        """Test that *.gov matches cdc.gov."""
        assert domain_matches("*.gov", "cdc.gov") is True
    
    def test_wildcard_ieee_org_matches_spectrum_ieee_org(self):
        """Test that *.ieee.org matches spectrum.ieee.org."""
        assert domain_matches("*.ieee.org", "spectrum.ieee.org") is True
    
    def test_wildcard_nature_com_matches_www_nature_com(self):
        """Test that *.nature.com matches www.nature.com."""
        domain = _extract_domain("https://www.nature.com/article")
        assert domain_matches("*.nature.com", domain) is True
    
    def test_wildcard_europa_eu_matches_ec_europa_eu(self):
        """Test that *.europa.eu matches ec.europa.eu."""
        assert domain_matches("*.europa.eu", "ec.europa.eu") is True
    
    def test_exact_match(self):
        """Test that exact domain matches."""
        assert domain_matches("nature.com", "nature.com") is True
    
    def test_exact_match_case_insensitive(self):
        """Test that matching is case-insensitive."""
        assert domain_matches("NATURE.COM", "nature.com") is True
        assert domain_matches("*.GOV", "FDA.GOV") is True
    
    def test_wildcard_does_not_match_parent(self):
        """Test that *.gov does not match gov (parent domain)."""
        assert domain_matches("*.gov", "gov") is False
    
    def test_wildcard_does_not_match_unrelated(self):
        """Test that *.gov does not match unrelated domains."""
        assert domain_matches("*.gov", "example.com") is False
        assert domain_matches("*.gov", "nature.com") is False
    
    def test_exact_does_not_match_subdomain(self):
        """Test that exact pattern does not match subdomains."""
        assert domain_matches("nature.com", "www.nature.com") is False
        # But wildcard does
        assert domain_matches("*.nature.com", "www.nature.com") is True


class TestFilterUrlsByAllowlist:
    """Tests for filter_urls_by_allowlist() function."""
    
    def test_empty_urls_returns_empty(self):
        """Test that empty URL list returns empty."""
        assert filter_urls_by_allowlist([], ["*.gov"]) == []
    
    def test_empty_allowlist_returns_empty(self):
        """Test that empty allowlist returns empty (strict mode)."""
        urls = ["https://fda.gov/page", "https://example.com/page"]
        assert filter_urls_by_allowlist(urls, []) == []
    
    def test_filters_non_allowlisted_domains(self):
        """Test that non-allowlisted domains are dropped."""
        urls = [
            "https://fda.gov/page1",
            "https://example.com/page2",
            "https://cdc.gov/page3",
        ]
        allowlist = ["*.gov"]
        filtered = filter_urls_by_allowlist(urls, allowlist)
        
        assert len(filtered) == 2
        assert "https://fda.gov/page1" in filtered
        assert "https://cdc.gov/page3" in filtered
        assert "https://example.com/page2" not in filtered
    
    def test_preserves_ordering(self):
        """Test that filtered URLs preserve original order."""
        urls = [
            "https://fda.gov/page1",
            "https://cdc.gov/page2",
            "https://nih.gov/page3",
        ]
        allowlist = ["*.gov"]
        filtered = filter_urls_by_allowlist(urls, allowlist)
        
        assert filtered == urls  # All match, order preserved
    
    def test_multiple_patterns(self):
        """Test filtering with multiple allowlist patterns."""
        urls = [
            "https://fda.gov/page1",
            "https://www.nature.com/article",
            "https://example.com/page",
            "https://spectrum.ieee.org/article",
        ]
        allowlist = ["*.gov", "*.nature.com", "*.ieee.org"]
        filtered = filter_urls_by_allowlist(urls, allowlist)
        
        assert len(filtered) == 3
        assert "https://fda.gov/page1" in filtered
        assert "https://www.nature.com/article" in filtered
        assert "https://spectrum.ieee.org/article" in filtered
        assert "https://example.com/page" not in filtered
    
    def test_all_filtered_returns_empty(self):
        """Test that if all URLs are filtered, returns empty list."""
        urls = [
            "https://example.com/page1",
            "https://test.com/page2",
        ]
        allowlist = ["*.gov"]
        filtered = filter_urls_by_allowlist(urls, allowlist)
        
        assert filtered == []
    
    def test_stable_ordering_with_mixed_results(self):
        """Test that ordering is stable even when some URLs are filtered."""
        urls = [
            "https://fda.gov/page1",
            "https://example.com/page2",  # Filtered
            "https://cdc.gov/page3",
            "https://test.com/page4",  # Filtered
            "https://nih.gov/page5",
        ]
        allowlist = ["*.gov"]
        filtered = filter_urls_by_allowlist(urls, allowlist)
        
        # Should preserve order of allowlisted URLs
        assert filtered == [
            "https://fda.gov/page1",
            "https://cdc.gov/page3",
            "https://nih.gov/page5",
        ]


class TestDefaultAllowlist:
    """Tests for default_allowlist() function."""
    
    def test_returns_list(self):
        """Test that default_allowlist returns a list."""
        allowlist = default_allowlist()
        assert isinstance(allowlist, list)
        assert len(allowlist) > 0
    
    def test_includes_tier1_domains(self):
        """Test that default allowlist includes Tier 1 domains."""
        allowlist = default_allowlist()
        
        # Check for key patterns
        assert "*.gov" in allowlist
        assert "*.edu" in allowlist
        assert "*.nature.com" in allowlist
        assert "*.ieee.org" in allowlist
        assert "*.europa.eu" in allowlist
    
    def test_all_patterns_are_strings(self):
        """Test that all patterns in default allowlist are strings."""
        allowlist = default_allowlist()
        for pattern in allowlist:
            assert isinstance(pattern, str)
            assert len(pattern) > 0


class TestIntegration:
    """Integration tests for domain policy filtering."""
    
    def test_end_to_end_filtering(self):
        """Test end-to-end filtering with real URLs and patterns."""
        urls = [
            "https://www.fda.gov/drugs",
            "https://www.cdc.gov/health",
            "https://www.nature.com/articles/12345",
            "https://spectrum.ieee.org/tech-news",
            "https://ec.europa.eu/policy",
            "https://twitter.com/user/status",
            "https://example.com/page",
        ]
        
        allowlist = default_allowlist()
        filtered = filter_urls_by_allowlist(urls, allowlist)
        
        # Should include allowlisted domains
        assert "https://www.fda.gov/drugs" in filtered
        assert "https://www.cdc.gov/health" in filtered
        assert "https://www.nature.com/articles/12345" in filtered
        assert "https://spectrum.ieee.org/tech-news" in filtered
        assert "https://ec.europa.eu/policy" in filtered
        
        # Should exclude non-allowlisted domains
        assert "https://twitter.com/user/status" not in filtered
        assert "https://example.com/page" not in filtered

