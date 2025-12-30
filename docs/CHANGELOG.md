# Changelog

All notable changes to Project Vyasa will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Knowledge Accrual System
- **Global Repository** (`canonical_knowledge` collection): Persistent knowledge base accumulating expert-vetted knowledge across all projects
- **Entity Resolution**: Brain (120B) matches new verified claims against existing canonical entities using semantic similarity
- **Conflict Management**: Contradictions are flagged with `conflict_flags` for "Systemic Review" rather than being overwritten
- **Provenance Tracking**: Every canonical entry maintains a `provenance_log` tracking all contributing projects and jobs
- **Evidence-Aware RAG**: Cartographer performs pre-extraction lookup in `canonical_knowledge` to guide extraction with established knowledge
- **Synthesis Service**: `SynthesisService.finalize_project()` orchestrates knowledge synthesis during project finalization
- **Knowledge Harvester**: Automatic JSONL dataset generation (`/raid/datasets/fine_tuning_v1.jsonl`) from expert-verified research
  - Manuscript Synthesis pairs: Graph Triples → Markdown text
  - Evidence Extraction pairs: Text snippet → Structured triple
  - Dataset metadata includes `project_id`, `timestamp`, `type` for curated training

#### Hardened Evidence Binding
- **Required `source_pointer`**: `source_pointer` is now **required** (not optional) in `GraphTriple` and `Claim` models
- **PDF Text Cache Service**: `src/orchestrator/pdf_text_cache.py` caches PDF page text in ArangoDB (`pdf_text_cache` collection)
- **Real Text Verification**: Critic node performs fuzzy string matching between extracted snippet and actual page text (threshold: 0.6)
- **Bbox Validation**: Enforces `bbox` must be exactly 4 elements, all values in [0, 1000] range
- **Hard Requirements**: Every claim/triple must have `doc_hash`, `page`, `bbox`, and `snippet` (no exceptions)

#### UMA & Core Hardening
- **Memory Fraction Adjustments**: 
  - Cortex-Brain and Cortex-Worker: `--mem-fraction-static 0.70` (70% for weights, 30% for KV cache)
  - Cortex-Vision: `--mem-fraction-static 0.75` (75% for weights, 25% for KV cache)
- **Headroom Guarantee**: At least 24GB of unified memory remains unallocated for OS, ArangoDB buffers, and Qdrant operations
- **CPU Core Partitioning**: Drafter and Embedder moved to efficiency cores (`cpuset: "0-9"`)

#### Committee of Experts Architecture
- **Split Cortex into three specialized services**:
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

#### Backend Merge Logic
- **Node Merging Endpoint**: `PATCH /jobs/<job_id>/extractions/merge` for merging graph nodes
- **Alias Relationships**: Creates alias relationships in `node_aliases` collection
- **Claim Migration**: Migrates all linked claims and `source_pointers` from source to target node

#### Export Enhancements
- **Verification Gating**: Default behavior excludes claims where `is_expert_verified == false` (unless `include_drafts=true`)
- **IEEE/ACM BibTeX**: Refined BibTeX export with standard fields (author, title, booktitle/journal, year, pages, doi)
- **Schema.org JSON-LD**: Semantic data export using `https://schema.org` context with appearance properties

### Changed
- **Orchestrator API**: Added async job endpoints, kept legacy `/workflow/process` for backward compatibility
- **Node Service Routing**: 
  - Cartographer now uses Worker (not Brain) with Evidence-Aware RAG
  - Critic now uses Brain (120B) for high-level reasoning and hardened evidence binding validation
  - Vision uses Vision service for confidence scoring
- **Critic Node**: Enhanced with hardened evidence binding checks:
  - Requires `doc_hash` (hard requirement)
  - Validates `bbox` range [0-1000]
  - Performs real text verification (fuzzy match against cached PDF text)
- **Cartographer Node**: Enhanced with Evidence-Aware RAG:
  - Pre-extraction lookup in `canonical_knowledge`
  - Injects "ESTABLISHED KNOWLEDGE" into system prompt
  - Guides extraction to focus on new relationships
- **Infrastructure**: 
  - GPU reservations via environment variables (`${BRAIN_GPU_IDS}`, `${WORKER_GPU_IDS}`, `${VISION_GPU_IDS}`, `${DRAFTER_GPU_IDS}`)
  - All ports configurable via `.env` variables
  - Docker image tags and model paths configurable
  - Memory fractions adjusted for 24GB headroom guarantee

### Fixed
- **Console Dockerfile**: Fixed build context and lock file handling
- **Qdrant Initialization**: Updated container name and collection creation
- **ArangoDB Initialization**: Consolidated into single `arango-init.js` script
- **Service Naming**: Migrated from `txt2kg` to `project_vyasa` naming convention

### Removed
- **Pinecone Dependency**: Replaced with local Qdrant (see [ADR 001](./decisions/001-local-vector-db.md))
- **Hardcoded Service URLs**: All URLs now use environment variables
- **Synchronous-only Workflow**: Async jobs prevent UI timeouts
- **Optional `source_pointer`**: Now required for all claims and triples (hardened evidence binding)

## [2025-01-XX] - Initial Release

### Added
- **Core Services**: Console, Orchestrator, Cortex, Drafter, Embedder, Graph (ArangoDB), Vector (Qdrant)
- **Knowledge Graph**: Vulnerability, Mechanism, Constraint, Outcome entities and relations
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

