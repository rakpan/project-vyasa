# Deployment Guide

This document covers deployment setup and optional services for Project Vyasa.

## Core Services

The main Vyasa stack includes:
- **Cortex services** (Brain, Worker, Vision) - SGLang inference engines
- **Drafter** - Ollama for prose generation
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

- **Orchestrator** depends on: cortex-brain, cortex-worker, cortex-vision, drafter, graph, vector
- **Console** depends on: cortex-brain, graph, vector
- **Firecrawl Cloud**: External API service (no local dependencies)

## Resource Allocation

- **GPU services** (cortex-brain, cortex-worker, cortex-vision, embedder): Assigned to performance cores with GPU access
- **CPU services** (graph, vector, console, orchestrator): Assigned to efficiency cores (0-9)
- **Firecrawl Cloud**: Remote API service (no local resources required)
- See `deploy/docker-compose.yml` for specific `cpuset` and `mem_limit` values

## Network

All services run on the `vyasa-net` Docker network (external network, created separately).

Service discovery uses service names (e.g., `http://graph:8529`). Firecrawl Cloud is accessed via HTTPS to `https://api.firecrawl.dev`.

