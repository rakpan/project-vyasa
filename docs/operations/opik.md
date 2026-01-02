# Opik (Observe-Only) Integration

Opik provides a self-hosted “flight data recorder” for Vyasa. It is optional and disabled by default. Opik traces must never impact runtime decisions.

## Starting Opik

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

## Stopping Opik

**Recommended**: Use the unified stack runner:
```bash
./scripts/run_stack.sh stop --opik
```

**Alternative**: Manual stop:
```bash
cd deploy
docker compose -f docker-compose.yml -f docker-compose.opik.yml down
```

## Services (compose override)
- `opik-postgres` (persisted at `/raid/vyasa/opik_data/postgres`)
- `opik-redis` (persisted at `/raid/vyasa/opik_data/redis`)
- `opik-api` (persisted at `/raid/vyasa/opik_data/opik`, exposed on `127.0.0.1:56500`)

## Vyasa Environment Variables
Set in your `.env` (optional):
- `OPIK_ENABLED=true`
- `OPIK_BASE_URL=http://opik-api:5000` (inside Docker network) or `http://127.0.0.1:56500` if calling from host
- `OPIK_API_KEY` if required by your Opik setup
- `OPIK_PROJECT_NAME=vyasa` (default)
- `OPIK_TIMEOUT_SECONDS=2`

If Opik is down or misconfigured, Vyasa continues normally (observe-only).

## What Gets Stored
- Trace metadata only: model id, expert/node tags, job_id/project_id, prompt hashes, token counts, durations.
- No raw prompt text is sent by default.

## Troubleshooting

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
  - If port 11434 (drafter) is in use, you'll see a warning with resolution options

- **Verify ports**: Ports are bound to localhost only (127.0.0.1) for security

## Offline Evaluation Scaffold (optional)

- Build datasets from existing artifacts:
  - Tone: `python scripts/opik/build_tone_dataset.py <blocks.jsonl> out/tone.jsonl`
  - Precision: `python scripts/opik/build_precision_dataset.py <tables.jsonl> out/precision.jsonl`
- Run evals (Opik optional): `python scripts/opik/run_evals.py out/tone.jsonl`
  - If Opik is configured, records are submitted.
  - Otherwise a local summary is printed.

Note: Evals are out-of-band; Vyasa runtime never depends on Opik availability.
