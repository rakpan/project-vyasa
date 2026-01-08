# Deployment Guide

This document covers deployment setup and optional services for Project Vyasa.

## Core Services

The main Vyasa stack includes:
- **Cortex services** (Brain, Worker, Vision) - SGLang inference engines
- **Graph** - ArangoDB for knowledge graph storage
- **Vector** - Qdrant for semantic search
- **Console** - Next.js frontend
- **Orchestrator** - LangGraph workflow API
- **Embedder** - Sentence transformer for embeddings

See `deploy/docker-compose.yml` for full service definitions.

## Optional Services

### Firecrawl Cloud (Optional)

Firecrawl Cloud is an optional service for web search and scraping. It is **disabled by default** and only used when `WEB_AUGMENTATION_ENABLED=true`.

**Important**: Firecrawl Cloud requires an API key. Sign up at https://firecrawl.dev to get your API key.

**Setup:**

1. **Get Firecrawl Cloud API Key:**
   - Sign up at https://firecrawl.dev
   - Obtain your API key from the dashboard
   - Free tier includes 500 requests/month

2. **Configure environment variables** in `deploy/.env`:
   ```bash
   FIRECRAWL_MODE=cloud
   FIRECRAWL_API_KEY=your-api-key-here
   FIRECRAWL_BASE_URL=https://api.firecrawl.dev
   FIRECRAWL_MONTHLY_QUOTA=500
   FIRECRAWL_FAIL_OPEN=false
   WEB_AUGMENTATION_ENABLED=true
   WEB_DOMAIN_ALLOWLIST=.edu,.gov,.org,.com,.net
   WEB_DOMAIN_BLOCKLIST=twitter.com,x.com,facebook.com,instagram.com,linkedin.com,reddit.com
   WEB_MAX_URLS_PER_REQUEST=5
   WEB_CRAWL_ENABLED=false
   ```

3. **No Docker container required** - Firecrawl Cloud is a remote API service.

**Service Details:**
- **Firecrawl Cloud**: Remote HTTP API service (no local deployment)
- Handles web scraping and crawling via cloud infrastructure
- No local resources required (no CPU/GPU/memory usage on DGX)

**Integration Notes:**
- **HTTP-only integration**: Vyasa core communicates with Firecrawl Cloud via HTTP requests only
- **No SDK imports**: This preserves AGPL boundaries (Firecrawl is AGPL-licensed; no SDK imports in Vyasa core)
- **Quota limits**: Free tier limited to 500 requests/month; use only for high-fidelity disputes
- **Optional**: Feature can be disabled; Vyasa core works without it
- **Note**: Local Firecrawl deployment was removed due to instability; Firecrawl Cloud is now required

**Verification:**
```bash
# Test API key (don't expose the key in logs)
curl -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"url":"https://example.com"}' \
     https://api.firecrawl.dev/v0/scrape

# Test scraping via FirecrawlBridge (integration test)
RUN_FIRECRAWL_TESTS=true pytest src/tests/integration/test_firecrawl_connectivity.py -v
```

**Integration Testing:**
To run Firecrawl Cloud integration tests:
```bash
# Set API key and test flag
export FIRECRAWL_API_KEY=your-api-key-here
export RUN_FIRECRAWL_TESTS=true

# Run integration tests
pytest src/tests/integration/test_firecrawl_connectivity.py -v -m integration
```

