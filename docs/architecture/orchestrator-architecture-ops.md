# Orchestrator Architecture & Ops (Flask/FastAPI Bridge)

Purpose: single place for runtime layout, entrypoints, and operational surfaces for the Orchestrator. For the full platform story, see `docs/README.md`. For operator procedures, see `docs/runbooks/*`.

## Runtime surfaces
- **Flask app (`app`)**: legacy ingestion and workflow routes (`/ingest/pdf`, `/workflow/submit`, project CRUD, jobs, manuscript). Max upload 100MB via `MAX_CONTENT_LENGTH`.
- **FastAPI gateway (`api_app`)**: observability router and SSE events. Mounts the Flask app via `a2wsgi.WSGIMiddleware` when available; if missing, returns 503 with guidance.
- **Ports**: exposed as `vyasa-orchestrator` on 8000 (see `deploy/docker-compose.yml`).

## Entry/bridge flow
- Imports and registers blueprints: knowledge, jobs, manuscript, ingestion (and claims when registered).
- Builds LangGraph workflow via `build_workflow()` once at import.
- Bridges Flask into FastAPI so a single ASGI surface serves both observability and legacy routes. Tests can skip the bridge by not installing `a2wsgi`.

## Event streaming
- **SSE endpoint**: `GET /events/{job_id}` on the FastAPI app. Uses per-job async queues with heartbeat on 30s timeout. Cleanup removes queues on cancel.
- **Internal publishers**: workflow runner calls `publish_event` for node start/telemetry, and `notify_sse_clients` for graph updates. Event queues live in `src/orchestrator/services/events.py`.

## Health and telemetry
- **Health**: `GET /health` (quick) and `GET /health?deep=true` (pings ArangoDB and worker). Returns 503 on dependency failure.
- **System pulse**: `GET /system/pulse` for hardware/software snapshot.
- **Metrics service**: `observatory_metrics_service.start()` runs unless `DISABLE_METRICS_SERVICE=true` or tests are active. Failure degrades gracefully with a warning.
- **Telemetry emitter**: initialized at module import; service wrappers in `src/orchestrator/services/telemetry.py`/`services/metrics.py`.

## Workflows (LangGraph)
- **State**: `ResearchState` TypedDict with required `jobId`/`threadId`. Checkpointing via `InMemorySaver`; all invokes pass `{"configurable": {"thread_id": jobId}}`.
- **Committee nodes**: cartographer, vision, critic, reframer (interrupt), synthesizer, tone validator, saver, etc. Progress mapping lives in the workflow runner and updates job status during stream.
- **Submission**: `/workflow/submit` accepts JSON or multipart PDF, requires `project_id`, hashes PDFs, may compute first-glance, and caches PDF text layers. Creates ingestion records and seeds corpus.

## Operational references
- **Runbooks**: use `docs/runbooks/operator-handbook.md` and `docs/runbooks/console-navigation.md` for procedures (restart, troubleshoot, UI flows).
- **Architecture maps**: see `docs/architecture/system-map.md` and `docs/architecture/module-map.md` for topology and module boundaries.
