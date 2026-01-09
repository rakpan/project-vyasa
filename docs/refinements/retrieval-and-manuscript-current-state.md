# Retrieval and Manuscript: Current State

**Purpose**: Document the current implementation of chunking, retrieval, manuscript storage, LangGraph context assembly, and UI data flows. This serves as the foundation for integrating Reranker, RetrievalBundle, Analytical Notes, and Blueprint-driven synthesis.

**Date**: 2025-01-XX  
**Status**: Research-only (no code changes)

Authoritative references (for “should”):
- `docs/architecture/09-retrieval-evidence-selection.md`
- `docs/architecture/10-citation-compilation.md`
- `docs/architecture/11-manuscript-persistence-lifecycle.md`

---

## 1. Chunking

### 1.1 Implementation Location

**Primary File**: `src/orchestrator/storage/qdrant.py`

**Key Function**: `QdrantStorage.ingest_document_chunks()`
- **Line**: 89-252
- **Signature**: `ingest_document_chunks(pdf_path, file_hash, ingestion_id, project_id, rigor_level, embeddings)`

### 1.2 Chunking Process

1. **PDF Processing**:
   - Opens PDF with PyMuPDF (`pymupdf`)
   - Iterates pages (1-based indexing)
   - Extracts text per page: `page.get_text()`

2. **Text Splitting**:
   - **Function**: `_split_text_into_chunks()` (line 254-281)
   - **Chunk size**: 512 characters
   - **Overlap**: 50 characters
   - **Algorithm**: Fixed-size sliding window
   - Splits per-page (not cross-page)

3. **Chunk ID Generation**:
   - **Function**: `_generate_chunk_id()` (line 283-295)
   - **Format**: SHA256 hash of `"{file_hash}|{page_number}|{chunk_index}"`
   - **Deterministic**: Same file/page/chunk_index → same chunk_id
   - **Example**: `"abc123|1|0"` → SHA256 → hex digest

### 1.3 Chunk Metadata (Payload)

Stored in Qdrant payload (not vector dimensions):

```python
payload = {
    "file_hash": str,           # SHA256 of source PDF
    "ingestion_id": str,        # Ingestion identifier
    "project_id": str,          # Project identifier (REQUIRED for security)
    "page_number": int,         # Page number (1-based)
    "chunk_index": int,         # Index within page
    "chunk_text_length": int,   # Length of chunk text
    "bbox": Optional[Dict],     # Bounding box: {x, y, w, h} (if available)
}
```

**Note**: In conservative mode, `bbox` or `span` is REQUIRED (line 182-193).

### 1.4 Chunk Storage

- **Database**: Qdrant (vector database)
- **Collection**: `"document_chunks"` (default, line 39)
- **Vector ID**: `chunk_id` (SHA256 hash)
- **Vector**: Embedding vector (1024 dimensions by default, `EMBEDDING_DIMENSION`)
- **Payload**: Metadata dict (as above)
- **Upsert**: `client.upsert(collection_name, points)` (line 222-225)

### 1.5 Chunk Text Storage

Chunk text is stored in Qdrant payload as `text_content` during ingestion (in addition to embedding vectors):
- **Vector ID** = `chunk_id`
- **Payload** includes `text_content` plus metadata
- Text is retrieved via `payload["text_content"]` in `retrieve_chunks_by_query`

**Note**: This makes retrieval self-contained (no separate text store lookup for chunk previews), but governance/audit may still prefer canonical text in ArangoDB depending on system-of-record policy.

---

## 2. Retrieval

### 2.1 Embedding Model

**Configuration**: `src/shared/config.py`
- **Model ID**: `EMBEDDER_MODEL_ID` (default: `"nvidia/nv-embedqa-e5-v5"`)
- **Dimension**: `EMBEDDING_DIMENSION` (default: 1024)
- **Service**: Embedder service (`http://embedder:30010`)
- **Implementation**: `src/embedder/app.py` (SentenceTransformer with CrossEncoder)

### 2.2 Retrieval Function

**Primary File**: `src/orchestrator/storage/qdrant.py`

