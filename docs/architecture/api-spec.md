# Project Vyasa API Specification (Orchestrator)

> **Complete API reference** for the Orchestrator service (Port 8000).

## Base URL

- **Development**: `http://localhost:8000`
- **Docker Network**: `http://orchestrator:8000`
- **Internal DNS**: `vyasa-orchestrator`

## Authentication

Currently, the Orchestrator API does not require authentication (runs on internal Docker network). For production deployments, consider adding API key authentication.

---

## Health & System Endpoints

### GET `/health`

Health check endpoint for Docker healthcheck and system monitoring.

**Query Parameters**:
- `deep` (optional, boolean): If `true`, performs deep health check including dependency verification

**Response** (`200` - Quick Check):
```json
{
  "status": "healthy",
  "service": "orchestrator",
  "version": "1.0.0"
}
```

**Response** (`200` or `503` - Deep Check with `?deep=true`):
```json
{
  "status": "healthy" | "unhealthy",
  "service": "orchestrator",
  "version": "1.0.0",
  "dependencies": {
    "arango": "ok" | "error",
    "worker": "ok" | "error"
  }
}
```

**Status Codes**:
- `200`: Service is healthy (or all dependencies healthy if `deep=true`)
- `503`: Service is unhealthy (dependency failure if `deep=true`)

**Code Reference**: `src/orchestrator/server.py` → `health()`

---

### GET `/system/pulse`

Unified hardware/software pulse for DGX Spark monitoring.

**Response** (`200`):
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "unified_memory": {
    "total_gb": 128,
    "used_gb": 96,
    "available_gb": 32
  },
  "gpu": {
    "name": "NVIDIA Grace Blackwell",
    "memory_total_gb": 128,
    "memory_used_gb": 96
  },
  "services": {
    "cortex-brain": "running",
    "cortex-worker": "running",
    "cortex-vision": "running"
  }
}
```

**Status Codes**:
- `200`: Metrics collected successfully
- `500`: Unable to collect system metrics

**Code Reference**: `src/orchestrator/server.py` → `system_pulse()`

---

## Project Management Endpoints

### POST `/api/projects`

Create a new project with Thesis, Research Questions, and Anti-Scope.

**Request Body** (JSON):
```json
{
  "title": "Security Analysis of Web Applications",
  "thesis": "Modern web applications are vulnerable to XSS attacks...",
  "research_questions": [
    "What are the most common XSS attack vectors?",
    "How effective are CSP headers in preventing XSS?"
  ],
  "anti_scope": ["Mobile applications", "Server-side attacks"],
  "target_journal": "IEEE Security & Privacy",
  "seed_files": []
}
```

**Response** (`201`):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Security Analysis of Web Applications",
  "thesis": "Modern web applications are vulnerable to XSS attacks...",
  "research_questions": ["..."],
  "anti_scope": ["..."],
  "target_journal": "IEEE Security & Privacy",
  "seed_files": [],
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Status Codes**:
- `201`: Project created successfully
- `400`: Validation errors (empty title, thesis, or no RQs)
- `503`: Database unavailable

**Code Reference**: `src/orchestrator/server.py` → `create_project()`

---

### GET `/api/projects`

List all projects as summaries.

**Response** (`200`):
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Security Analysis of Web Applications",
    "created_at": "2024-01-15T10:30:00Z"
  },
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "title": "PLC Security Research",
    "created_at": "2024-01-14T09:20:00Z"
  }
]
```

**Status Codes**:
- `200`: Success
- `503`: Database unavailable

**Code Reference**: `src/orchestrator/server.py` → `list_projects()`

---

### GET `/api/projects/<project_id>`

Get full project details by ID.

**Path Parameters**:
- `project_id` (string, required): UUID of the project

**Response** (`200`):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Security Analysis of Web Applications",
  "thesis": "Modern web applications are vulnerable to XSS attacks...",
  "research_questions": ["..."],
  "anti_scope": ["..."],
  "target_journal": "IEEE Security & Privacy",
  "seed_files": ["paper1.pdf", "paper2.pdf"],
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Status Codes**:
- `200`: Project found
- `404`: Project not found
- `503`: Database unavailable

**Code Reference**: `src/orchestrator/server.py` → `get_project()`

---

## Document Ingestion Endpoints

### POST `/ingest/pdf`

Convert PDF to Markdown and prepare for workflow processing. **Requires `project_id`**.

**Request** (multipart/form-data):
- `file` (file, required): PDF file to process
- `project_id` (string, required): UUID of the project

