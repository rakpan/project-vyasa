# Configuration Reference (Env Flags)

Single source for common Vyasa env flags. API docs should link here instead of repeating tables.

## Prompt Registry / Opik
- `PROMPT_REGISTRY_ENABLED` (default: false unless set or `OPIK_ENABLED=true`)
- `OPIK_ENABLED` (default: false), `OPIK_BASE_URL`, `OPIK_API_KEY`
- `PROMPT_TAG` (default: `production`), `PROMPT_CACHE_SECONDS` (default: `300`)
- `OPIK_TIMEOUT_SECONDS` (default: `2`)

## Orchestrator Runtime
- `DISABLE_METRICS_SERVICE` (default: false) — skip observatory metrics thread.
- `MAX_CONTENT_LENGTH` (Flask) — set to 100MB by code; can override for uploads.

## Data/Services
- ArangoDB: `ARANGODB_DB` (default: `project_vyasa`), `ARANGODB_USER` (default: `root`), `ARANGODB_PASSWORD`.
- Memory/graph URL: `MEMORY_URL` (used by orchestrator).
- Qdrant: `QDRANT_URL` (vector DB).
- Worker/Brain/Vision/Drafter URLs: see `src/shared/config.py` for defaults; override via env.

## Testing / Local
- Set `PROMPT_REGISTRY_ENABLED=0 OPIK_ENABLED=0` for fast unit tests (no Opik calls).
- Use localhost overrides in `src/tests/unit/conftest.py` firewalls; no extra env needed.

See `src/shared/config.py` for the full list of defaults and parsing rules.