**Key Function**: `QdrantStorage.retrieve_chunks_by_query()`
- **Line**: 405-543
- **Signature**: `retrieve_chunks_by_query(query_text, project_id, ingestion_id=None, file_hashes=None, limit=5, query_vector=None, top_k_embed=None, top_k_rerank=None, use_reranker=True)`

### 2.3 Retrieval Flow

1. **Query Embedding** (if `query_vector` not provided):
   - Calls embedder service: `POST {embedder_url}/embed`
   - Payload: `{"texts": [query_text]}`
   - Response: `{"embeddings": [[...]]}`
   - Extracts first embedding as `query_vector`
   - **Fallback**: Zero vector if embedding fails (line 458-459)

2. **Qdrant Search**:
   - Builds filter: `project_id` (REQUIRED), optional `ingestion_id`, optional `file_hashes`
   - Searches: `client.search(collection_name, query_vector, query_filter, limit, with_payload=True)`
   - **Limit**: `top_k_embed` if reranker enabled (default: 64), else `limit` (default: 5)

3. **Reranking** (if `use_reranker=True`):
   - Calls reranker service: `POST {reranker_url}/rerank`
   - Payload: `{"query": query_text, "documents": chunks, "top_k": top_k_rerank}`
   - Returns top-M reranked chunks (default: `limit`)
   - **Fallback**: Top-M by embedding score if reranker fails

4. **Result Format**:
   ```python
   {
       "chunk_id": str,
       "text_content": str,      # From payload
       "payload": Dict,          # Full Qdrant payload
       "score": float,           # Embedding score (or rerank_score if reranked)
       "rerank_score": Optional[float],  # If reranked
       "rerank_rank": Optional[int],     # If reranked
       "file_hash": str,
       "ingestion_id": str,
       "page_number": int,
       "bbox": Optional[Dict],
       "chunk_index": int,
   }
   ```

### 2.4 RQ-Scoped Retrieval

**Location**: `src/orchestrator/nodes/cartography.py` (line 361-391)

**Flow**:
- Cartographer node retrieves chunks per Research Question
- For each RQ: `qdrant_storage.retrieve_chunks_by_query(rq_text, project_id, ingestion_id, limit=chunks_per_rq)`
- Default: `CARTOGRAPHER_CHUNKS_PER_RQ=5` (configurable via env var)
- Results stored in `rq_scoped_chunks` dict: `{rq_id: [chunks]}`

---

## 3. Manuscript Text Storage

### 3.1 Data Model

**Schema**: `src/shared/schema.py`

**Class**: `ManuscriptBlock` (line 422-458)
```python
{
    "id": Optional[str],           # ArangoDB _id
    "key": Optional[str],          # ArangoDB _key
    "block_id": str,               # Unique block identifier within project
    "section_title": str,          # Section heading
    "content": str,                # Block content (Markdown format)
    "order_index": int,            # Order for sequencing
    "claim_ids": List[str],        # Linked claim IDs (REQUIRED in conservative mode)
    "citation_keys": List[str],    # BibTeX citation keys
    "project_id": Optional[str],   # Project identifier
    "version": int,                # Version number (for auditability)
    "created_at": Optional[str],   # ISO timestamp
    "updated_at": Optional[str],   # ISO timestamp
}
```

**Storage**: ArangoDB collection `"manuscript_blocks"` (not a single string, but blocks)

### 3.2 Persistence

**Service**: `src/manuscript/service.py`

**Key Function**: `ManuscriptService.save_block()`
- **Line**: 144-216
- **Collection**: `"manuscript_blocks"`
- **Document Key**: `f"{project_id}_{block_id}_v{version}"`
- **Versioning**: Each save increments version (line 179)
- **Citation Validation**: Librarian Key-Guard validates citations (line 174-176)

### 3.3 Manuscript Structure

**Not a single string**: Manuscript is stored as a **list of blocks**.

- Each block is a separate document in ArangoDB
- Blocks have `order_index` for sequencing
- Blocks are linked to claims via `claim_ids` (REQUIRED in conservative mode)
- Blocks are linked to citations via `citation_keys`

**LangGraph State**: `ResearchState.manuscript_blocks: List[ManuscriptBlock]` (line 66)

### 3.4 Artifact Manifest

**Location**: `src/orchestrator/artifacts/manifest_builder.py`

