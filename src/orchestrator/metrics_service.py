"""
MetricsEngine: aggregates telemetry, SGLang metrics, and ArangoDB signals into the
Vyasa Observatory contract.

Runs two background loops:
- Fast loop (10s): scrape SGLang/system metrics and fold in recent telemetry breadcrumbs.
- Slow loop (60s): query ArangoDB for Gold Layer outcomes (volume/quality/context).

The service maintains fixed-length (60-point) ring buffers for every series and
serves snapshots in O(1) from an in-memory cache.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

from arango import ArangoClient
from pydantic import BaseModel

from .collectors.sglang_metrics import SGLangMetricsCollector
from .collectors.system_metrics import SystemMetricsCollector
from ..shared.config import (
    ARANGODB_DB,
    ARANGODB_URL,
    ARANGODB_USER,
    TELEMETRY_PATH,
    get_arango_password,
    get_brain_url,
    get_vision_url,
    get_worker_url,
)
from ..shared.utils import get_utc_now
from ..shared.logger import get_logger

logger = get_logger("metrics_engine", __name__)

TELEMETRY_PATH = Path(TELEMETRY_PATH)


# -----------------------------
# Pydantic models (contract)
# -----------------------------

class SeriesPoint(BaseModel):
    timestamp: str
    value: float


class SeriesPointInt(BaseModel):
    timestamp: str
    value: int


class TokensPerSec(BaseModel):
    prefill: float
    decode: float


class PerformancePanel(BaseModel):
    status: str
    summary: Dict[str, Any]
    series: Dict[str, Any]


class HardwarePanel(BaseModel):
    status: str
    summary: Dict[str, Any]
    series: Dict[str, Any]


class QualityPanel(BaseModel):
    status: str
    summary: Dict[str, float]
    series: Dict[str, List[SeriesPoint]]


class ContextPanel(BaseModel):
    status: str
    summary: Dict[str, float]
    series: Dict[str, List[SeriesPoint]]


class VolumePanel(BaseModel):
    status: str
    summary: Dict[str, int]
    series: Dict[str, List[SeriesPointInt]]


class ObservatorySnapshot(BaseModel):
    generated_at: str
    window: Dict[str, float]
    sources: Dict[str, str]
    quality: QualityPanel
    context: ContextPanel
    performance: PerformancePanel
    hardware: HardwarePanel
    volume: VolumePanel


# -----------------------------
# Time series management
# -----------------------------

class TimeSeriesManager:
    """Fixed-length ring buffers for metrics (60 points each)."""

    def __init__(self, maxlen: int = 60):
        self.maxlen = maxlen
        self._series: Dict[str, Deque[Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def add_point(self, key: str, value: float, timestamp: Optional[str] = None) -> None:
        ts = timestamp or get_utc_now().isoformat()
        with self._lock:
            dq = self._series.get(key)
            if dq is None:
                dq = deque(maxlen=self.maxlen)
                self._series[key] = dq
            dq.append({"timestamp": ts, "value": float(value)})

    def get_series(self, key: str, default_value: float = 0.0) -> List[Dict[str, Any]]:
        with self._lock:
            dq = self._series.get(key)
            data = list(dq) if dq else []
        if not data:
            ts = get_utc_now()
            return [{"timestamp": (ts - timedelta(seconds=i)).isoformat(), "value": float(default_value)} for i in reversed(range(self.maxlen))]
        if len(data) < self.maxlen:
            try:
                first_ts = datetime.fromisoformat(data[0]["timestamp"].replace("Z", "+00:00"))
            except Exception:
                first_ts = get_utc_now()
            pad_count = self.maxlen - len(data)
            pad = [
                {
                    "timestamp": (first_ts - timedelta(seconds=pad_count - idx)).isoformat(),
                    "value": float(default_value),
                }
                for idx in range(pad_count)
            ]
            data = pad + data
        # Ensure exact length
        data = data[-self.maxlen :]
        assert len(data) == self.maxlen, f"series {key} must have {self.maxlen} points"
        return data

    def latest(self, key: str, default_value: float = 0.0) -> float:
        with self._lock:
            dq = self._series.get(key)
            if dq:
                return float(dq[-1]["value"])
        return float(default_value)

    def latest_timestamp(self, key: str) -> Optional[str]:
        with self._lock:
            dq = self._series.get(key)
            if dq:
                return dq[-1]["timestamp"]
        return None


# -----------------------------
# Metrics Engine
# -----------------------------

class MetricsService:
    def __init__(
        self,
        worker_urls: Optional[Iterable[str]] = None,
        telemetry_path: Path = TELEMETRY_PATH,
        fast_interval: float = 10.0,
        slow_interval: float = 60.0,
    ) -> None:
        self.worker_urls = list(worker_urls) if worker_urls else [
            get_brain_url(),
            get_worker_url(),
            get_vision_url(),
        ]
        self.telemetry_path = telemetry_path
        self.fast_interval = fast_interval
        self.slow_interval = slow_interval

        self.sglang_collector = SGLangMetricsCollector(self.worker_urls, timeout=2.0)
        self.system_collector = SystemMetricsCollector(timeout=2.0)

        self._prev_token_counters: Optional[Tuple[float, float, float]] = None  # (timestamp, prefill_total, decode_total)
        self._threads: List[threading.Thread] = []
        self._panel_status: Dict[str, str] = {
            "quality": "warning",
            "context": "warning",
            "performance": "warning",
            "hardware": "warning",
            "volume": "warning",
        }
        self._source_health: Dict[str, str] = {
            "sglang": "warning",
            "db": "warning",
            "telemetry": "warning",
        }

        self._series = TimeSeriesManager()
        self._stop_event = threading.Event()
        self._snapshot_lock = threading.Lock()
        self._snapshot: ObservatorySnapshot = self._empty_snapshot()
        self._last_snapshot_ts: datetime = get_utc_now()

        # DB client (lazy)
        self._db = None

    # ---------- Public API ----------
    def start(self) -> None:
        """Start background loops."""
        if self._threads:
            return
        fast_thread = threading.Thread(target=self._fast_loop, daemon=True)
        slow_thread = threading.Thread(target=self._slow_loop, daemon=True)
        self._threads = [fast_thread, slow_thread]
        for t in self._threads:
            t.start()

    def stop(self) -> None:
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=5.0)

    def get_snapshot(self) -> ObservatorySnapshot:
        """Return cached snapshot (O(1) read)."""
        with self._snapshot_lock:
            return self._snapshot

    def snapshot_age_seconds(self) -> Optional[float]:
        """Age of the cached snapshot in seconds."""
        if not self._last_snapshot_ts:
            return None
        return max(0.0, (get_utc_now() - self._last_snapshot_ts).total_seconds())

    def is_running(self) -> bool:
        """True if background loops have started and not stopped."""
        return bool(self._threads) and not self._stop_event.is_set()

    # ---------- Internal helpers ----------
    def _fast_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._collect_fast_path()
            except Exception as exc:  # pragma: no cover - background guardrail
                logger.warning("Fast loop failed", extra={"payload": {"error": str(exc)}})
            time.sleep(self.fast_interval)

    def _slow_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._collect_slow_path()
            except Exception as exc:  # pragma: no cover
                logger.warning("Slow loop failed", extra={"payload": {"error": str(exc)}})
            time.sleep(self.slow_interval)

    def _collect_fast_path(self) -> None:
        now = get_utc_now().isoformat()
        telemetry_events = self._load_recent_events(window_seconds=60)
        p95_latency = self._compute_p95_latency(telemetry_events)
        p50_latency = self._compute_p50_latency(telemetry_events)
        retrieval_hit_rate = self._compute_retrieval_hit_rate(telemetry_events)
        completion_tokens = self._sum_completion_tokens(telemetry_events)

        # SGLang metrics (includes kv cache fill/concurrency)
        sglang_payload = self.sglang_collector.collect()
        perf_raw = sglang_payload.get("performance", {})
        hardware_raw = sglang_payload.get("hardware", {})

        tps_prefill, tps_decode = self._compute_tps(perf_raw.get("tokens_per_sec"))
        cache_hit_rate = perf_raw.get("cache_hit_rate") or 0.0
        concurrency = perf_raw.get("concurrency") or 0.0
        kv_cache_fill_pct = hardware_raw.get("kv_cache_fill_pct") or 0.0
        has_sglang_signal = any(
            val
            for val in [
                perf_raw.get("tokens_per_sec", {}).get("prefill"),
                perf_raw.get("tokens_per_sec", {}).get("decode"),
                perf_raw.get("cache_hit_rate"),
                perf_raw.get("concurrency"),
                hardware_raw.get("kv_cache_fill_pct"),
            ]
        )
        self._source_health["sglang"] = "online" if has_sglang_signal else "warning"

        # System metrics
        hardware_payload = self.system_collector.collect().get("hardware", {})
        uma_utilization_pct = hardware_payload.get("uma_utilization_pct") or 0.0

        # Update time series
        self._series.add_point("performance.p95_latency_ms", p95_latency, timestamp=now)
        self._series.add_point("performance.p50_latency_ms", p50_latency, timestamp=now)
        self._series.add_point("performance.tokens_per_sec.prefill", tps_prefill, timestamp=now)
        self._series.add_point("performance.tokens_per_sec.decode", tps_decode, timestamp=now)
        self._series.add_point("performance.cache_hit_rate", cache_hit_rate, timestamp=now)
        self._series.add_point("performance.concurrency", concurrency, timestamp=now)

        self._series.add_point("hardware.kv_cache_fill_pct", kv_cache_fill_pct, timestamp=now)
        self._series.add_point("hardware.uma_utilization_pct", uma_utilization_pct, timestamp=now)

        # Context metrics that depend on telemetry (tokens per claim uses slow loop minted count)
        minted_latest = self._series.latest("volume.minted_claims_24h", default_value=1.0)
        tokens_per_claim = completion_tokens / minted_latest if minted_latest > 0 else 0.0
        self._series.add_point("context.tokens_per_claim", tokens_per_claim, timestamp=now)
        self._series.add_point("context.retrieval_hit_rate_at_5", retrieval_hit_rate, timestamp=now)

        # Panel statuses
        # Threshold-based statuses
        if p95_latency > 5000:
            self._panel_status["performance"] = "critical"
        elif p95_latency > 2000:
            self._panel_status["performance"] = "warning"
        else:
            self._panel_status["performance"] = "online"

        if uma_utilization_pct > 90:
            self._panel_status["hardware"] = "warning"
        else:
            self._panel_status["hardware"] = "online"

        self._panel_status["context"] = "online" if minted_latest > 0 else "warning"

        self._refresh_snapshot()

    def _collect_slow_path(self) -> None:
        """Query ArangoDB for volume/quality/context windowed metrics."""
        now = get_utc_now().isoformat()
        minted_claims = self._query_minted_claims_24h()
        conflict_rate = self._query_conflict_rate(minted_claims or 0)
        unsupported_rate = self._query_unsupported_rate() if minted_claims is not None else None

        # Update series
        self._series.add_point("volume.minted_claims_24h", minted_claims or 0, timestamp=now)
        self._series.add_point("quality.conflict_rate", conflict_rate or 0.0, timestamp=now)
        self._series.add_point("quality.unsupported_rate", unsupported_rate or 0.0, timestamp=now)

        if minted_claims is None:
            self._panel_status["volume"] = "warning"
            self._panel_status["quality"] = "warning"
            self._source_health["db"] = "warning"
        else:
            self._panel_status["volume"] = "online"
            self._panel_status["quality"] = "online" if minted_claims > 0 else "warning"
            self._source_health["db"] = "online"

        self._refresh_snapshot()

    def _rate_delta(self, prev: Tuple[float, float, float], current: Tuple[float, float, float]) -> Tuple[Optional[float], Optional[float]]:
        prev_ts, prev_prefill, prev_decode = prev
        cur_ts, cur_prefill, cur_decode = current
        delta_t = cur_ts - prev_ts
        if delta_t <= 0:
            return None, None
        prefill_tps = (cur_prefill - prev_prefill) / delta_t if cur_prefill is not None and prev_prefill is not None else None
        decode_tps = (cur_decode - prev_decode) / delta_t if cur_decode is not None and prev_decode is not None else None
        return prefill_tps, decode_tps

    def _compute_tps(self, counters: Optional[Dict[str, Any]]) -> Tuple[float, float]:
        """Convert token counters into TPS using previous sample."""
        if not counters:
            return self._series.latest("performance.tokens_per_sec.prefill", 0.0), self._series.latest("performance.tokens_per_sec.decode", 0.0)
        now = time.time()
        prefill_total = float(counters.get("prefill") or 0.0)
        decode_total = float(counters.get("decode") or 0.0)
        current = (now, prefill_total, decode_total)
        if self._prev_token_counters is None:
            self._prev_token_counters = current
            return 0.0, 0.0
        prefill_tps, decode_tps = self._rate_delta(self._prev_token_counters, current)
        self._prev_token_counters = current
        # Keep previous if delta invalid
        if prefill_tps is None:
            prefill_tps = self._series.latest("performance.tokens_per_sec.prefill", 0.0)
        if decode_tps is None:
            decode_tps = self._series.latest("performance.tokens_per_sec.decode", 0.0)
        return prefill_tps, decode_tps

    def _load_recent_events(self, window_seconds: int) -> List[Dict[str, Any]]:
        if not self.telemetry_path.exists():
            self._source_health["telemetry"] = "warning"
            return []
        cutoff = get_utc_now() - timedelta(seconds=window_seconds)
        try:
            # Read a manageable tail (last ~5000 lines)
            with self.telemetry_path.open("rb") as fh:
                fh.seek(0, 2)
                file_size = fh.tell()
                fh.seek(max(file_size - 200_000, 0))  # ~200KB tail
                data = fh.read().decode("utf-8", errors="ignore")
            lines = data.strip().splitlines()[-5000:]
            events: List[Dict[str, Any]] = []
            for line in lines:
                try:
                    evt = json.loads(line)
                    ts = evt.get("timestamp")
                    if not ts:
                        continue
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt >= cutoff:
                        events.append(evt)
                except Exception:
                    continue
            self._source_health["telemetry"] = "online"
            return events
        except Exception as exc:
            logger.warning("Failed to read telemetry events", extra={"payload": {"error": str(exc)}})
            self._source_health["telemetry"] = "warning"
            return []

    def _compute_p95_latency(self, events: List[Dict[str, Any]]) -> float:
        durations = [float(e.get("duration_ms", 0)) for e in events if e.get("event_type") == "node_execution" and e.get("duration_ms") is not None]
        if not durations:
            return 0.0
        durations.sort()
        idx = int(0.95 * (len(durations) - 1))
        return durations[idx]

    def _compute_p50_latency(self, events: List[Dict[str, Any]]) -> float:
        durations = [float(e.get("duration_ms", 0)) for e in events if e.get("event_type") == "node_execution" and e.get("duration_ms") is not None]
        if not durations:
            return 0.0
        durations.sort()
        mid = 0.5 * (len(durations) - 1)
        lower = int(mid)
        upper = min(len(durations) - 1, lower + 1)
        frac = mid - lower
        return durations[lower] * (1 - frac) + durations[upper] * frac

    def _compute_retrieval_hit_rate(self, events: List[Dict[str, Any]]) -> float:
        retrievals = [e for e in events if e.get("event_type") == "retrieval"]
        if not retrievals:
            return 0.0
        hits = sum(1 for e in retrievals if e.get("metadata", {}).get("retrieval_hit") is True)
        return hits / len(retrievals)

    def _sum_completion_tokens(self, events: List[Dict[str, Any]]) -> float:
        total = 0.0
        for e in events:
            if e.get("event_type") != "llm_call":
                continue
            usage = e.get("metadata", {}).get("usage") or {}
            completion = usage.get("completion_tokens") or usage.get("output_tokens")
            if completion is not None:
                total += float(completion)
        return total

    def _db_client(self):
        if self._db:
            return self._db
        try:
            client = ArangoClient(hosts=ARANGODB_URL)
            self._db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
            return self._db
        except Exception as exc:
            logger.warning("Arango connection failed", extra={"payload": {"error": str(exc)}})
            self._db = None
            return None

    def _query_minted_claims_24h(self) -> Optional[int]:
        db = self._db_client()
        if not db:
            return None
        if not db.has_collection("extractions"):
            return None
        try:
            query = """
            FOR e IN extractions
              LET created = e.created_at ?? e.timestamp ?? e.saved_at
              LET created_ts = created != null ? DATE_TIMESTAMP(created) : null
              FILTER created_ts == null OR created_ts >= DATE_NOW() - 86400000
              FOR t IN e.graph.triples
                FILTER t.is_expert_verified == true
                COLLECT WITH COUNT INTO count
              RETURN count
            """
            cursor = db.aql.execute(query, batch_size=1000, max_runtime=10)
            counts = list(cursor)
            return counts[0] if counts else 0
        except Exception as exc:
            logger.warning("Failed to query minted claims", extra={"payload": {"error": str(exc)}})
            return None

    def _query_conflict_rate(self, vetted_claims: int) -> Optional[float]:
        db = self._db_client()
        if not db or vetted_claims <= 0:
            return None
        alias_count = 0
        try:
            if db.has_collection("node_aliases"):
                cursor = db.aql.execute("FOR a IN node_aliases COLLECT WITH COUNT INTO c RETURN c", max_runtime=10)
                alias_vals = list(cursor)
                alias_count = alias_vals[0] if alias_vals else 0
        except Exception as exc:
            logger.warning("Failed to query alias edges", extra={"payload": {"error": str(exc)}})
            return None
        if vetted_claims == 0:
            return 0.0
        return float(alias_count) / float(vetted_claims)

    def _query_unsupported_rate(self) -> Optional[float]:
        """Compute unsupported_rate from claims where is_supported == false in last 24h."""
        db = self._db_client()
        if not db or not db.has_collection("extractions"):
            return None
        try:
            total_query = """
            FOR e IN extractions
              LET created = e.created_at ?? e.timestamp ?? e.saved_at
              LET created_ts = created != null ? DATE_TIMESTAMP(created) : null
              FILTER created_ts == null OR created_ts >= DATE_NOW() - 86400000
              LET claims = e.graph.claims
              FILTER claims != null
              FOR c IN claims
                COLLECT WITH COUNT INTO count
              RETURN count
            """
            unsupported_query = """
            FOR e IN extractions
              LET created = e.created_at ?? e.timestamp ?? e.saved_at
              LET created_ts = created != null ? DATE_TIMESTAMP(created) : null
              FILTER created_ts == null OR created_ts >= DATE_NOW() - 86400000
              LET claims = e.graph.claims
              FILTER claims != null
              FOR c IN claims
                FILTER c.is_supported == false
                COLLECT WITH COUNT INTO count
              RETURN count
            """
            total_cursor = db.aql.execute(total_query, batch_size=1000, max_runtime=10)
            unsupported_cursor = db.aql.execute(unsupported_query, batch_size=1000, max_runtime=10)
            total = list(total_cursor)
            unsupported = list(unsupported_cursor)
            total_claims = total[0] if total else 0
            unsupported_claims = unsupported[0] if unsupported else 0
            if total_claims == 0:
                return 0.0
            return float(unsupported_claims) / float(total_claims)
        except Exception as exc:
            logger.warning("Failed to query unsupported rate", extra={"payload": {"error": str(exc)}})
            return None

    def _refresh_snapshot(self) -> None:
        """Rebuild cached snapshot from latest series values."""
        quality_summary = {
            "conflict_rate": self._series.latest("quality.conflict_rate", 0.0),
            "unsupported_rate": self._series.latest("quality.unsupported_rate", 0.0),
        }
        context_summary = {
            "tokens_per_claim": self._series.latest("context.tokens_per_claim", 0.0),
            "retrieval_hit_rate_at_5": self._series.latest("context.retrieval_hit_rate_at_5", 0.0),
        }
        perf_summary = {
            "p95_latency_ms": self._series.latest("performance.p95_latency_ms", 0.0),
            "p50_latency_ms": self._series.latest("performance.p50_latency_ms", 0.0),
            "tokens_per_sec": {
                "prefill": self._series.latest("performance.tokens_per_sec.prefill", 0.0),
                "decode": self._series.latest("performance.tokens_per_sec.decode", 0.0),
            },
        }
        hardware_summary = {
            "uma_utilization_pct": self._series.latest("hardware.uma_utilization_pct", 0.0),
            "kv_cache_fill_pct": self._series.latest("hardware.kv_cache_fill_pct", 0.0),
        }
        volume_summary = {
            "minted_claims_24h": int(self._series.latest("volume.minted_claims_24h", 0.0)),
        }

        quality_series = {
            "conflict_rate": [SeriesPoint(**p) for p in self._series.get_series("quality.conflict_rate")],
            "unsupported_rate": [SeriesPoint(**p) for p in self._series.get_series("quality.unsupported_rate")],
        }
        context_series = {
            "tokens_per_claim": [SeriesPoint(**p) for p in self._series.get_series("context.tokens_per_claim")],
            "retrieval_hit_rate_at_5": [SeriesPoint(**p) for p in self._series.get_series("context.retrieval_hit_rate_at_5")],
        }
        perf_series = {
            "p95_latency_ms": [SeriesPoint(**p) for p in self._series.get_series("performance.p95_latency_ms")],
            "p50_latency_ms": [SeriesPoint(**p) for p in self._series.get_series("performance.p50_latency_ms")],
            "tokens_per_sec": {
                "prefill": [SeriesPoint(**p) for p in self._series.get_series("performance.tokens_per_sec.prefill")],
                "decode": [SeriesPoint(**p) for p in self._series.get_series("performance.tokens_per_sec.decode")],
            },
        }
        hardware_series = {
            "uma_utilization_pct": [SeriesPoint(**p) for p in self._series.get_series("hardware.uma_utilization_pct")],
            "kv_cache_fill_pct": [SeriesPoint(**p) for p in self._series.get_series("hardware.kv_cache_fill_pct")],
        }
        volume_series = {
            "minted_claims_24h": [
                SeriesPointInt(timestamp=p["timestamp"], value=int(p.get("value", 0)))
                for p in self._series.get_series("volume.minted_claims_24h")
            ],
        }

        snapshot = ObservatorySnapshot(
            generated_at=get_utc_now().isoformat(),
            window={
                "fast_interval": float(self.fast_interval),
                "slow_interval": float(self.slow_interval),
            },
            sources=dict(self._source_health),
            quality=QualityPanel(
                status=self._panel_status.get("quality", "warning"),
                summary=quality_summary,
                series=quality_series,
            ),
            context=ContextPanel(
                status=self._panel_status.get("context", "warning"),
                summary=context_summary,
                series=context_series,
            ),
            performance=PerformancePanel(
                status=self._panel_status.get("performance", "warning"),
                summary=perf_summary,
                series=perf_series,
            ),
            hardware=HardwarePanel(
                status=self._panel_status.get("hardware", "warning"),
                summary=hardware_summary,
                series=hardware_series,
            ),
            volume=VolumePanel(
                status=self._panel_status.get("volume", "warning"),
                summary=volume_summary,
                series=volume_series,
            ),
        )

        with self._snapshot_lock:
            self._snapshot = snapshot
            self._last_snapshot_ts = get_utc_now()

    def _empty_snapshot(self) -> ObservatorySnapshot:
        """Initialize snapshot with zeros to satisfy schema."""
        now = get_utc_now().isoformat()
        def series_block():
            return [SeriesPoint(timestamp=now, value=0.0) for _ in range(60)]
        def series_block_int():
            return [SeriesPointInt(timestamp=now, value=0) for _ in range(60)]

        return ObservatorySnapshot(
            generated_at=now,
            window={"fast_interval": float(self.fast_interval), "slow_interval": float(self.slow_interval)},
            sources=dict(self._source_health),
            quality=QualityPanel(
                status="warning",
                summary={"conflict_rate": 0.0, "unsupported_rate": 0.0},
                series={"conflict_rate": series_block(), "unsupported_rate": series_block()},
            ),
            context=ContextPanel(
                status="warning",
                summary={"tokens_per_claim": 0.0, "retrieval_hit_rate_at_5": 0.0},
                series={"tokens_per_claim": series_block(), "retrieval_hit_rate_at_5": series_block()},
            ),
            performance=PerformancePanel(
                status="warning",
                summary={"p95_latency_ms": 0.0, "p50_latency_ms": 0.0, "tokens_per_sec": {"prefill": 0.0, "decode": 0.0}},
                series={
                    "p95_latency_ms": series_block(),
                    "p50_latency_ms": series_block(),
                    "tokens_per_sec": {"prefill": series_block(), "decode": series_block()},
                },
            ),
            hardware=HardwarePanel(
                status="warning",
                summary={"uma_utilization_pct": 0.0, "kv_cache_fill_pct": 0.0},
                series={
                    "uma_utilization_pct": series_block(),
                    "kv_cache_fill_pct": series_block(),
                },
            ),
            volume=VolumePanel(
                status="warning",
                summary={"minted_claims_24h": 0},
                series={"minted_claims_24h": series_block_int()},
            ),
        )
