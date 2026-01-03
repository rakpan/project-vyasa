# 05 Telemetry and Observability

Content merged from `05-performance-and-observability.md`, `opik-observability.md`, `opik.md`, and `observatory_contract.md`.

## Performance Baselines
- Throughput and latency benchmarks for core services
- GPU/CPU utilization patterns and recommended alerts

## Telemetry Stack
- Structured logging for Orchestrator and Console
- Metrics collection (Prometheus/OpenMetrics)
- Tracing/Opik integration (non-blocking)

## Opik Observability

Opik provides a self-hosted "flight data recorder" for Vyasa. It is optional and disabled by default. Opik traces must never impact runtime decisions.

### Starting Opik

**Recommended**: Use the unified stack runner:
```bash
./scripts/run_stack.sh start --opik
```

This automatically:
- Creates the `vyasa-net` network if it doesn't exist
- Creates Opik data directories if needed (no sudo required)
- Checks for port conflicts before starting
- Waits for Opik services to be ready

**Alternative**: Manual start:
```bash
cd deploy
docker compose -f docker-compose.yml -f docker-compose.opik.yml up -d
```

### Stopping Opik

**Recommended**: Use the unified stack runner:
```bash
./scripts/run_stack.sh stop --opik
```

**Alternative**: Manual stop:
```bash
cd deploy
docker compose -f docker-compose.yml -f docker-compose.opik.yml down
```

### Services (compose override)
- `opik-postgres` (persisted at `/raid/vyasa/opik_data/postgres`)
- `opik-redis` (persisted at `/raid/vyasa/opik_data/redis`)
- `opik-api` (persisted at `/raid/vyasa/opik_data/opik`, exposed on `127.0.0.1:56500`)

### Vyasa Environment Variables
Set in your `.env` (optional):
- `OPIK_ENABLED=true`
- `OPIK_BASE_URL=http://opik-api:5000` (inside Docker network) or `http://127.0.0.1:56500` if calling from host
- `OPIK_API_KEY` if required by your Opik setup
- `OPIK_PROJECT_NAME=vyasa` (default)
- `OPIK_TIMEOUT_SECONDS=2`

If Opik is down or misconfigured, Vyasa continues normally (observe-only).

### What Gets Stored
- Trace metadata only: model id, expert/node tags, job_id/project_id, prompt hashes, token counts, durations.
- No raw prompt text is sent by default.

### Advisory Traces
- Advisory traces for node execution
- Handling trace failures (must not block workflow)
- Tagging jobs/projects for drill-down

### Troubleshooting

- **Check container logs**: 
  ```bash
  ./scripts/run_stack.sh logs --opik opik-api
  # Or manually:
  docker compose -f docker-compose.yml -f docker-compose.opik.yml logs opik-api
  ```

- **Directory permissions**: 
  - The script automatically creates `/raid/vyasa/opik_data/*` directories if possible
  - If creation fails, Docker will create them when containers start (owned by root)
  - No sudo required - Docker handles directory creation automatically

- **Network issues**: 
  - The script automatically creates the `vyasa-net` network if it doesn't exist
  - If you see "network vyasa-net declared as external, but could not be found", the script should handle this automatically

- **Port conflicts**: 
  - The script checks for port conflicts before starting
  - If port 11435 (drafter) is in use, you'll see a warning with resolution options

- **Verify ports**: Ports are bound to localhost only (127.0.0.1) for security

### Offline Evaluation Scaffold (optional)

- Build datasets from existing artifacts:
  - Tone: `python scripts/opik/build_tone_dataset.py <blocks.jsonl> out/tone.jsonl`
  - Precision: `python scripts/opik/build_precision_dataset.py <tables.jsonl> out/precision.jsonl`
- Run evals (Opik optional): `python scripts/opik/run_evals.py out/tone.jsonl`
  - If Opik is configured, records are submitted.
  - Otherwise a local summary is printed.

Note: Evals are out-of-band; Vyasa runtime never depends on Opik availability.

## Observatory API Contract

The observatory response is the single source of truth for the KPI dashboard. The backend **must** conform to this contract; the frontend consumes it without additional shaping.

### Response Shape

- Object keyed by panel:
  - `quality`, `context`, `performance`, `hardware`, `volume`
- Each panel object:
  - `status`: `"online" | "warning" | "critical"` (panel health)
  - `summary`: object of primary KPI point-in-time values (latest)
  - `series`: object of KPI sparkline series
    - Each series is an array of **exactly 60** points ordered oldest → newest
    - Point shape: `{ "timestamp": ISO-8601 string, "value": number }`

### Panel KPIs and Units

**Quality**
- `conflict_rate`: conflicts / vetted_claims (0–1 ratio)
- `unsupported_rate`: unsupported findings / vetted_claims (0–1 ratio)

**Context**
- `tokens_per_claim`: average tokens consumed per vetted claim (number)
- `retrieval_hit_rate_at_5`: fraction of claims where the correct source is in top-5 retrieval results (0–1 ratio)

**Performance**
- `p95_latency_ms`: end-to-end p95 latency in milliseconds (number)
- `tokens_per_sec`: throughput split by phase:
  - `prefill`: tokens/sec during prompt ingestion
  - `decode`: tokens/sec during generation

**Hardware**
- `uma_utilization_pct`: unified memory utilization percent (0–128 range maps to 0–128GB)
- `kv_cache_fill_pct`: KV cache fill level percent (0–100)

**Volume**
- `minted_claims_24h`: vetted claims minted in the last 24h (integer, verified by expert)

### Example (abbreviated)

```json
{
  "quality": {
    "status": "online",
    "summary": {
      "conflict_rate": 0.03,
      "unsupported_rate": 0.07
    },
    "series": {
      "conflict_rate": [
        { "timestamp": "2025-02-20T10:00:00Z", "value": 0.04 },
        { "timestamp": "2025-02-20T10:05:00Z", "value": 0.03 }
      ],
      "unsupported_rate": [
        { "timestamp": "2025-02-20T10:00:00Z", "value": 0.08 },
        { "timestamp": "2025-02-20T10:05:00Z", "value": 0.07 }
      ]
    }
  }
}
```

Refer to `schemas/observatory_response.schema.json` for the authoritative machine-readable schema.

## Dashboards and Alerting
- Recommended panels for queue depth, node latency, GPU/CPU use
- Alert thresholds for backpressure and failures
