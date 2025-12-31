"""
SGLang metrics scraper for Prometheus exposition endpoints.

Fetches /metrics from SGLang workers and normalizes into Observatory-ready
performance and hardware snippets.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from prometheus_client.parser import text_string_to_metric_families

logger = logging.getLogger(__name__)

MetricDict = Dict[str, float]


class SGLangMetricsCollector:
    """Scrape SGLang Prometheus endpoints and normalize key metrics."""

    def __init__(self, worker_urls: Iterable[str], timeout: float = 2.0) -> None:
        # Default to localhost brain port if none provided
        urls = list(worker_urls)
        if not urls:
            urls = ["http://localhost:30000"]
        self.worker_urls = urls
        self.timeout = timeout

    def _fetch(self, url: str) -> Optional[str]:
        try:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # pragma: no cover - network errors are expected
            logger.warning("Failed to fetch SGLang metrics", extra={"payload": {"url": url, "error": str(exc)}})
            return None

    def _aggregate_metric(self, families: Dict[str, Any], name: str) -> Optional[float]:
        fam = families.get(name)
        if fam is None:
            return None
        total = 0.0
        has_sample = False
        for sample in fam.samples:
            # sample.value can be int or float
            total += float(sample.value)
            has_sample = True
        return total if has_sample else None

    def _parse(self, text: str) -> Dict[str, Any]:
        families: Dict[str, Any] = {}
        for family in text_string_to_metric_families(text):
            families[family.name] = family

        prefill = self._aggregate_metric(families, "sglang:prompt_tokens_total")
        decode = self._aggregate_metric(families, "sglang:generation_tokens_total")
        cache_hit = self._aggregate_metric(families, "sglang:cache_hit_rate")
        concurrency = self._aggregate_metric(families, "sglang:num_running_reqs")

        # KV cache fill: try known gauges; fall back to token_usage ratio if present
        kv_gauge_candidates = [
            "sglang:token_usage",  # often a ratio 0-1 of occupied slots
            "sglang:kv_cache_usage",
            "sglang:kv_cache_usage_ratio",
            "sglang:kv_cache_fill_id",
            "sglang_kv_token_usage_ratio",
        ]
        kv_fill_pct = None
        for candidate in kv_gauge_candidates:
            val = self._aggregate_metric(families, candidate)
            if val is not None:
                # If the metric is already a percentage, keep; if it's a ratio <=1, scale
                kv_fill_pct = float(val) * 100 if val <= 1.5 else float(val)
                break

        return {
            "prefill_tokens_total": prefill,
            "decode_tokens_total": decode,
            "cache_hit_rate": cache_hit,
            "concurrency": concurrency,
            "kv_cache_fill_pct": kv_fill_pct,
            "status": "online",
        }

    def collect(self) -> Dict[str, Any]:
        """Scrape all workers and return normalized aggregates."""
        aggregates: List[Dict[str, Any]] = []
        for base_url in self.worker_urls:
            url = f"{base_url.rstrip('/')}/metrics"
            text = self._fetch(url)
            if not text:
                continue
            parsed = self._parse(text)
            aggregates.append(parsed)

        if not aggregates:
            logger.warning("No SGLang metrics scraped; marking source degraded")
            return {
                "status": "degraded",
                "performance": {
                    "tokens_per_sec": {"prefill": None, "decode": None},
                    "cache_hit_rate": None,
                    "concurrency": None,
                },
                "hardware": {"kv_cache_fill_pct": None},
            }

        def _sum(key: str) -> Optional[float]:
            vals = [p[key] for p in aggregates if p.get(key) is not None]
            return float(sum(vals)) if vals else None

        def _avg(key: str) -> Optional[float]:
            vals = [p[key] for p in aggregates if p.get(key) is not None]
            return float(sum(vals) / len(vals)) if vals else None

        def _max(key: str) -> Optional[float]:
            vals = [p[key] for p in aggregates if p.get(key) is not None]
            return float(max(vals)) if vals else None

        performance = {
            # Counters aggregated across workers; downstream can rate-convert
            "tokens_per_sec": {
                "prefill": _sum("prefill_tokens_total"),
                "decode": _sum("decode_tokens_total"),
            },
            "cache_hit_rate": _avg("cache_hit_rate"),
            "concurrency": _sum("concurrency"),
        }

        hardware = {
            "kv_cache_fill_pct": _max("kv_cache_fill_pct"),
        }

        return {"status": "online", "performance": performance, "hardware": hardware}
