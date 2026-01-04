# ADR-004: Web Augmentation Sidecar Architecture

- **Status**: Accepted
- **Date**: 2025-01-04
- **Deciders**: Project Vyasa Team

## Context

Project Vyasa requires the ability to augment local knowledge with web sources when:
- Disagreements are detected between local claims
- Evidence gaps exist that cannot be filled from the seed corpus
- Low-confidence claims need external validation

However, web scraping and search require external dependencies that must be isolated from Vyasa's core research engine to:
1. Preserve AGPL license boundaries (Firecrawl is AGPL-licensed)
2. Maintain local-first architecture (optional feature, not required)
3. Keep GPU resources reserved for inference workloads

## Decision

We will implement a **sidecar architecture** where:
- **Vyasa Core** (orchestrator) makes all decisions about when and what to augment
- **Firecrawl** runs as a separate, optional service that only retrieves content
- Communication is **HTTP-only** (no SDK imports in Vyasa core)
- Feature is **disabled by default** and requires explicit opt-in

## System Boundaries

The web augmentation loop is divided into five distinct boundaries:

### 1. Discovery (Vyasa Core)
- **Responsibility**: Convert `DisputeContext` into search queries
- **Implementation**: `WebDiscoveryService` in `src/orchestrator/web/discovery.py`
- **Dependencies**: Google Custom Search JSON API (optional, HTTP-only)
- **Output**: List of candidate URLs (bounded by `WEB_MAX_URLS`)

### 2. Retrieval (Firecrawl Sidecar)
- **Responsibility**: Scrape URLs and return markdown content
- **Implementation**: `FirecrawlBridge` in `src/orchestrator/web/firecrawl.py`
- **Communication**: HTTP POST requests to `FIRECRAWL_SERVICE_URL`
- **No SDK imports**: Uses `requests` library only (no Firecrawl SDK)
- **Output**: Markdown content per URL (bounded by `WEB_MAX_PAGES`)

### 3. Normalization (Vyasa Core)
- **Responsibility**: Convert Firecrawl/PDF content into unified `NormalizedEvidenceUnit`
- **Implementation**: `EvidenceNormalizer` in `src/orchestrator/web/normalizer.py`
- **Purpose**: Single interface so Worker extraction ignores source type
- **Output**: `NormalizedEvidenceUnit` objects with provenance metadata

### 4. Intelligence (Vyasa Core)
- **Responsibility**: Extract claims from normalized evidence using existing Worker pipeline
- **Implementation**: Reuses `_extract_claims_from_content()` pattern from `knowledge.py`
- **No new schemas**: Uses existing `Claim` schema
- **Output**: Candidate claims for review

### 5. Governance (Vyasa Core)
- **Responsibility**: Create `ReviewTask` and persist to governance queue
- **Implementation**: `AugmentationOrchestrator` in `src/orchestrator/web/augmentation_orchestrator.py`
- **Storage**: `review_tasks` collection in ArangoDB (not knowledge graph)
- **Output**: `ReviewTask` with status `PENDING` for human approval

## Trigger-Driven Augmentation

Web augmentation is **triggered** by specific events, not run continuously:

1. **Disagreement Detection**: When `DisputeContext` is created (conflicting claims detected)
2. **Evidence Gap**: When required evidence type cannot be found in seed corpus
3. **Low Confidence**: When claims fall below confidence threshold (future enhancement)

The trigger creates a `DisputeContext` which flows through:
```
DisputeContext → WebDiscoveryService → URLs
URLs → FirecrawlBridge → Markdown
Markdown → EvidenceNormalizer → NormalizedEvidenceUnit
NormalizedEvidenceUnit → Worker.extract → Claims
Claims → AugmentationOrchestrator → ReviewTask(PENDING)
```

## AGPL Boundary Rule

**Critical**: No Firecrawl SDK imports in Vyasa core code.

### Allowed
- HTTP requests via `requests` library
- `FirecrawlBridge` class that wraps HTTP calls
- Configuration via environment variables

### Forbidden
- `from firecrawl import *` or any Firecrawl SDK imports
- Direct Firecrawl client instantiation
- Any code that would create a dependency on Firecrawl's AGPL license

### Enforcement
- Code reviews must check for Firecrawl SDK imports
- Linter rules (if possible) to detect Firecrawl imports
- Integration tests verify HTTP-only communication

## Feature Flag and Offline Behavior

### Feature Flag
- `WEB_AUGMENTATION_ENABLED` (default: `false`)
- When disabled:
  - `AugmentationOrchestrator.run()` returns `ReviewTask` with status `FAILED`
  - No HTTP calls to Firecrawl
  - No Google Search API calls
  - System continues normally without web augmentation

