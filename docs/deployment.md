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

### Firecrawl (Web Augmentation)

Firecrawl is an optional sidecar service for web search and scraping. It is **disabled by default** and only used when `WEB_AUGMENTATION_ENABLED=true`.

**Setup:**
1. Add `PORT_FIRECRAWL=3002` to `deploy/.env` (optional, defaults to 3002)
2. Set `FIRECRAWL_SERVICE_URL=http://firecrawl:3002` in `deploy/.env`
3. Enable web augmentation: `WEB_AUGMENTATION_ENABLED=true`
4. Start Firecrawl service: `docker compose up firecrawl`

**Service Details:**
- **Firecrawl**: HTTP API service on port 3002 (CPU-only)
- Includes Playwright browser automation internally (no separate service needed)
- Runs on efficiency cores (CPU-only, no GPU access)
- Memory limit: 4GB

**Integration Notes:**
- **HTTP-only integration**: Vyasa core communicates with Firecrawl via HTTP requests only
- **No SDK imports**: This preserves AGPL boundaries (Firecrawl is AGPL-licensed; no SDK imports in Vyasa core)
- **CPU-only**: Firecrawl does not use GPUs; GPUs remain reserved for vyasa-worker inference
- **Optional**: Service can be started/stopped independently; Vyasa core works without it

**Verification:**
```bash
# Check Firecrawl health
curl http://localhost:3002/health

# Test scraping via FirecrawlBridge (integration test)
pytest src/tests/integration/test_firecrawl_connectivity.py -v
```

**Integration Testing:**
To run Firecrawl integration tests, ensure the Firecrawl container is running:
```bash
# Start Firecrawl service
docker compose up firecrawl

# Run integration tests
pytest src/tests/integration/test_firecrawl_connectivity.py -v -m integration
```

The integration test verifies:
- Firecrawl service is reachable
- Scraping `https://example.com` returns HTTP 200
- Markdown content includes "Example Domain"
- Error handling works correctly (failed URLs don't abort batch)

**Configuration:**
See `docs/configuration/config-reference.md` for all web augmentation environment variables.

## Service Dependencies

- **Orchestrator** depends on: cortex-brain, cortex-worker, cortex-vision, drafter, graph, vector
- **Console** depends on: cortex-brain, graph, vector
- **Firecrawl**: Standalone service (no dependencies)

## Resource Allocation

- **GPU services** (cortex-brain, cortex-worker, cortex-vision, embedder): Assigned to performance cores with GPU access
- **CPU services** (graph, vector, console, orchestrator, firecrawl): Assigned to efficiency cores (0-9)
- See `deploy/docker-compose.yml` for specific `cpuset` and `mem_limit` values

## Network

All services run on the `vyasa-net` Docker network (external network, created separately).

Service discovery uses service names (e.g., `http://firecrawl:3002`, `http://graph:8529`).

