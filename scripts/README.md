# Scripts Overview (DGX / Local-First)

## Quick Start
- Start Vyasa (no Opik): `./scripts/run_stack.sh up --detach`
- Start Vyasa + Opik: `./scripts/run_stack.sh up --opik --detach`
- Stop stack: `./scripts/run_stack.sh down [--opik]`
- Logs: `./scripts/run_stack.sh logs [--opik] [service]`
- Run tests: `./scripts/run_tests.sh`
- Generate Opik datasets: see `scripts/opik/README.md`

## Scripts Inventory (selected)
- `init_vyasa.sh` — sequential startup; sources deploy/.env; uses docker compose.
- `preflight_check.sh` — hardware/config checks; auto-gens secrets if missing.
- `run_mock_llm.sh` — starts mock LLM server (no GPU).
- `run_tests.sh` / `test_local.sh` — pytest runners.
- `vyasa-cli.sh` — operational helpers (merge, etc.).
- `watchdog.sh` — observatory watchdog (restart actions, telemetry log).
- `run_stack.sh` — unified compose wrapper with optional `--opik`.
- `opik/` — offline dataset/eval scripts (observe-only; no runtime impact).
- `test_scripts.sh` — lint/sanity (shellcheck if available).

## Opik (Optional)
- Controlled via env: `OPIK_ENABLED`, `OPIK_BASE_URL`, `OPIK_API_KEY`, `OPIK_PROJECT_NAME`, `OPIK_TIMEOUT_SECONDS`.
- `run_stack.sh --opik` adds `deploy/docker-compose.opik.yml`.
- If Opik is disabled/missing, scripts continue normally.

## Change Summary
- Added shared helpers (`scripts/lib/env.sh`) for defaults, cmd checks, boolean parsing, Opik gating.
- Added `run_stack.sh` to reduce duplication; other scripts now source the helper.
- Added offline Opik dataset/eval scripts and docs.
