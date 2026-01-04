# Contributing to Project Vyasa

Thank you for your interest in contributing to Project Vyasa! This document outlines guidelines and important boundaries for contributors.

## Code of Conduct

- Be respectful and constructive in all interactions
- Focus on evidence-bound, rigorous contributions
- Follow the project's architecture and design principles

## Development Setup

See the main [README.md](../README.md) for setup instructions.

## Architecture Principles

### Local-First Design
- All data must remain on the DGX system (no cloud dependencies)
- Services should work offline when possible
- External APIs are optional and feature-flagged

### Evidence-Bound Workflows
- Every claim must be traceable to a source
- Conflicts and uncertainty are surfaced, not hidden
- Human judgment is required for final decisions

### Resource Optimization
- GPUs are reserved for inference workloads (worker/brain)
- CPU services (graph, vector, console, orchestrator) run on efficiency cores
- KV cache utilization is monitored and backpressure is enforced

## Critical Boundaries

### License Boundary / Sidecar Rule

**⚠️ CRITICAL: No Firecrawl SDK imports in Vyasa core code.**

Firecrawl is AGPL-licensed. To preserve license boundaries, Vyasa core must **never** import Firecrawl's SDK or create a dependency on Firecrawl's code.

#### The Sidecar Pattern

Firecrawl runs as a **sidecar service** (separate Docker container) and communicates with Vyasa core via HTTP only. This maintains clear license boundaries:

- **Vyasa core**: Remains under its own license
- **Firecrawl sidecar**: Runs as a separate service (AGPL-licensed)
- **Communication**: HTTP requests only (standard protocol, not code dependency)

#### Browser Automation Boundary

**Playwright** is only allowed in:
- ✅ Console E2E tests (`src/console/e2e/`)
- ✅ Inside Firecrawl container (Firecrawl's internal use)

**Playwright is FORBIDDEN in:**
- ❌ Vyasa orchestrator runtime code (`src/orchestrator/`)
- ❌ Any core Python modules
- ❌ Integration tests that run in Vyasa containers

### AGPL License Boundary: Firecrawl Integration

#### Allowed Patterns

```python
# ✅ HTTP-only communication
import requests

class FirecrawlBridge:
    def scrape(self, urls: List[str]) -> List[Dict[str, Any]]:
        response = requests.post(
            f"{FIRECRAWL_SERVICE_URL}/v1/scrape",
            json={"urls": urls},
            timeout=30
        )
        return response.json()
```

#### Forbidden Patterns

```python
# ❌ DO NOT import Firecrawl SDK
from firecrawl import FirecrawlApp  # FORBIDDEN
from firecrawl.firecrawl import Firecrawl  # FORBIDDEN
import firecrawl  # FORBIDDEN
```

#### Enforcement

- **Automated Tests**: `test_firecrawl_boundary.py` scans codebase for forbidden imports
- **Code Reviews**: All PRs are checked for Firecrawl SDK imports
- **Linting**: Use grep/ripgrep to detect `from firecrawl` or `import firecrawl`
- **CI/CD**: Test suite fails if forbidden imports are detected

Run the boundary test:
```bash
pytest src/tests/unit/orchestrator/test_firecrawl_boundary.py -v
```

### Domain Allowlist Policy

**⚠️ CRITICAL: Do not broaden the allowlist casually.**

The web augmentation system enforces a **strict allowlist policy** to ensure only high-fidelity sources enter the knowledge graph:

- **Default Allowlist**: Includes `.gov`, `.edu`, `.org`, `.com`, `.net` (with quality scoring)
- **Configuration**: Set via `WEB_DOMAIN_ALLOWLIST` in `deploy/.env`
- **Enforcement Points**: Search endpoint, queue endpoint, and `AugmentationOrchestrator`

#### Why This Matters

- **Quality Control**: Prevents low-quality or unreliable sources from entering the knowledge graph
- **Quota Efficiency**: Ensures quota is used only for high-fidelity sources
- **Safety**: Reduces risk of misinformation or unreliable claims

#### Adding Domains to Allowlist

If you need to add a domain to the allowlist:

1. **Justify the addition**: Explain why the domain is high-fidelity and necessary
2. **Update configuration**: Add to `WEB_DOMAIN_ALLOWLIST` in `deploy/.env.example`
3. **Update documentation**: Document the addition in `docs/configuration/config-reference.md`
4. **Code review**: All allowlist changes require explicit approval

**Do not**:
- Add domains without justification
- Add social media sites or low-quality sources
- Bypass allowlist checks in code

#### Why This Matters

AGPL (Affero General Public License) requires that derivative works be AGPL-licensed. By keeping Firecrawl as an HTTP-only sidecar, we maintain clear boundaries:
- Vyasa core remains under its own license
- Firecrawl runs as a separate service
- Communication is via HTTP (standard protocol, not code dependency)

See [ADR-004: Web Augmentation Sidecar](../decisions/ADR-004-web-augmentation-sidecar.md) for full architectural details.

## Testing Guidelines

### Unit Tests
- **Location**: `src/tests/unit/`
- **Rule**: Zero I/O allowed (no DB, no network, no file system)
- **Mechanism**: Use `mock_*_firewall` fixtures from `conftest.py`
- **Patches**: Patch libraries at the source (e.g., `arango.ArangoClient`), never the consumer

### Integration Tests
- **Location**: `src/tests/integration/`
- **Rule**: Real Docker connections allowed
- **Mechanism**: Use `real_stack` fixture (skips if Docker is down)

### Test Execution
```bash
# Unit tests only (default)
./scripts/run_tests.sh

# Full stack (unit + integration)
./scripts/run_tests.sh --integration
```

## Code Style

### Python
- Use Pydantic for all external boundaries (API requests/responses, DB models)
- Type hints are required for public APIs
- Follow existing patterns for error handling and logging

### TypeScript
- Use TypeScript for all console code
- Prefer Next.js Server Actions for backend mutations
- Use Shadcn/UI components for consistency

## Pull Request Process

1. **Create a feature branch** from `main`
2. **Write tests** for new functionality
3. **Update documentation** if needed
4. **Ensure all tests pass** (`./scripts/run_tests.sh`)
5. **Check for Firecrawl SDK imports** (if touching web augmentation code)
6. **Submit PR** with clear description of changes

### PR Checklist

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No Firecrawl SDK imports (if web augmentation code)
- [ ] No hardcoded credentials or secrets
- [ ] Follows existing code patterns
- [ ] Type hints added (Python) or types defined (TypeScript)

## Documentation

### When to Update Docs

- New features or architecture changes
- API changes
- Configuration changes
- Breaking changes

### Documentation Locations

- **Architecture**: `docs/architecture/`
- **Decisions**: `docs/decisions/ADR-*.md`
- **Runbooks**: `docs/runbooks/`
- **Configuration**: `docs/configuration/config-reference.md`
- **User Guide**: `docs/runbooks/user_guide.md`

## Questions?

- Open an issue for questions or clarifications
- Check existing ADRs for architectural decisions
- Review `docs/architecture/` for system design details

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