**Response** (`200`):
```json
{
  "markdown": "# Document Title\n\nContent...",
  "filename": "paper.pdf",
  "project_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Status Codes**:
- `200`: PDF processed successfully
- `400`: Invalid file format (not PDF) or missing `project_id`
- `404`: Project not found
- `503`: Database unavailable

**Notes**:
- This endpoint is **preview-only** and does not return reusable `image_paths`
- For full workflow processing, use `POST /workflow/submit` with multipart

**Code Reference**: `src/orchestrator/server.py` → `ingest_pdf()`

---

## Workflow Endpoints

### POST `/workflow/submit`

Submit an asynchronous workflow job for document processing. Returns immediately with `job_id` for polling.

**Request** (JSON):
```json
{
  "raw_text": "Document text...",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "source_filename": "paper.pdf"
}
```

**Request** (multipart/form-data):
- `file` (file, required): PDF file to process
- `project_id` (string, required): UUID of the project

**Response** (`202`):
```json
{
  "job_id": "job-123456",
  "status": "PENDING",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "project_context": {
    "thesis": "...",
    "research_questions": ["..."]
  }
}
```

**Status Codes**:
- `202`: Job submitted successfully
- `400`: Missing `project_id` or invalid request
- `404`: Project not found
- `503`: Database unavailable or job queue full

**Notes**:
- Jobs are processed asynchronously in background threads
- Maximum 2 concurrent jobs (semaphore-controlled)
- Use `GET /workflow/status/<job_id>` to poll for completion

**Code Reference**: `src/orchestrator/server.py` → `submit_workflow()`

---

### GET `/workflow/status/<job_id>`

Get current status of a workflow job (legacy endpoint, percentage-based).

**Path Parameters**:
- `job_id` (string, required): UUID of the job

**Response** (`200`):
```json
{
  "status": "PENDING" | "RUNNING" | "COMPLETED" | "FAILED",
  "progress": 0.75,
  "message": "Processing..."
}
```

**Status Codes**:
- `200`: Job found
- `404`: Job not found

**Code Reference**: `src/orchestrator/server.py` → `get_workflow_status()`

---

### GET `/jobs/<job_id>/status`

Get current status of a workflow job (researcher-facing, step-based).

**Path Parameters**:
- `job_id` (string, required): UUID of the job

**Response** (`200`):
```json
{
  "status": "running" | "completed" | "failed",
  "progress": 75,
  "step": "Validating Logic...",
  "error": null
}
```

**Progress Mapping**:
- `__start__` → 5% "Initializing..."
- `cartographer` → 30% "Extracting Claims..."
- `vision` → 50% "Analyzing Visuals..."
- `critic` → 75% "Validating Logic..."
- `saver` → 90% "Saving to Graph..."
- `__end__` → 100% "Complete"

**Status Codes**:
- `200`: Job found
- `404`: Job not found
- `500`: Unexpected server error

**Code Reference**: `src/orchestrator/server.py` → `get_job_status()`

---

### GET `/workflow/result/<job_id>`

Get final result of a completed workflow job. **Guarantees `extracted_json.triples` array** (normalized).

**Path Parameters**:
- `job_id` (string, required): UUID of the job

**Response** (`200` - SUCCEEDED):
```json
{
  "status": "SUCCEEDED",
  "extracted_json": {
    "triples": [
      {
        "subject": "PLC",
        "predicate": "has_vulnerability",
        "object": "CVE-2024-1234",
        "source_pointer": {
          "doc_hash": "abc123...",
          "page": 5,
          "bbox": [100, 200, 300, 250],
          "snippet": "The vulnerability in PLC systems..."
        },
        "confidence": 0.9
      }
    ]
  },
  "nodes": [...],
  "edges": [...]
}
```

**Response** (`202` - QUEUED/RUNNING):
```json
{
  "status": "QUEUED" | "RUNNING",
  "message": "Job is still processing"
}
```

**Response** (`500` - FAILED):
```json
{
  "status": "FAILED",
  "error": "Error message here"
}
```

**Status Codes**:
- `200`: Job succeeded, result available
- `202`: Job still processing
- `404`: Job not found
- `500`: Job failed

**Code Reference**: `src/orchestrator/server.py` → `get_workflow_result()`

---

### POST `/workflow/process`

Synchronous workflow processing (legacy endpoint, kept for backward compatibility).

**Request** (JSON):
```json
{
  "raw_text": "Document text...",
  "project_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response** (`200`):
```json
{
  "extracted_json": {
    "triples": [...]
  },
  "nodes": [...],
  "edges": [...]
}
```

**Status Codes**:
- `200`: Processing completed
- `400`: Invalid request
- `500`: Processing failed

**Notes**: This endpoint blocks until processing completes. For async processing, use `POST /workflow/submit`.

**Code Reference**: `src/orchestrator/server.py` → `process_workflow()`

---

## Job Management Endpoints

### POST `/jobs/<job_id>/finalize`

Finalize a completed job, triggering knowledge synthesis and harvesting.

**Path Parameters**:
- `job_id` (string, required): UUID of the job

**Request Body** (JSON, optional):
```json
{
  "trigger_synthesis": true,
  "trigger_harvesting": true
}
```

**Response** (`202`):
```json
{
  "status": "accepted",
  "message": "Finalization started in background",
  "job_id": "job-123456"
}
```

**Background Operations**:
1. **Knowledge Synthesis**: Merges expert-verified claims into `canonical_knowledge`
2. **Knowledge Harvesting**: Generates JSONL datasets for fine-tuning
3. **Export Generation**: Creates Markdown/BibTeX/JSON-LD exports

**Status Codes**:
- `202`: Finalization started
- `404`: Job not found
- `400`: Job not in SUCCEEDED state

**Code Reference**: `src/orchestrator/server.py` → `finalize_job()`

---

### GET `/jobs/<job_id>/export`

Export job results in various formats (Markdown, BibTeX, JSON-LD).

**Path Parameters**:
- `job_id` (string, required): UUID of the job

**Query Parameters**:
- `format` (string, optional): Export format (`markdown`, `bibtex`, `jsonld`). Default: `markdown`
- `include_drafts` (boolean, optional): Include unverified claims. Default: `false`

**Response** (`200` - Markdown):
```markdown
# Document Title

## Introduction

Content here...
```

**Response** (`200` - BibTeX):
```bibtex
@article{vyasa2024,
  title={Document Title},
  author={...},
  year={2024},
  journal={IEEE Security \& Privacy}
}
```

**Response** (`200` - JSON-LD):
```json
{
  "@context": "https://schema.org",
  "@type": "CreativeWork",
  "name": "Document Title",
  "author": {...},
  "datePublished": "2024-01-15"
}
```

**Status Codes**:
- `200`: Export generated successfully
- `404`: Job not found
- `400`: Invalid format

**Notes**:
- Default behavior excludes claims where `is_expert_verified == false` (unless `include_drafts=true`)
- BibTeX export is IEEE/ACM-compliant
- JSON-LD export uses Schema.org context

**Code Reference**: `src/orchestrator/server.py` → `export_job()`

---

### PATCH `/jobs/<job_id>/extractions/merge`

Merge two graph nodes by creating an alias relationship and migrating claims.

**Path Parameters**:
- `job_id` (string, required): UUID of the job

**Request Body** (JSON):
```json
{
  "source_node_id": "entity_1",
  "target_node_id": "entity_2"
}
```

**Response** (`200`):
```json
{
  "status": "merged",
  "source_node_id": "entity_1",
  "target_node_id": "entity_2",
  "claims_migrated": 5,
  "source_pointers_migrated": 5
}
```

**Process**:
1. Creates alias relationship in `node_aliases` collection
2. Migrates all linked claims from source to target
3. Migrates all `source_pointers` from source to target
4. Updates graph in ArangoDB

**Status Codes**:
- `200`: Merge successful
- `404`: Job not found
- `400`: Invalid request (missing node IDs or same node)
- `500`: Merge failed

**Code Reference**: `src/orchestrator/server.py` → `merge_extractions()`

---

## Streaming Endpoints

### GET `/jobs/<job_id>/stream`

Server-Sent Events (SSE) stream for live graph updates during workflow execution.

**Path Parameters**:
- `job_id` (string, required): UUID of the job

**Response** (`200` - text/event-stream):
```
event: graph_update
data: {"type": "graph_update", "timestamp": "2024-01-15T10:30:00Z", "nodes": [...], "edges": [...]}

event: graph_update
data: {"type": "graph_update", "timestamp": "2024-01-15T10:30:01Z", "nodes": [...], "edges": [...]}
```

**Event Payload Structure**:
```json
{
  "type": "graph_update",
  "timestamp": "2024-01-15T10:30:00Z",
  "nodes": [
    {
      "id": "entity_1",
      "label": "Concept A",
      "type": "concept"
    }
  ],
  "edges": [
    {
      "source": "entity_1",
      "target": "entity_2",
      "label": "causes",
      "evidence": "...",
      "confidence": 0.9
    }
  ]
}
```

**Status Codes**:
- `200`: Stream started
- `404`: Job not found

**Notes**: Stream closes when job completes or fails.

**Code Reference**: `src/orchestrator/server.py` → `stream_job_updates()` (if implemented)

---

## Error Responses

All endpoints may return error responses in the following format:

```json
{
  "error": "Error message here",
  "details": "Optional detailed error information"
}
```

**Common Status Codes**:
- `400`: Bad Request (validation errors, missing parameters)
- `404`: Not Found (job/project not found)
- `500`: Internal Server Error (unexpected errors)
- `503`: Service Unavailable (database unavailable, dependency failures)

---

## Rate Limiting

Currently, the Orchestrator does not enforce rate limiting. For production deployments, consider:
- Per-IP rate limiting
- Per-project rate limiting
- Job queue size limits (currently max 2 concurrent jobs)

---

## Versioning

API versioning is not currently implemented. All endpoints are under `/` root. For future versions, consider:
- `/v1/` prefix for version 1
- `/v2/` prefix for version 2

---

## Code References

- **Main Server**: `src/orchestrator/server.py`
- **Job Manager**: `src/orchestrator/job_manager.py`
- **Workflow**: `src/orchestrator/workflow.py`
- **State**: `src/orchestrator/state.py`
- **Export Service**: `src/orchestrator/export_service.py`
- **Synthesis Service**: `src/orchestrator/synthesis_service.py`
- **Harvester**: `src/orchestrator/harvester_node.py`
