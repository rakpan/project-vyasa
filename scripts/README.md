# Scripts Overview (DGX / Local-First)

## Quick Start (numbered)
1. Preflight (env + hardware + secrets): `./scripts/preflight_check.sh`
2. Start stack (detached): `./scripts/run_stack.sh start` or `./scripts/run_stack.sh start --opik`
3. Tail logs (optional): `./scripts/run_stack.sh logs [--opik] [service]`
4. Stop stack: `./scripts/run_stack.sh stop` (add `--opik` if you started with it)
5. Run tests (optional): `./scripts/run_tests.sh`
6. Opik datasets/evals (optional): see `scripts/opik/README.md`

## Scripts Inventory (selected)
- `run_stack.sh` — primary start/stop/logs wrapper (supports `--opik`).
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