### Offline Behavior
- If `WEB_AUGMENTATION_ENABLED=true` but Firecrawl is unavailable:
  - `FirecrawlBridge.scrape()` returns empty list with logged warning
  - `AugmentationOrchestrator` returns `ReviewTask` with status `FAILED`
  - No crash or exception propagation
  - System continues normally

### Resource Constraints
- **Firecrawl**: CPU-only service (no GPU access)
- **GPUs**: Reserved exclusively for `vyasa-worker` and `vyasa-brain` inference
- **Network**: Firecrawl may require internet access (for web scraping)

## Implementation Details

### Service Configuration
```yaml
# docker-compose.yml
firecrawl:
  image: mintlabs/firecrawl:latest
  container_name: firecrawl
  ports:
    - "3002:3002"
  # No GPU access
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
```

### HTTP Client Pattern
```python
# src/orchestrator/web/firecrawl.py
class FirecrawlBridge:
    def scrape(self, urls: List[str]) -> List[Dict[str, Any]]:
        response = requests.post(
            f"{FIRECRAWL_SERVICE_URL}/v1/scrape",
            json={"urls": urls, "formats": ["markdown"]},
            timeout=WEB_TIMEOUT_SECONDS
        )
        return response.json()
```

### Orchestrator Pattern
```python
# src/orchestrator/web/augmentation_orchestrator.py
class AugmentationOrchestrator:
    def run(self, dispute: DisputeContext) -> ReviewTask:
        if not WEB_AUGMENTATION_ENABLED:
            return ReviewTask.create(..., status=ReviewStatus.FAILED)
        
        urls = self.discovery_service.discover(dispute)
        markdown = self.firecrawl_bridge.scrape(urls)
        units = [EvidenceNormalizer.normalize_web(item) for item in markdown]
        claims = _extract_claims_from_content(unit.content, ...)
        return ReviewTask.create(..., candidate_claims=claims, status=ReviewStatus.PENDING)
```

## Consequences

### Positive
- ✅ **License Isolation**: AGPL boundary preserved via HTTP-only communication
- ✅ **Optional Feature**: System works without web augmentation
- ✅ **Resource Efficiency**: Firecrawl CPU-only, GPUs reserved for inference
- ✅ **Deterministic**: All components are testable via mocks
- ✅ **Human-in-Loop**: ReviewTasks require approval before knowledge graph writes

### Negative
- ⚠️ **Network Dependency**: Requires internet for web scraping (when enabled)
- ⚠️ **Additional Service**: Firecrawl container must be running (when enabled)
- ⚠️ **Latency**: HTTP round-trips add delay to augmentation loop

### Neutral
- **Review Queue**: Creates new UI surface for human approval
- **Governance Queue**: New `review_tasks` collection in ArangoDB

## Alternatives Considered

### 1. Direct Firecrawl SDK Integration (Rejected)
- **Why**: Would create AGPL license dependency in Vyasa core
- **Risk**: AGPL requires derivative works to be AGPL-licensed

### 2. No Web Augmentation (Rejected)
- **Why**: Limits system to seed corpus only
- **Gap**: Cannot resolve disagreements or fill evidence gaps

### 3. Cloud Search API Only (Rejected)
- **Why**: Requires external API keys and network dependency
- **Limitation**: Cannot scrape full page content, only search results

### 4. Built-in Scraper (Rejected)
- **Why**: Duplicates Firecrawl functionality, maintenance burden
- **Complexity**: Would require browser automation, proxy handling, etc.

## References

- [Firecrawl Documentation](https://docs.firecrawl.dev/)
- [AGPL License](https://www.gnu.org/licenses/agpl-3.0.html)
- [Web Augmentation Implementation](../architecture/00-overview.md#web-augmentation-loop)
- [Configuration Reference](../configuration/config-reference.md)

## Related Decisions

- [ADR-001: Local Vector DB](./ADR-001-local-vector-db.md) - Local-first architecture
- [ADR-003: Governance Contracts](./ADR-003-governance-contracts.md) - ReviewTask governance queue

## Implementation History

- **2025-01-04**: Initial implementation
  - Created `WebDiscoveryService` for Google Custom Search integration
  - Created `FirecrawlBridge` for HTTP-only Firecrawl communication
  - Created `EvidenceNormalizer` for unified evidence interface
  - Created `AugmentationOrchestrator` for end-to-end loop
  - Created Review Queue UI for human approval
  - Added feature flag `WEB_AUGMENTATION_ENABLED`