**Function**: `build_manifest()` (line 102-219)

**Storage**:
- **Filesystem**: `/raid/artifacts/{project_id}/{job_id}/artifact_manifest.json`
- **ArangoDB**: `artifact_manifests` collection

**Contents**:
- `blocks`: List of `BlockArtifact` (per-block stats: word_count, citation_count, tone_flags, supported_by)
- `tables`: List of `TableArtifact`
- `figures`: List of `FigureArtifact`
- `metrics`: Aggregate counts
- `rigor_level`: exploratory or conservative

**Note**: Artifact manifest is written at job completion (Saver node).

---

## 4. LangGraph Nodes: Context Assembly and LLM Calls

### 4.1 Cartographer Node

**Location**: `src/orchestrator/nodes/cartography.py`

**Function**: `cartographer_node()` (line 292-401)

**Context Assembly**:
1. **RQ-Scoped Retrieval** (line 361-391):
   - Retrieves chunks per RQ from Qdrant
   - Stores in `rq_scoped_chunks` dict

2. **Established Knowledge Query** (line 398-399):
   - Calls `_query_established_knowledge()` (line 76-145)
   - Queries ArangoDB for `candidate_knowledge` and `canonical_knowledge`
   - Filters by entity names and reference IDs

3. **Prompt Wrapping** (line 396):
   - Calls `wrap_prompt_with_context()` (from `src/orchestrator/nodes/base.py`)
   - Injects Thesis, RQs, Anti-Scope into system prompt

4. **LLM Call** (line 401+):
   - Calls `call_expert_with_fallback()` (from `src/orchestrator/nodes/nodes.py`)
   - Uses Worker service (SGLang)
   - Prompt: System prompt (with context) + user message (raw_text + chunks + knowledge)

### 4.2 Synthesizer Node

**Location**: `src/orchestrator/nodes/synthesis.py`

**Function**: `synthesizer_node()` (line 24-167)

**Context Assembly**:
1. **Prompt Fetching** (line 52):
   - Fetches prompt from Prompt Registry (Opik)
   - Fallback to `DEFAULT_SYNTHESIZER_PROMPT`

2. **Prompt Wrapping** (line 60):
   - Calls `wrap_prompt_with_context()` to inject ProjectConfig

3. **Claims Preparation** (line 71-83):
   - Extracts claims from `triples` in state
   - Formats as JSON for LLM input

4. **LLM Call** (line 86+):
   - Calls `call_expert_with_fallback()` with Brain service
   - Prompt: System prompt (with context) + user message (claims JSON + synthesis instruction)

**Output**: Manuscript blocks (parsed from JSON or single block)

### 4.3 Prompt Context Injection

**Location**: `src/orchestrator/nodes/base.py`

**Function**: `wrap_prompt_with_context()` (line 14-52)

**Process**:
1. Extracts `project_context` from state
2. Prepends to system prompt:
   - Thesis (if available)
   - Research Questions (if available)
   - Anti-Scope (if available, with strict instruction in conservative mode)
3. Returns enhanced system prompt

**Note**: All nodes use this wrapper to ensure ProjectConfig is injected.

### 4.4 LLM Client

**Location**: `src/shared/llm_client.py`

**Function**: `chat()` (line 267-307)

**Process**:
1. Normalizes tools (if provided)
2. Builds payload: `{"messages": messages, "model": model, ...}`
3. Calls `call_model()` with retry/fallback
4. Returns `(response_json, meta)` where `meta` includes duration_ms, tokens, expert_metadata

**Unified Gateway**: NO direct `requests.post` to SGLang. All inference passes through `llm_client.chat()`.

---

## 5. UI: Evidence Dock and Manuscript Editor

### 5.1 Evidence Dock

**Location**: `src/console/components/EvidenceDock.tsx`

**Component**: `EvidenceDock` (line 48-642)

**Data Sources**:
1. **Corpus Files** (line 167-214):
   - **Endpoint**: `GET /api/proxy/orchestrator/api/projects/{projectId}/files`
   - **Fallback**: `activeProject.seed_files` from Zustand store
   - Displays list of uploaded files with status

