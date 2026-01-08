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
- Worker/Brain/Vision URLs: see `src/shared/config.py` for defaults; override via env.

## Web Augmentation (Optional)
- `WEB_AUGMENTATION_ENABLED` (default: `false`) — Enable web search and scraping via Firecrawl Cloud.
- `WORKBENCH_WEB_SEARCH_ENABLED` (default: `false`) — Enable web search panel in workbench UI.
- `GOOGLE_SEARCH_API_KEY` — Google Custom Search API key (required if web search enabled).
- `GOOGLE_SEARCH_ENGINE_ID` — Google Custom Search Engine ID (PSE cx id, required if web search enabled).
- `WEB_MAX_SEARCH_RESULTS` (default: `10`) — Maximum search results per query (Google API max is 10 per request).

### Firecrawl Cloud Configuration
- `FIRECRAWL_MODE` (default: `cloud`) — Firecrawl deployment mode. Use `cloud` for Firecrawl Cloud API.
- `FIRECRAWL_API_KEY` — Firecrawl Cloud API key (required if `WEB_AUGMENTATION_ENABLED=true`).
  - Sign up at https://firecrawl.dev to obtain API key
  - Free tier includes 500 requests/month
- `FIRECRAWL_BASE_URL` (default: `https://api.firecrawl.dev`) — Firecrawl Cloud API endpoint.
- `FIRECRAWL_MONTHLY_QUOTA` (default: `500`) — Monthly quota limit for Firecrawl Cloud (free tier).
  - Quota is enforced via `QuotaManager` in `src/orchestrator/web/quota.py`
  - Usage tracked in ArangoDB `web_usage` collection (keyed by YYYY-MM)
  - When quota exceeded, operations return `ReviewTask` with status `FAILED` and reason `quota_exceeded`
- `FIRECRAWL_FAIL_OPEN` (default: `false`) — If quota exceeded, fail with structured error (do not silently degrade).

### Domain Allowlist Policy
- `WEB_DOMAIN_ALLOWLIST` — Comma-separated allowed domains or patterns.
  - **Default**: Includes Tier 1 domains (`.edu`, `.gov`, `.org`, `.com`, `.net`)
  - **Patterns**: Supports wildcards (e.g., `*.gov`, `*.edu`, `nature.com`)
  - **Empty string**: Uses default allowlist (recommended)
  - **Override**: Set to restrict to specific domains (e.g., `*.gov,*.edu,nature.com`)
  - **⚠️ Warning**: Do not broaden allowlist casually; all additions require justification
- `WEB_DOMAIN_BLOCKLIST` — Comma-separated blocked domains (default: social media sites like `twitter.com`, `x.com`, `facebook.com`).
  - Applied after allowlist filtering
  - Default includes common social media and low-quality sites

### Web Augmentation Limits
- `WEB_MAX_URLS_PER_REQUEST` (default: `5`) — Maximum URLs to fetch per request (conservative default).
- `WEB_MAX_URLS` (default: `10`) — Maximum URLs to fetch per query (legacy, use `WEB_MAX_URLS_PER_REQUEST`).
- `WEB_MAX_PAGES` (default: `25`) — Maximum pages to scrape per URL.
- `WEB_TIMEOUT_SECONDS` (default: `30`) — HTTP timeout for Firecrawl requests.
- `WEB_CRAWL_ENABLED` (default: `false`) — Enable full-site crawling (default: scrape only, no crawling).

**Safety Notes:**
- **Firecrawl Cloud Strategy**: Vyasa uses Firecrawl Cloud for retrieval only; Vyasa owns extraction and governance.
- **HTTP-only Integration**: Firecrawl Cloud is HTTP-only integration; no SDK imports (preserves AGPL boundaries).
- **Feature Flags**: Web augmentation is disabled by default; set `WEB_AUGMENTATION_ENABLED=true` to enable. Workbench web search is disabled by default; set `WORKBENCH_WEB_SEARCH_ENABLED=true` to enable.
- **Allowlist Policy**: Results are restricted to approved domains only (see Domain Allowlist Policy section above).
  - Search endpoint filters results before returning to UI
  - Queue endpoint filters URLs before scraping
  - Do not broaden allowlist casually; all additions require justification
- **Quota Guardrails**: Free tier limited to 500 requests/month; use only for high-fidelity disputes.
  - Quota enforced via `QuotaManager`; usage tracked in ArangoDB
  - When quota exceeded, operations return `ReviewTask` with status `FAILED` and reason `quota_exceeded`
  - Set `FIRECRAWL_FAIL_OPEN=false` to fail explicitly when quota exceeded
- **Google PSE Configuration**: Google PSE configuration (included/excluded domains, weighting) is authoritative; Vyasa does not re-implement domain policy.
- **Minimal Guardrails**: Minimal "do-not-scrape" guardrail list (url shorteners, paste sites) is enforced as a safety measure only.

**Performance Notes:**
- Firecrawl Cloud handles retrieval; GPUs remain reserved for vyasa-worker inference.
- Web scraping is asynchronous and does not block workflow execution.
- **Note**: Local Firecrawl deployment was removed due to instability; Firecrawl Cloud is now required.

## Testing / Local
- Set `PROMPT_REGISTRY_ENABLED=0 OPIK_ENABLED=0` for fast unit tests (no Opik calls).
- Use localhost overrides in `src/tests/unit/conftest.py` firewalls; no extra env needed.

See `src/shared/config.py` for the full list of defaults and parsing rules.
