"""
Librarian kernel telemetry hooks.

Logs retrieval breadcrumbs so downstream dashboards can compute hit rates and
recall quality without coupling to retrieval implementation details.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .telemetry import TelemetryEmitter


class LibrarianKernel:
    """Thin wrapper to emit retrieval telemetry from the Librarian."""

    def __init__(self, emitter: Optional[TelemetryEmitter] = None) -> None:
        self.emitter = emitter or TelemetryEmitter()

    def emit_retrieval(
        self,
        *,
        job_id: Optional[str],
        project_id: Optional[str],
        retrieval_hit: bool,
        max_score: Optional[float],
        chunk_count: int,
        node_name: str = "librarian",
        started_at: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Alias for log_retrieval_metrics to ensure instrumentation is used."""
        self.log_retrieval_metrics(
            job_id=job_id,
            project_id=project_id,
            retrieval_hit=retrieval_hit,
            max_score=max_score,
            chunk_count=chunk_count,
            node_name=node_name,
            started_at=started_at,
            metadata=metadata,
        )

    def log_retrieval_metrics(
        self,
        *,
        job_id: Optional[str],
        project_id: Optional[str],
        retrieval_hit: bool,
        max_score: Optional[float],
        chunk_count: int,
        node_name: str = "librarian",
        started_at: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a retrieval event with hit rate, scores, and chunk counts."""
        duration_ms = None
        if started_at is not None:
            duration_ms = (time.perf_counter() - started_at) * 1000
        if duration_ms is None:
            duration_ms = 0.0

        meta = dict(metadata or {})
        meta.update(
            {
                "retrieval_hit": bool(retrieval_hit),
                "max_score": max_score,
                "chunk_count": chunk_count,
            }
        )

        self.emitter.emit_event(
            "retrieval",
            {
                "job_id": job_id,
                "project_id": project_id,
                "node_name": node_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": duration_ms,
                "metadata": meta,
            },
        )