2. **Ingestion Status** (line 57-80):
   - **Endpoint**: `GET /api/proxy/orchestrator/api/projects/{projectId}/ingest/{ingestionId}/status`
   - Polls every 2 seconds for status updates
   - Displays progress, metadata (pages, tables, figures), error messages

3. **File Upload** (via `FileUploader` component):
   - **Endpoint**: `POST /api/proxy/orchestrator/api/projects/{projectId}/ingest/pdf`
   - Uploads PDF file, triggers ingestion workflow

**Note**: Evidence Dock does **not** directly display retrieved chunks. It shows uploaded files and ingestion status. Chunks are displayed in the Knowledge Stream (Graph View).

### 5.2 Manuscript Editor

**Location**: `src/console/components/ZenManuscriptEditor.tsx`

**Component**: `ZenManuscriptEditor` (line 53-531)

**Data Sources**:
1. **Blocks** (props):
   - Received from parent: `blocks={manifest?.blocks || []}`
   - Parent: `src/console/app/projects/[id]/manuscript/page.tsx` (line 125)

2. **Manifest Fetching** (from `page.tsx`, line 49-66):
   - **Endpoint**: `GET /api/proxy/orchestrator/workflow/result/{jobId}`
   - Response: `{result: {artifact_manifest: {...}}}`
   - Extracts `manifest.blocks` for editor
   - Listens for `refresh-manifest` event

3. **Claim Data** (line 69-98):
   - **Endpoint**: `GET /api/proxy/orchestrator/workflow/result/{jobId}`
   - Extracts `result.extracted_json.triples`
   - Builds map: `claim_id -> source_pointer`

**Manuscript Editor Features**:
- Displays blocks with `section_title` and `content` (Markdown)
- Shows `claim_ids` and `citation_keys` per block
- Allows editing, adding, deleting blocks
- Ghost mode (add/delete buttons only on active block)
- Fork block (generate alternate version with different rigor level)

### 5.3 Workflow Result Endpoint

**Location**: `src/orchestrator/server.py`

**Endpoint**: `GET /workflow/result/<job_id>` (line 1865)

**Response**:
```json
{
  "result": {
    "extracted_json": {
      "triples": [...]
    },
    "artifact_manifest": {
      "blocks": [...],
      "tables": [...],
      "figures": [...],
      "metrics": {...}
    }
  }
}
```

**Note**: This endpoint returns the final state of a workflow execution, including extracted triples and artifact manifest.

---

## 6. Research Questions (RQs) Data Model

### 6.1 Storage

**Collection**: ArangoDB `"projects"` collection

**Field**: `research_questions: List[str]`

**Schema**: `src/project/types.py`

**Class**: `ProjectConfig` (line 42-74)
```python
{
    "id": str,                      # Project UUID
    "title": str,
    "thesis": str,
    "research_questions": List[str],  # RQs stored as list of strings
    "anti_scope": Optional[List[str]],
    "target_journal": Optional[str],
    "seed_files": List[str],
    "rigor_level": str,             # "exploratory" or "conservative"
    "created_at": str,
    "last_updated": Optional[str],
    "tags": Optional[List[str]],
}
```

### 6.2 Access

**API Endpoint**: `GET /api/projects/<project_id>` (line 875+)

**Service**: `src/project/service.py`

**Function**: `ProjectService.get_project()`

**Note**: RQs are part of `ProjectConfig`, which is loaded into `ResearchState.project_config` at workflow start.

### 6.3 Usage in Nodes

- **Cartographer**: Uses RQs for RQ-scoped chunk retrieval (line 362-378 in `cartography.py`)
- **Prompt Context**: RQs are injected into system prompts via `wrap_prompt_with_context()`
- **Claim Tagging**: Claims can have `rq_hits: List[str]` field (line 111 in `claims.py`)

---

## 7. Jobs and Artifacts: Storage for RetrievalBundle

### 7.1 Job Store

**Location**: `src/orchestrator/job_store.py`

**Collection**: ArangoDB `"jobs"` collection

