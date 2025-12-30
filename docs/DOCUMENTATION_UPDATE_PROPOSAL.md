# Documentation Update Proposal

This document identifies all documentation files that need updates based on recent architectural changes to Project Vyasa.

## Summary of Recent Changes

1. **Knowledge Accrual System**: Global Repository (`canonical_knowledge`) with entity resolution and conflict management
2. **Knowledge Harvester**: Automatic JSONL dataset generation for fine-tuning
3. **Hardened Evidence Binding**: Required `source_pointer`, PDF text cache, real text verification
4. **UMA & Core Hardening**: Memory fraction adjustments, CPU core pinning updates
5. **Backend Merge Logic**: Node merging/aliasing endpoint
6. **Evidence-Aware RAG**: Pre-extraction lookup in canonical knowledge
7. **Synthesis Service**: Finalization workflow with knowledge synthesis
8. **Export Enhancements**: Verification gating, BibTeX refinement, Schema.org JSON-LD

---

## Files Requiring Updates

### 1. `docs/README.md` (High Priority)

**Current State**: Missing several key features and architectural components.

**Updates Needed**:

#### A. Add "Knowledge Accrual" Section
- **Location**: After "Evidence & Provenance" section (around line 260)
- **Content**:
  - Global Repository (`canonical_knowledge` collection)
  - Entity Resolution using Brain (120B)
  - Conflict Management (flagging contradictions)
  - Provenance Tracking (provenance_log with project/job IDs)
  - Evidence-Aware RAG (pre-extraction lookup)

#### B. Add "Knowledge Harvester" Section
- **Location**: After "Knowledge Accrual" section
- **Content**:
  - Automatic JSONL dataset generation (`/raid/datasets/fine_tuning_v1.jsonl`)
  - Manuscript Synthesis pairs (Graph Triples → Markdown)
  - Evidence Extraction pairs (Snippet → Triple)
  - Dataset metadata (project_id, timestamp, type)
  - Curated Training support

#### C. Update "Evidence Binding" Section
- **Location**: Line 215-232
- **Updates**:
  - Change "MUST contain" to emphasize `source_pointer` is **required** (not optional)
  - Add mention of PDF text cache service (`pdf_text_cache.py`)
  - Add real text verification in Critic node
  - Add bbox validation [0-1000] requirement

#### D. Update "Four-Kernel Architecture" Diagram
- **Location**: Line 108-161
- **Updates**:
  - Add "Finalization" phase showing:
    - Knowledge Synthesis → `canonical_knowledge`
    - Knowledge Harvesting → JSONL datasets
  - Add "Evidence-Aware RAG" step in Cartographer node

#### E. Update Service Ports Table
- **Location**: Line 19-31
- **Updates**:
  - Verify all ports match `docker-compose.yml`
  - Add note about memory fractions (0.70 for Brain/Worker, 0.1 for Vision)

#### F. Update "Hardware Optimization" Section
- **Location**: Line 35-105
- **Updates**:
  - Update memory fractions: Brain/Worker 0.70 (not 0.75), Vision 0.1 (not 0.75)
  - Add note about 24GB headroom guarantee
  - Update Drafter and Embedder to efficiency cores (`cpuset: "0-9"`)

---

### 2. `docs/architecture/system-map.md` (High Priority)

**Current State**: Missing new collections, services, and endpoints.

**Updates Needed**:

#### A. Update ArangoDB Collections List
- **Location**: Line 184-190
- **Add**:
  - `canonical_knowledge` - Global repository of expert-vetted knowledge
  - `pdf_text_cache` - Cached PDF text layers for evidence verification
  - `node_aliases` - Alias relationships for merged nodes
  - `manuscript_blocks` - Versioned manuscript blocks
  - `patches` - Proposed edits for manuscript blocks
  - `project_bibliography` - Citation validation collection

#### B. Update Orchestrator API Endpoints
- **Location**: Line 75-86
- **Add**:
  - `POST /jobs/<job_id>/finalize` - Finalize job (triggers synthesis + harvesting)
  - `GET /jobs/<job_id>/export` - Export in Markdown/BibTeX/JSON-LD
  - `PATCH /jobs/<job_id>/extractions/merge` - Merge graph nodes
  - `GET /jobs/<job_id>/stream` - SSE stream for live graph updates

