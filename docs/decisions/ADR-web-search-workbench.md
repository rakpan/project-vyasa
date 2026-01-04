# ADR: Web Search Workbench Integration

## Status
Accepted

## Context
Project Vyasa needs a minimal web search capability in the workbench that allows users to:
1. Search the web using Google Programmable Search Engine (PSE) as the source of truth
2. Queue selected URLs into the governance review flow (Firecrawl scrape → extract → ReviewTask)
3. Avoid persisting anything into the knowledge graph without human approval

The system already has:
- Google Custom Search JSON API configured (cx=61d688577df944862)
- Firecrawl sidecar for web scraping (HTTP-only boundary)
- ReviewTask schema and governance queue
- Web augmentation orchestrator for processing web sources

## Decision
Implement a minimal Vyasa-native Web Search panel inside the Project Workbench that:
1. Calls Google Custom Search JSON API server-side (backend-controlled)
2. Displays results in the workbench UI
3. Allows users to queue selected URLs into the governance review flow
4. Does NOT persist anything into the knowledge graph without human approval

### Key Design Principles

1. **PSE as Source of Truth**: Treat Google PSE configuration (included/excluded domains, weighting, etc.) as authoritative. Do NOT re-implement allowlists, blocklists, scoring, tiers, or ranking logic in Vyasa.

2. **Minimal Guardrails**: Only implement a small "do-not-scrape" guardrail list for obvious unsafe categories (url shorteners, paste sites). This is a safety measure only; PSE configuration is authoritative.

3. **Backend-Controlled**: All API calls (Google Search, Firecrawl) are made server-side to:
   - Protect API keys
   - Enforce rate limits
   - Maintain security boundaries

4. **Governance Queue Only**: URLs are queued into ReviewTasks (governance queue), not directly into the knowledge graph. Human approval is required before knowledge graph persistence.

5. **Reuse Existing Infrastructure**: Leverage existing Firecrawl bridge, augmentation orchestrator, and ReviewTask schema. Avoid creating new orchestration layers.

## Implementation Details

### Backend API (`src/orchestrator/api/web_search.py`)

Two endpoints:
1. `POST /api/web-search/search`: Calls Google Custom Search JSON API
2. `POST /api/web-search/queue`: Queues URLs into governance review flow

### Frontend Components

1. `WebSearchPanel`: Main search interface with query input and results
2. `SearchResultsList`: Displays search results with selection checkboxes
3. `useWebSearch`: React hook for search state management

### Integration

WebSearchPanel is integrated into the workbench as a tab in the "Knowledge Claims" pane (right pane), alongside the existing claims view.

### Configuration

Required environment variables:
- `WORKBENCH_WEB_SEARCH_ENABLED=false` (feature flag)
- `GOOGLE_SEARCH_API_KEY=` (Google API key)
- `GOOGLE_SEARCH_ENGINE_ID=` (PSE cx id, e.g., `61d688577df944862`)
- `WEB_MAX_SEARCH_RESULTS=10` (max results per search)
- `WEB_AUGMENTATION_ENABLED=false` (required for queue functionality)

### Safety Guardrails

Minimal "do-not-scrape" list (local constant in queue endpoint):
- URL shorteners: `bit.ly`, `tinyurl.com`, `t.co`, `goo.gl`, `short.link`
- Paste sites: `pastebin.com`, `paste.ee`, `hastebin.com`, `dpaste.com`

This is a safety measure only. PSE configuration (included/excluded domains, weighting) is authoritative.

## Consequences

### Positive
- Minimal implementation reuses existing infrastructure
- Backend-controlled API calls protect keys and enforce security
- Governance queue ensures human approval before knowledge graph persistence
- PSE configuration remains authoritative (no duplicate logic)

### Negative
- Requires Google Custom Search API key and PSE configuration
- Depends on Firecrawl sidecar for scraping (optional service)
- Adds UI complexity to workbench (mitigated by tab-based integration)

### Risks
- Google API rate limits (mitigated by server-side control)
- Firecrawl unavailability (handled gracefully with FAILED ReviewTask)
- PSE configuration drift (mitigated by treating PSE as authoritative)

## Alternatives Considered

1. **Client-side Google Search**: Rejected - exposes API keys, harder to enforce rate limits
2. **Direct Knowledge Graph Persistence**: Rejected - violates governance principle (requires human approval)
3. **Re-implement Domain Policy**: Rejected - PSE configuration is authoritative, avoid duplication

## References
- Google Custom Search JSON API: https://developers.google.com/custom-search/v1/overview
- ADR-004: Web Augmentation Sidecar (Firecrawl integration)
- ReviewTask schema: `src/orchestrator/schemas/review.py`
- Web Augmentation Orchestrator: `src/orchestrator/web/augmentation_orchestrator.py`

