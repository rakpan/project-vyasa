# Opik Observability (Optional, Observe-Only)

## Purpose
- Opik provides advisory, observe-only tracing and evaluation for Vyasa.
- It is non-blocking and never affects routing, acceptance, or job success.
- If Opik is down or misconfigured, Vyasa continues normally.

## What Opik Captures
- Node boundaries (start/end) with small summaries.
- Model metadata: expert/node name, model id, durations, token counts.
- Critic annotations (summaries only, no raw text).

## What Opik Does NOT Do
- No pass/fail decisions.
- No workflow routing.
- No prompt text storage by default.

## Enabling Opik
- Env vars (optional):
  - `OPIK_ENABLED`
  - `OPIK_BASE_URL`
  - `OPIK_API_KEY` (if required)
  - `OPIK_PROJECT_NAME` (default: `vyasa`)
  - `OPIK_TIMEOUT_SECONDS` (default: `2`)
- Self-hosted and local-first (see docker-compose.opik.yml).

## Viewing Traces
- Surface via the “Reasoning Diagnostics” button in failure/deadlock cases.
- Opens in a new tab; purely read-only.

## Failure Modes
- If Opik is unavailable, telemetry and workflow continue; Opik spans are skipped silently.