#### C. Add New Services to Container Diagram
- **Location**: Line 11-40 (Mermaid diagram)
- **Add**:
  - SynthesisService (internal to Orchestrator)
  - KnowledgeHarvester (internal to Orchestrator)
  - PDF Text Cache (internal to Orchestrator)

#### D. Update Data Flow Section
- **Location**: Line 206-229
- **Add**:
  - Finalization flow: Job → Synthesis → `canonical_knowledge`
  - Harvesting flow: Expert-verified blocks/triples → JSONL dataset
  - Evidence-Aware RAG: Cartographer queries `canonical_knowledge` before extraction

---

### 3. `docs/architecture/agent-workflow.md` (High Priority)

**Current State**: Missing new nodes and workflow enhancements.

**Updates Needed**:

#### A. Update State Definition
- **Location**: Line 12-23
- **Add**:
  - `doc_hash: Optional[str]` - SHA256 hash for PDF text cache lookup

#### B. Update Cartographer Node Description
- **Location**: Line 85-102
- **Add**:
  - Evidence-Aware RAG: Pre-extraction lookup in `canonical_knowledge`
  - Established Knowledge injection into system prompt
  - Query `canonical_knowledge` for entities mentioned in text

#### C. Update Critic Node Description
- **Location**: Line 106-119
- **Add**:
  - Hardened Evidence Binding validation:
    - Requires `doc_hash` (hard requirement)
    - Validates bbox range [0-1000]
    - Real text verification (fuzzy match snippet against cached page text)
    - Validates both claims and triples

#### D. Add Finalization Workflow Section
- **Location**: After "Complete Workflow Example" (around line 182)
- **Content**:
  - Finalization triggers:
    - Export generation
    - Knowledge synthesis (verified claims → `canonical_knowledge`)
    - Knowledge harvesting (expert-verified → JSONL datasets)
  - Entity resolution process
  - Conflict flagging

---

### 4. `docs/CHANGELOG.md` (Medium Priority)

**Current State**: Missing recent features in [Unreleased] section.

**Updates Needed**:

#### A. Add to [Unreleased] Section
- **Location**: After line 28
- **Add**:
  ```markdown
  - **Knowledge Accrual System**:
    - Global Repository (`canonical_knowledge` collection) for expert-vetted knowledge
    - Entity Resolution using Brain (120B) for matching entities
    - Conflict Management (flags contradictions for systemic review)
    - Provenance Tracking (provenance_log tracks all contributing projects/jobs)
  - **Knowledge Harvester**:
    - Automatic JSONL dataset generation (`/raid/datasets/fine_tuning_v1.jsonl`)
    - Manuscript Synthesis pairs (Graph Triples → Markdown)
    - Evidence Extraction pairs (Snippet → Triple)
    - Dataset metadata for curated training
  - **Hardened Evidence Binding**:
    - `source_pointer` is now **required** (not optional) in `GraphTriple`
    - PDF text cache service for real text verification
    - Critic node validates snippets against actual page text
    - Bbox validation [0-1000] enforced
  - **Backend Merge Logic**:
    - `PATCH /jobs/<job_id>/extractions/merge` endpoint for node merging
    - Alias relationships in `node_aliases` collection
    - Migrates claims and source_pointers from source to target
  - **Evidence-Aware RAG**:
    - Pre-extraction lookup in `canonical_knowledge`
    - Established Knowledge injection into Cartographer prompt
    - Guides extraction with global context
  - **Synthesis Service**:
    - Finalization workflow synthesizes verified claims into canonical knowledge
    - Background processing for synthesis and harvesting
  - **Export Enhancements**:
    - Verification gating (default: only `is_expert_verified=True`)
    - IEEE/ACM-compliant BibTeX export
    - Schema.org JSON-LD export with appearance properties
  ```

---

### 5. `docs/runbooks/getting-started.md` (Medium Priority)

**Current State**: Missing new features and updated memory settings.

