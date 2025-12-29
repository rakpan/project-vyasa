# Changelog

All notable changes to Project Vyasa will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Committee of Experts Architecture**: Split Cortex into three specialized services:
  - **Brain** (Port 30000): High-level reasoning and routing decisions
  - **Worker** (Port 30001): Strict JSON extraction and validation (cheap model)
  - **Vision** (Port 30002): Confidence scoring and filtering
- **Asynchronous Job System**: 
  - `POST /workflow/submit` - Submit async workflow jobs
  - `GET /workflow/status/<job_id>` - Poll job status
  - Concurrency control (max 2 concurrent jobs via semaphore)
- **Dynamic Role System**: 
  - Roles stored in ArangoDB (`RoleProfile` model)
  - Runtime role updates without code redeployment
  - Role versioning and fallback to defaults
- **Vision Node**: Confidence filtering (removes triples with `confidence_score < 0.5`)
- **Normalized Output Guarantee**: `normalize_extracted_json()` ensures consistent `{"triples": [...]}` structure
- **Test Suite**: 
  - Unit tests for Cartographer, Critic, Vision nodes
  - Integration tests for ArangoDB and Qdrant
  - Safety checks (schema enforcement, citation validation)

### Changed
- **Orchestrator API**: Added async job endpoints, kept legacy `/workflow/process` for backward compatibility
- **Node Service Routing**: 
  - Cartographer now uses Worker (not Brain)
  - Critic now uses Worker (cheap model)
  - Vision uses Vision service for confidence scoring
- **Infrastructure**: 
  - GPU reservations via environment variables (`${BRAIN_GPU_IDS}`, `${WORKER_GPU_IDS}`, `${VISION_GPU_IDS}`, `${DRAFTER_GPU_IDS}`)
  - All ports configurable via `.env` variables
  - Docker image tags and model paths configurable

### Fixed
- **Console Dockerfile**: Fixed build context and lock file handling
- **Qdrant Initialization**: Updated container name and collection creation
- **ArangoDB Initialization**: Consolidated into single `arango-init.js` script
- **Service Naming**: Migrated from `txt2kg` to `project_vyasa` naming convention

### Removed
- **Pinecone Dependency**: Replaced with local Qdrant (see [ADR 001](./decisions/001-local-vector-db.md))
- **Hardcoded Service URLs**: All URLs now use environment variables
- **Synchronous-only Workflow**: Async jobs prevent UI timeouts

## [2025-01-XX] - Initial Release

### Added
- **Core Services**: Console, Orchestrator, Cortex, Drafter, Embedder, Graph (ArangoDB), Vector (Qdrant)
- **PACT Ontology**: Vulnerability, Mechanism, Constraint, Outcome entities and relations
- **LangGraph Workflow**: Cartographer → Critic → Saver loop
- **NextAuth Authentication**: Password-based UI authentication
- **PDF Processing**: pymupdf4llm integration for document ingestion

---

## Migration Notes

### From Single Cortex to Committee Architecture

If migrating from a single Cortex service:

1. **Update Environment Variables**:
   ```bash
   # Old
   CORTEX_URL=http://cortex:30000
   
   # New
   CORTEX_BRAIN_URL=http://cortex-brain:30000
   CORTEX_WORKER_URL=http://cortex-worker:30001
   CORTEX_VISION_URL=http://cortex-vision:30002
   ```

2. **Update GPU Reservations**:
   ```bash
   BRAIN_GPU_IDS=0,1
   WORKER_GPU_IDS=2
   VISION_GPU_IDS=3,4
   DRAFTER_GPU_IDS=5
   ```

3. **Update Service Calls**:
   - Cartographer/Critic nodes automatically use Worker URL
   - Vision node uses Vision URL
   - Supervisor (if used) uses Brain URL

### From Synchronous to Async Jobs

1. **Update Frontend**: Use `submitWorkflowJob()` and `pollWorkflowStatus()` from `orchestrator-client.ts`
2. **Legacy Support**: `/workflow/process` endpoint still works for backward compatibility
3. **Job Management**: Jobs stored in-memory (consider persistence for production)

---

## References

- [System Architecture](./architecture/system-map.md)
- [Agent Workflow](./architecture/agent-workflow.md)
- [ADR 001: Local Vector DB](./decisions/001-local-vector-db.md)