**Structure** (line 55-71):
```python
{
    "_key": str,                    # job_id (UUID)
    "job_id": str,
    "status": str,                  # JobStatus enum
    "progress": float,              # 0.0 to 1.0
    "message": str,
    "error": Optional[str],
    "created_at": str,              # ISO timestamp
    "updated_at": str,              # ISO timestamp
    "initial_state": Dict,          # Initial ResearchState dict
    "result": Optional[Dict],       # Final result (can include RetrievalBundle)
    "idempotency_key": Optional[str],
    "parent_job_id": Optional[str],
    "job_version": int,
    "reprocess_reason": Optional[str],
    "applied_reference_ids": Optional[List[str]],
}
```

**Functions**:
- `create_job_record()`: Creates job record in ArangoDB
- `update_job_record()`: Updates job status/progress/result
- `get_job_record()`: Retrieves job record

**Note**: `result` field can store RetrievalBundle artifacts.

### 7.2 Artifact Manifest

**Location**: `src/orchestrator/artifacts/manifest_builder.py`

**Collection**: ArangoDB `"artifact_manifests"` collection

**Filesystem**: `/raid/artifacts/{project_id}/{job_id}/artifact_manifest.json`

**Structure**: `ArtifactManifest` (from `src/shared/schema.py`, line 764-777)
```python
{
    "project_id": str,
    "job_id": str,
    "doc_hash": str,
    "created_at": datetime,
    "rigor_level": str,             # "conservative" or "exploratory"
    "rq_links": List[str],          # Research question IDs linked to artifacts
    "blocks": List[BlockArtifact],
    "tables": List[TableArtifact],
    "figures": List[FigureArtifact],
    "metrics": ArtifactMetrics,
    "flags": List[str],
    "totals": Dict[str, int],
}
```

**Note**: Artifact manifest could be extended to include `retrieval_bundles: List[RetrievalBundle]`.

### 7.3 State Storage

**LangGraph Checkpointing**: Uses `InMemorySaver` by default (from `src/shared/config.py`, line 15-28)

**ResearchState**: Stored in memory during workflow execution, persisted to `jobs.result` at completion.

**Note**: RetrievalBundle could be stored in:
1. `ResearchState` (as a field, e.g., `retrieval_bundles: List[RetrievalBundle]`)
2. `jobs.result` (as part of job result)
3. ArangoDB `"retrieval_bundles"` collection (separate collection for queryability)
4. `artifact_manifests` (as part of artifact manifest)

---

## 8. Summary

### 8.1 Chunking
- **Where**: `src/orchestrator/storage/qdrant.py` → `ingest_document_chunks()`
- **Chunk ID**: SHA256(`{file_hash}|{page_number}|{chunk_index}`)
- **Metadata**: Stored in Qdrant payload (file_hash, ingestion_id, project_id, page_number, chunk_index, bbox, etc.)
- **Storage**: Qdrant collection `"document_chunks"` (vector ID = chunk_id, payload = metadata)

### 8.2 Retrieval
- **Embedding Model**: `nvidia/nv-embedqa-e5-v5` (1024 dimensions)
- **Service**: Embedder (`http://embedder:30010`)
- **Query Flow**: Embed query → Qdrant search (top-K) → Rerank (top-M) → Return
- **Function**: `QdrantStorage.retrieve_chunks_by_query()` (supports reranking)
- **RQ-Scoped**: Cartographer retrieves chunks per RQ (default: 5 chunks per RQ)

### 8.3 Manuscript
- **Structure**: List of blocks (not single string)
- **Storage**: ArangoDB `"manuscript_blocks"` collection
- **Schema**: `ManuscriptBlock` (block_id, section_title, content, claim_ids, citation_keys, version)
- **Service**: `ManuscriptService.save_block()`
- **Artifact Manifest**: Stores per-block stats (word_count, citation_count, tone_flags, supported_by)

### 8.4 LangGraph Nodes
- **Cartographer**: Assembles context (RQ-scoped chunks + established knowledge), wraps prompt with ProjectConfig, calls Worker
- **Synthesizer**: Prepares claims JSON, wraps prompt with ProjectConfig, calls Brain
- **Context Injection**: `wrap_prompt_with_context()` injects Thesis, RQs, Anti-Scope into system prompts
- **LLM Gateway**: All inference passes through `llm_client.chat()` (no direct SGLang calls)