**Updates Needed**:

#### A. Update "Step 8: Process Documents"
- **Location**: Line 144-166
- **Add**:
  - Mention of Evidence-Aware RAG (established knowledge lookup)
  - Hardened evidence binding (required source_pointer)
  - Real text verification in Critic

#### B. Add "Step 10: Finalize Project"
- **Location**: After "Step 9: Test Search"
- **Content**:
  - Finalization triggers knowledge synthesis and harvesting
  - How to access exported datasets
  - How to view canonical knowledge

#### C. Update Memory/GPU Requirements
- **Location**: Line 7-12
- **Updates**:
  - Update memory fractions mention
  - Add note about 24GB headroom guarantee

---

### 6. `docs/guides/development.md` (Low Priority)

**Current State**: Mostly up-to-date, but missing some new patterns.

**Updates Needed**:

#### A. Add "Knowledge Accrual" Section
- **Location**: After "Database Interactions" (around line 293)
- **Content**:
  - How to query `canonical_knowledge`
  - Entity resolution patterns
  - Conflict management best practices

#### B. Add "Knowledge Harvesting" Section
- **Location**: After "Knowledge Accrual"
- **Content**:
  - How harvesting works
  - Dataset format specification
  - Curated training patterns

#### C. Update "Error Handling" Section
- **Location**: Line 108-130
- **Add**:
  - Example of PDF text cache error handling
  - Evidence binding validation error patterns

---

### 7. `docs/architecture/api-spec.md` (High Priority)

**Current State**: Severely outdated, missing most endpoints.

**Updates Needed**:

#### A. Complete API Endpoint Documentation
- **Location**: Entire file needs rewrite
- **Add all endpoints**:
  - `GET /health` (quick and deep check)
  - `POST /api/projects` - Create project
  - `GET /api/projects` - List projects
  - `GET /api/projects/<project_id>` - Get project
  - `POST /ingest/pdf` - PDF to Markdown (requires project_id)
  - `POST /workflow/submit` - Submit async job
  - `GET /workflow/status/<job_id>` - Get job status
  - `GET /workflow/result/<job_id>` - Get job result
  - `GET /jobs/<job_id>/status` - Alternative status endpoint
  - `POST /jobs/<job_id>/finalize` - Finalize job
  - `GET /jobs/<job_id>/export` - Export in various formats
  - `PATCH /jobs/<job_id>/extractions/merge` - Merge nodes
  - `GET /jobs/<job_id>/stream` - SSE stream for live updates
  - `GET /system/pulse` - System metrics

#### B. Add Request/Response Examples
- Include full JSON examples for each endpoint
- Include error response formats
- Include query parameters

---

### 8. `README.md` (Root) (Medium Priority)

**Current State**: Missing new features.

**Updates Needed**:

#### A. Update "Key Features" Section
- **Location**: Line 117-123
- **Add**:
  - Knowledge Accrual (Global Repository)
  - Knowledge Harvester (Automatic dataset generation)
  - Hardened Evidence Binding (Required source_pointer, real text verification)

#### B. Update "Architecture Overview"
- **Location**: Line 33-45
- **Add**:
  - SynthesisService (internal to Orchestrator)
  - KnowledgeHarvester (internal to Orchestrator)

---

## Priority Ranking

1. **High Priority** (Update Immediately):
   - `docs/README.md` - Main documentation entry point
   - `docs/architecture/system-map.md` - Architecture reference
   - `docs/architecture/agent-workflow.md` - Workflow documentation
   - `docs/architecture/api-spec.md` - API reference (severely outdated)

2. **Medium Priority** (Update Soon):
   - `docs/CHANGELOG.md` - Track new features
   - `docs/runbooks/getting-started.md` - User onboarding
   - `README.md` (root) - Project overview

3. **Low Priority** (Update When Time Permits):
   - `docs/guides/development.md` - Developer reference

---

## Specific Content Additions Needed

### Knowledge Accrual Documentation