The integration test verifies:
- Firecrawl Cloud API is reachable
- Scraping `https://example.com` returns HTTP 200
- Markdown content includes "Example Domain"
- Error handling works correctly (failed URLs don't abort batch)
- Quota handling (if `FIRECRAWL_FAIL_OPEN=false`)

**Configuration:**
See `docs/configuration/config-reference.md` for all web augmentation environment variables.

## Service Dependencies

- **Orchestrator** depends on: cortex-brain, cortex-worker, graph, vector
  - **Note**: cortex-vision is optional (profiles: ["vision"]). Orchestrator handles vision unavailability gracefully.
- **Console** depends on: cortex-brain, graph, vector
- **Firecrawl Cloud**: External API service (no local dependencies)

## Optional Services

### Vision Service (Optional Accelerator)

Vision is **disabled by default** and runs under Docker Compose profiles. This allows you to reclaim GPU memory when vision is not needed.

**Vision OFF (Default):**
```bash
# Start all services except vision (default behavior)
docker compose up -d
```

**Turn Vision ON:**
```bash
# Start vision service (requires VISION_ENABLED=true in .env)
docker compose --profile vision up -d cortex-vision
```

**Turn Vision OFF:**
```bash
# Stop vision service and reclaim GPU memory
docker compose stop cortex-vision
# Or explicitly with profile:
docker compose --profile vision stop cortex-vision
```

**Important Notes:**
- **UI toggle does NOT start/stop containers**: The UI toggle (`VISION_ENABLED`) only reflects configuration and health status. It does not control Docker containers.
- **GPU memory reclamation**: Stopping `cortex-vision` immediately reclaims GPU memory (single GPU by default).
- **Graceful degradation**: The orchestrator handles vision unavailability gracefully. Workflows continue without vision processing when the service is unavailable.
- **Configuration**: Set `VISION_ENABLED=true` in `deploy/.env` to enable vision processing in the orchestrator (in addition to starting the container).

**Configuration Variables** (in `deploy/.env`):
```bash
# Vision as Optional Accelerator (disabled by default)
VISION_ENABLED=false          # Set to true to enable vision processing
VISION_TRIAGE_PAGES=2         # Pages to preview for scanned PDF detection
VISION_MIN_TEXT_CHARS=800     # Minimum text chars to consider PDF text-based
VISION_HEALTH_TIMEOUT=1       # Health check timeout in seconds
```

**When to Enable Vision:**
- Processing scanned/image-heavy PDFs
- Need OCR for figures, tables, or charts
- Have sufficient GPU headroom (vision uses single GPU by default, tp-size=1)

**When to Disable Vision:**
- Processing text-based journal PDFs (most common case)
- Need to reclaim GPU memory for other workloads
- Vision service is unstable or unavailable

## Resource Allocation

### GPU Assignment

GPU assignment is controlled via environment variables (single source of truth):

- **TEXT_GPU_IDS** (default: `"0"`): GPU IDs for `cortex-brain` and `cortex-worker`
  - Both services share the same GPU assignment (service-level redundancy)
  - Default: Single GPU (0)

- **VISION_GPU_IDS** (default: `"0"`): GPU IDs for `cortex-vision` (optional override)
  - Default: Single GPU (0) with tp-size=1
  - Disabled by default (Docker Compose profile)
  - Multi-GPU override: Set `VISION_GPU_IDS="0,1"` and update `--tp-size 2` in docker-compose.yml

- **EMBEDDER_GPU_IDS** (default: empty): GPU IDs for `embedder`
  - **Default: CPU mode** (no GPU) to avoid VRAM contention
  - To enable GPU: Set `EMBEDDER_GPU_IDS="0"` in `.env`

**Default Configuration** (single GPU):
- `cortex-brain`: GPU 0
- `cortex-worker`: GPU 0
- `cortex-vision`: GPU 0 (optional, disabled by default)
- `embedder`: CPU (no GPU)

**Multi-GPU Override**: See `deploy/runbooks/dgx-runtime.md` for multi-GPU configuration.

### CPU Allocation

- **GPU services** (cortex-brain, cortex-worker, cortex-vision): Performance cores (10-19)
- **CPU services** (graph, vector, console, orchestrator, embedder): Efficiency cores (0-9)
- **Firecrawl Cloud**: Remote API service (no local resources required)
- See `deploy/docker-compose.yml` for specific `cpuset` and `mem_limit` values

## Network

All services run on the `vyasa-net` Docker network (external network, created separately).

Service discovery uses service names (e.g., `http://graph:8529`). Firecrawl Cloud is accessed via HTTPS to `https://api.firecrawl.dev`.