### 8.5 UI
- **Evidence Dock**: Shows uploaded files and ingestion status (does not display chunks directly)
- **Manuscript Editor**: Fetches blocks from `/workflow/result/{jobId}` → `artifact_manifest.blocks`
- **Data Flow**: `ManifestPage` → fetches manifest → passes blocks to `ZenManuscriptEditor`

### 8.6 RQs
- **Storage**: ArangoDB `"projects"` collection → `research_questions: List[str]`
- **Access**: Part of `ProjectConfig`, loaded into `ResearchState.project_config`
- **Usage**: RQ-scoped chunk retrieval, prompt context injection, claim tagging (`rq_hits`)

### 8.7 Jobs/Artifacts
- **Job Store**: ArangoDB `"jobs"` collection (can store RetrievalBundle in `result` field)
- **Artifact Manifest**: ArangoDB `"artifact_manifests"` collection + filesystem (`/raid/artifacts/...`)
- **Potential Storage**: RetrievalBundle could be stored in:
  1. `ResearchState.retrieval_bundles`
  2. `jobs.result.retrieval_bundles`
  3. ArangoDB `"retrieval_bundles"` collection
  4. `artifact_manifests.retrieval_bundles`

---

## 9. Key Integration Points

### 9.1 RetrievalBundle Persistence
- **Option 1**: Store in `ResearchState.retrieval_bundles: List[RetrievalBundle]` (persist to `jobs.result`)
- **Option 2**: Store in separate ArangoDB collection `"retrieval_bundles"` (for queryability)
- **Option 3**: Store in `artifact_manifests.retrieval_bundles` (linked to job_id)

### 9.2 Analytical Notes Storage
- **Collection**: ArangoDB `"analytical_notes"` collection (needs to be created)
- **Fields**: note_id, project_id, text, tags, state (Draft/Manuscript), linked_rq, created_at, updated_at

### 9.3 Blueprint Storage
- **Collection**: ArangoDB `"manuscript_blueprints"` collection (needs to be created)
- **Fields**: blueprint_id, project_id, sections (List[BlueprintSection]), target_journal, created_at, updated_at

### 9.4 Section Synthesis Loop
- **Location**: New node in `src/orchestrator/nodes/` (e.g., `blueprint_synthesis.py`)
- **Flow**: For each section in blueprint → retrieve (embed + rerank) → build Packets A/B → call Nemotron 49B → Critic cross-examination → save block
- **Integration**: Wire into existing workflow graph after Cartographer, before Synthesizer

---

## 10. References

### File Paths
- Chunking: `src/orchestrator/storage/qdrant.py`
- Retrieval: `src/orchestrator/storage/qdrant.py` → `retrieve_chunks_by_query()`
- Manuscript Service: `src/manuscript/service.py`
- Manuscript Schema: `src/shared/schema.py` → `ManuscriptBlock`
- LangGraph Nodes: `src/orchestrator/nodes/cartography.py`, `src/orchestrator/nodes/synthesis.py`
- Prompt Context: `src/orchestrator/nodes/base.py` → `wrap_prompt_with_context()`
- LLM Client: `src/shared/llm_client.py` → `chat()`
- Evidence Dock: `src/console/components/EvidenceDock.tsx`
- Manuscript Editor: `src/console/components/ZenManuscriptEditor.tsx`
- Manifest Page: `src/console/app/projects/[id]/manuscript/page.tsx`
- Job Store: `src/orchestrator/job_store.py`
- Artifact Manifest: `src/orchestrator/artifacts/manifest_builder.py`
- Project Config: `src/project/types.py` → `ProjectConfig`
- Research Questions: Stored in `projects.research_questions` (List[str])

### Key Functions
- `QdrantStorage.ingest_document_chunks()`: Chunking
- `QdrantStorage.retrieve_chunks_by_query()`: Retrieval
- `QdrantStorage._generate_chunk_id()`: Chunk ID generation
- `QdrantStorage._split_text_into_chunks()`: Text splitting
- `cartographer_node()`: RQ-scoped retrieval and extraction
- `synthesizer_node()`: Manuscript block synthesis
- `wrap_prompt_with_context()`: ProjectConfig injection
- `ManuscriptService.save_block()`: Manuscript persistence
- `build_manifest()`: Artifact manifest creation
- `create_job_record()`: Job creation
- `update_job_record()`: Job status updates