**New Section Template**:
```markdown
## Knowledge Accrual: Global Repository

Project Vyasa maintains a **Global Repository** (`canonical_knowledge`) that accumulates expert-vetted knowledge across all projects. This enables:

1. **Entity Resolution**: Brain (120B) matches new claims against existing entities
2. **Conflict Management**: Contradictions are flagged for review, not overwritten
3. **Provenance Tracking**: Every entry tracks all contributing projects/jobs
4. **Evidence-Aware RAG**: Cartographer queries established knowledge before extraction

### Finalization Workflow

When a project is finalized:
1. All `is_expert_verified: true` claims are synthesized
2. Entity resolution determines if claims match existing canonical entries
3. Matches are merged (attributes + source_pointers aggregated)
4. Conflicts are flagged for systemic review
5. New entities are added to canonical knowledge

### Evidence-Aware RAG

Before extraction, the Cartographer:
1. Extracts potential entity names from raw text
2. Queries `canonical_knowledge` for matching entities
3. Injects "Established Knowledge" section into system prompt
4. Guides extraction to focus on new relationships or updated information
```

### Knowledge Harvester Documentation

**New Section Template**:
```markdown
## Knowledge Harvester: Automatic Dataset Generation

Project Vyasa automatically generates JSONL instruction datasets from expert-verified research for fine-tuning models on the DGX Spark.

### Dataset Types

1. **Manuscript Synthesis Pairs**:
   - Input: Graph Triples (JSON)
   - Output: Finalized Markdown text
   - Metadata: project_id, block_id, claim_ids, citation_keys

2. **Evidence Extraction Pairs**:
   - Input: Text snippet from source_pointer
   - Output: Structured triple (JSON)
   - Metadata: project_id, doc_hash, page, bbox

### Storage

- **Location**: `/raid/datasets/fine_tuning_v1.jsonl` (configurable via `VYASA_DATASET_DIR`)
- **Format**: JSONL (one JSON object per line)
- **Metadata**: Includes project_id and timestamp for curated training

### Triggering

Harvesting is automatically triggered when:
- A job is finalized (`POST /jobs/<job_id>/finalize`)
- Expert-verified blocks/triples exist
- Project has `project_id` present
```

### Hardened Evidence Binding Documentation

**Update Existing Section**:
```markdown
### 2. Evidence Binding (Source Pointers) - **REQUIRED**

**Requirement**: Every claim/triple **MUST** contain a `source_pointer` (no longer optional) with:
- `doc_hash`: SHA256 hash of source document (required)
- `page`: 1-based page number (required)
- `bbox`: Normalized bounding box `[x1, y1, x2, y2]` (0-1000 scale, required)
- `snippet`: Exact text excerpt from the source (required)

**Real Text Verification**:
- PDF text layers are cached by `doc_hash` and `page` number
- Critic node performs fuzzy string matching between snippet and actual page text
- Claims/triples failing verification are rejected

**PDF Text Cache**:
- Service: `src/orchestrator/pdf_text_cache.py`
- Storage: File system (`/tmp/vyasa_pdf_cache`) + ArangoDB (`pdf_text_cache` collection)
- Fallback: Extracts from PDF if cache miss
```

---

## Action Items

1. ✅ **Create this proposal document** (DONE)
2. ⏳ **Update `docs/README.md`** - Add Knowledge Accrual and Harvester sections
3. ⏳ **Update `docs/architecture/system-map.md`** - Add new collections and endpoints
4. ⏳ **Update `docs/architecture/agent-workflow.md`** - Add Evidence-Aware RAG and finalization
5. ⏳ **Update `docs/CHANGELOG.md`** - Add all new features to [Unreleased]
6. ⏳ **Update `docs/architecture/api-spec.md`** - Complete API documentation
7. ⏳ **Update `docs/runbooks/getting-started.md`** - Add finalization step
8. ⏳ **Update `README.md` (root)** - Add new features to overview

---

## Notes

- All documentation should emphasize the **Project-First** workflow
- Highlight the **hardened evidence binding** requirements
- Document the **automatic** nature of synthesis and harvesting (no manual triggers)
- Include code references where appropriate
- Use Mermaid diagrams for visual flows
- Maintain consistency with existing documentation style

