"""
Observatory API router: read-only snapshot of Vyasa metrics.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from ..metrics_service import MetricsService, ObservatorySnapshot

# Singleton metrics engine; lifecycle managed by server startup.
metrics_service = MetricsService()


def get_metrics_service() -> MetricsService:
    return metrics_service


router = APIRouter(tags=["observatory"])


@router.get("/api/system/observatory", response_model=ObservatorySnapshot)
def get_observatory_snapshot(
    response: Response,
    service: MetricsService = Depends(get_metrics_service),
) -> ObservatorySnapshot:
    age = service.snapshot_age_seconds()
    if (not service.is_running()) or age is None or age > 300:
        raise HTTPException(
            status_code=503,
            detail={"message": "Metrics engine warming up or stale snapshot"},
        )

    snapshot = service.get_snapshot()
    response.headers["X-Vyasa-Snapshot-Age"] = str(int(age or 0.0))
    return snapshot
