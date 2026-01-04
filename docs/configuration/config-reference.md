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

## Web Augmentation (Optional)
- `WEB_AUGMENTATION_ENABLED` (default: `false`) — Enable web search and scraping via Firecrawl sidecar.
- `GOOGLE_SEARCH_API_KEY` — Google Custom Search API key (required if enabled).
- `GOOGLE_SEARCH_ENGINE_ID` — Google Custom Search Engine ID (required if enabled).
- `FIRECRAWL_SERVICE_URL` (default: `http://firecrawl:3002`) — Firecrawl HTTP service endpoint (use `http://firecrawl:3002` for Docker, `http://localhost:3002` for local).
- `WEB_DOMAIN_ALLOWLIST` — Comma-separated allowed domains (empty = allow all except blocklist).
- `WEB_DOMAIN_BLOCKLIST` (default: social media sites) — Comma-separated blocked domains.
- `WEB_MAX_URLS` (default: `10`) — Maximum URLs to fetch per query.
- `WEB_MAX_PAGES` (default: `25`) — Maximum pages to scrape per URL.
- `WEB_TIMEOUT_SECONDS` (default: `30`) — HTTP timeout for Firecrawl requests.

**Safety Notes:**
- Firecrawl is an HTTP-only sidecar service; no SDK imports (preserves AGPL boundaries).
- Web augmentation is disabled by default; set `WEB_AUGMENTATION_ENABLED=true` to enable.

**Performance Notes:**
- Firecrawl runs CPU-only; GPUs are reserved for vyasa-worker inference.
- Web scraping is asynchronous and does not block workflow execution.

## Testing / Local
- Set `PROMPT_REGISTRY_ENABLED=0 OPIK_ENABLED=0` for fast unit tests (no Opik calls).
- Use localhost overrides in `src/tests/unit/conftest.py` firewalls; no extra env needed.

See `src/shared/config.py` for the full list of defaults and parsing rules.
