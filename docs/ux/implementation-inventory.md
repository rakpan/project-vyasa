# UX Implementation Inventory: Projects Hub, Create, Workbench

**Status**: Current State Documentation (No Refactoring)  
**Date**: 2025-01-02  
**Purpose**: Ground truth inventory of existing routes, components, APIs, and state management before UX improvements

---

## 1. Routes & Pages

### 1.1 Projects Hub (`/projects`)
**File**: `src/console/app/projects/page.tsx`

**Purpose**: Lists all research projects and provides project creation dialog

**Features**:
- Project list table with columns: Title, Created Date, Latest Job Status
- "New Project" button (Dialog trigger)
- Resume workbench action for projects with jobs
- Fetches projects via `useProjectStore.fetchProjects()`
- Fetches latest job per project via `GET /api/projects/{id}/jobs?limit=1`

**Navigation**:
- Create project → Navigates to `/projects/{newProjectId}`
- Resume workbench → Navigates to `/research-workbench?jobId={jobId}&projectId={projectId}&pdfUrl={pdfUrl}`

---

### 1.2 Project Workbench (`/projects/[id]`)
**File**: `src/console/app/projects/[id]/page.tsx`

**Purpose**: 3-column dashboard for project work (Seed Corpus, Processing, Intent Context)

**Layout**:
- **Left Column (Seed Corpus)**: FileUploader component + file list + "Start Research" button
- **Center Column (Processing)**: Recent jobs list with status badges
- **Right Column (Intent Context)**: Project thesis, RQs, anti-scope display

**Features**:
- Fetches project details via `useProjectStore.setActiveProject(id)`
- Fetches recent jobs via `GET /api/projects/{id}/jobs?limit=5`
- FileUploader uploads to `/api/proxy/orchestrator/ingest/pdf` (preview only)
- "Start Research" button triggers workflow submission (not yet implemented in UI)

**Navigation**:
- Click job → Navigates to `/research-workbench?jobId={jobId}&projectId={projectId}`

---

### 1.3 Project Workbench (3-Pane) (`/projects/[id]/workbench`)
**File**: `src/console/app/projects/[id]/workbench/page.tsx`

**Purpose**: 3-pane resizable research workbench with Source/Evidence, Synthesis Editor, Knowledge Graph

**Layout** (using `react-resizable-panels`):
- **Pane 1 (Left, 30%)**: Source/Evidence - `ZenSourceVault` component (PDF viewer)
- **Pane 2 (Center, 40%)**: Synthesis Editor - `ZenManuscriptEditor` + pinned `ManifestBar`
- **Pane 3 (Right, 30%)**: Knowledge Graph - `LiveGraphWorkbench` component

**Features**:
- Fetches manifest via `GET /api/proxy/orchestrator/workflow/result/{jobId}`
- Extracts `artifact_manifest` from result
- Calculates neutrality score from tone flags
- Listens for `refresh-manifest` window event

**URL Parameters**:
- `jobId`: Required for manifest/graph display
- `pdfUrl`: Optional, for PDF viewer
- `threadId`: Optional, for workflow context

---

### 1.4 Research Workbench (`/research-workbench`)
**File**: `src/console/app/research-workbench/page.tsx`

**Purpose**: Zen-first research cockpit with auto-hide toolbars and focus mode

**Features**:
- Similar 3-pane layout but with different component set
- Uses `ZenManuscriptEditor`, `LiveGraphWorkbench`, `ZenSourceVault`
- Includes `ManifestBar`, `ManuscriptHealthTile`, `InterruptPanel`
- Fetches job status via `GET /api/proxy/orchestrator/workflow/status/{jobId}`
- Fetches manifest via `GET /api/proxy/orchestrator/workflow/result/{jobId}`

**Note**: This appears to be a more advanced/zen-focused version of the workbench. May be redundant with `/projects/[id]/workbench`.

---

## 2. Components

### 2.1 Project-Related Components

#### `FileUploader`
**File**: `src/console/components/FileUploader.tsx`

**Props**:
```typescript
{
  projectId: string
  onUploadComplete?: (filename: string) => void
  onUploadError?: (error: string) => void
}
```

**Functionality**:
- Drag & drop or file browser
- Validates PDF format
- Uploads to `/api/proxy/orchestrator/ingest/pdf` (multipart/form-data)
- Sends `file` + `project_id` in FormData
- **Note**: This endpoint is deprecated (preview-only). Should use `/workflow/submit` for production.

---

#### `ManifestBar`
**File**: `src/console/components/manifest-bar.tsx`

**Props**:
```typescript
{
  manifest?: {
    metrics?: {
      total_words?: number
      total_claims?: number
      claims_per_100_words?: number
      citation_count?: number
    }
    totals?: {
      words?: number
      tables?: number
      citations?: number
      figures?: number
    }
    blocks?: Array<{
      tone_flags?: Array<unknown>
    }>
  }
  neutralityScore?: number
}
```

**Functionality**:
- Displays word count, table count, citation count, tone flags
- Provides manifest download button
- Pinned to top of manuscript editor

---

#### `ZenManuscriptEditor`
**File**: `src/console/components/ZenManuscriptEditor.tsx`

**Purpose**: Manuscript block editor with ghost mode and focus controls

**Props**: (Need to check file for exact interface)

---

#### `ZenSourceVault`
**File**: `src/console/components/ZenSourceVault.tsx`

**Purpose**: PDF viewer with highlight support and vision rescan capability

**Props**: (Need to check file for exact interface)

---

#### `LiveGraphWorkbench`
**File**: `src/console/components/LiveGraphWorkbench.tsx`

**Purpose**: Real-time knowledge graph visualization

**Props**: (Need to check file for exact interface)

---

### 2.2 Reusable UI Components

Located in `src/console/components/ui/`:
- `Button`, `Dialog`, `Input`, `Textarea`, `Card`, `Badge`, `Table`, `Skeleton`, `Alert`, etc.
- Shadcn/UI based components

---

## 3. API Endpoints

### 3.1 Project Management

#### `POST /api/projects`
**Handler**: `src/orchestrator/server.py::create_project()` (line 525)

**Request**:
```json
{
  "title": "string (required)",
  "thesis": "string (required)",
  "research_questions": ["string"] (required, min 1),
  "anti_scope": ["string"] (optional),
  "target_journal": "string (optional)",
  "seed_files": ["string"] (optional)
}
```

**Response** (201):
```json
{
  "id": "uuid",
  "title": "string",
  "thesis": "string",
  "research_questions": ["string"],
  "anti_scope": ["string"] | null,
  "target_journal": "string" | null,
  "seed_files": ["string"],
  "rigor_level": "exploratory" | "conservative",
  "created_at": "ISO timestamp"
}
```

**Errors**: 400 (validation), 503 (DB unavailable)

---

#### `GET /api/projects`
**Handler**: `src/orchestrator/server.py::list_projects()` (line 582)

**Response** (200):
```json
[
  {
    "id": "uuid",
    "title": "string",
    "created_at": "ISO timestamp"
  }
]
```

**Errors**: 503 (DB unavailable)

---

#### `GET /api/projects/{project_id}`
**Handler**: `src/orchestrator/server.py::get_project()` (line 674)

**Response** (200): Full `ProjectConfig` object

**Errors**: 404 (not found), 503 (DB unavailable)

---

#### `GET /api/projects/{project_id}/jobs`
**Handler**: `src/orchestrator/server.py::list_project_jobs()` (line 640)

**Query Params**:
- `limit`: int (default 10, max 50)

**Response** (200):
```json
{
  "jobs": [
    {
      "job_id": "uuid",
      "status": "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "FINALIZED",
      "created_at": "ISO timestamp",
      "updated_at": "ISO timestamp",
      "progress": 0.0-1.0,
      "pdf_path": "string" | null,
      "parent_job_id": "uuid" | null,
      "job_version": int
    }
  ]
}
```

---

#### `GET /api/projects/{project_id}/rigor`
**Handler**: `src/orchestrator/server.py::project_rigor()` (line 608)

**Response** (200):
```json
{
  "project_id": "uuid",
  "rigor_level": "exploratory" | "conservative"
}
```

---

#### `PATCH /api/projects/{project_id}/rigor`
**Handler**: `src/orchestrator/server.py::project_rigor()` (line 608)

**Request**:
```json
{
  "rigor_level": "exploratory" | "conservative"
}
```

**Response** (200): Same as GET

---

### 3.2 Workflow & Ingestion

#### `POST /ingest/pdf` (DEPRECATED)
**Handler**: `src/orchestrator/server.py::ingest_pdf()` (line 342)

**Purpose**: Preview-only PDF → Markdown helper (not for production)

**Request**: multipart/form-data
- `file`: PDF file
- `project_id`: string

**Response** (200):
```json
{
  "markdown": "string",
  "filename": "string",
  "image_count": int,
  "note": "Preview only. Use /workflow/submit to run full pipeline.",
  "project_id": "uuid",
  "project_context": { ... }
}
```

**Note**: This endpoint is deprecated. Use `/workflow/submit` for production.

---

#### `POST /workflow/submit`
**Handler**: `src/orchestrator/server.py::submit_workflow()` (line 905)

**Purpose**: Submit workflow job for asynchronous processing (production endpoint)

**Request** (multipart/form-data):
- `file`: PDF file (optional)
- `project_id`: string (required)
- `idempotency_key`: string (optional)

**Request** (JSON):
```json
{
  "raw_text": "string (required if no file)",
  "pdf_path": "string (optional)",
  "extracted_json": {} (optional),
  "critiques": [] (optional),
  "revision_count": int (optional),
  "project_id": "string (required)",
  "idempotency_key": "string (optional)"
}
```

**Response** (202):
```json
{
  "job_id": "uuid",
  "status": "QUEUED"
}
```

**Flow**:
1. Validates `project_id` exists
2. Fetches `ProjectConfig` from ArangoDB
3. Extracts text from PDF (if provided)
4. Creates workflow job with initial state
5. Starts background thread running LangGraph workflow
6. Returns `job_id` immediately

---

#### `GET /workflow/status/{job_id}`
**Handler**: `src/orchestrator/server.py::get_workflow_status()` (line 1091)

**Response** (PENDING/PROCESSING):
```json
{
  "job_id": "uuid",
  "status": "QUEUED" | "RUNNING",
  "current_step": "Cartographer" | "Critic" | "Saver" | null,
  "progress_pct": 0.0-100.0,
  "created_at": "ISO timestamp",
  "started_at": "ISO timestamp" | null
}
```

**Response** (COMPLETED):
```json
{
  "job_id": "uuid",
  "status": "SUCCEEDED",
  "result": {
    "raw_text": "string",
    "extracted_json": {
      "triples": [...]
    },
    ...
  },
  "progress_pct": 100.0,
  "completed_at": "ISO timestamp"
}
```

**Response** (FAILED):
```json
{
  "job_id": "uuid",
  "status": "FAILED",
  "error": "error message",
  "completed_at": "ISO timestamp"
}
```

---

#### `GET /workflow/result/{job_id}`
**Handler**: `src/orchestrator/server.py::get_workflow_result()` (line 1232)

**Purpose**: Return final result if available, otherwise status

**Response** (QUEUED/RUNNING, 202):
```json
{
  "job_id": "uuid",
  "status": "QUEUED" | "RUNNING",
  "progress_pct": 0.0-100.0
}
```

**Response** (FAILED, 500):
```json
{
  "job_id": "uuid",
  "status": "FAILED",
  "error": "error message"
}
```

**Response** (SUCCEEDED, 200):
```json
{
  "job_id": "uuid",
  "status": "SUCCEEDED",
  "result": {
    "raw_text": "string",
    "extracted_json": {
      "triples": [...]
    },
    "artifact_manifest": {
      "blocks": [...],
      "metrics": {...},
      "totals": {...}
    },
    ...
  }
}
```

**Note**: The `artifact_manifest` is embedded in the result. This is what `ManifestBar` extracts.

---

### 3.3 Knowledge Management

#### `POST /api/knowledge/sideload`
**Handler**: `src/orchestrator/api/knowledge.py::sideload_knowledge()` (line 528)

**Purpose**: Ingest external research content (OOB) into knowledge pipeline

**Request**:
```json
{
  "project_id": "string (required)",
  "content_raw": "string (required)",
  "source_name": "string (required)",
  "source_url": "string (optional)",
  "tags": ["string"] (optional, default ["OOB"])
}
```

**Response** (200):
```json
{
  "reference_id": "uuid",
  "status": "INGESTED"
}
```

---

#### `GET /api/knowledge/references`
**Handler**: `src/orchestrator/api/knowledge.py::list_references()` (line 611)

**Query Params**:
- `project_id`: string (optional, filter by project)

**Response** (200):
```json
[
  {
    "reference_id": "uuid",
    "project_id": "uuid",
    "source_name": "string",
    "source_url": "string" | null,
    "extracted_at": "ISO timestamp",
    "tags": ["string"],
    "status": "INGESTED" | "EXTRACTING" | "EXTRACTED" | "PROMOTED" | "REJECTED"
  }
]
```

---

### 3.4 Job Management

#### `POST /api/jobs/{job_id}/reprocess`
**Handler**: `src/orchestrator/api/jobs.py::reprocess_job()` (line 94)

**Purpose**: Reprocess a job with new knowledge references

**Request**:
```json
{
  "reference_ids": ["uuid"] (required)
}
```

**Response** (202):
```json
{
  "new_job_id": "uuid",
  "parent_job_id": "uuid",
  "status": "QUEUED"
}
```

---

#### `GET /api/jobs/{job_id}/diff`
**Handler**: `src/orchestrator/api/jobs.py::job_diff()` (line 324)

**Purpose**: Compare job versions (parent vs. reprocessed)

**Response** (200):
```json
{
  "parent_job_id": "uuid",
  "child_job_id": "uuid",
  "diff": {
    "triples_added": int,
    "triples_removed": int,
    "triples_modified": int,
    ...
  }
}
```

---

## 4. State Management

### 4.1 Zustand Store: `useProjectStore`
**File**: `src/console/state/useProjectStore.ts`

**State**:
```typescript
{
  activeProjectId: string | null
  activeJobId: string | null
  activePdfUrl: string | null
  activeThreadId: string | null
  projects: ProjectSummary[]
  activeProject: ProjectConfig | null
  isLoading: boolean
  error: string | null
}
```

**Actions**:
- `fetchProjects()`: Fetches all projects via `projectService.listProjects()`
- `setActiveProject(id)`: Fetches full project details via `projectService.getProject(id)`
- `createProject(payload)`: Creates project via `projectService.createProject(payload)`
- `updateRigor(rigor)`: Updates rigor level via `projectService.updateRigor(id, rigor)`
- `setActiveJobContext(jobId, projectId, pdfUrl?, threadId?)`: Sets workbench context
- `clearActiveProject()`: Clears active project
- `clearActiveJob()`: Clears active job context
- `clearError()`: Clears error state

**Persistence**:
- Uses `persist` middleware from Zustand
- Stores `activeProjectId`, `activeJobId`, `activePdfUrl`, `activeThreadId` in localStorage
- Key: `'project-vyasa-active-project'`
- On rehydrate: Fetches full project details if `activeProjectId` exists

---

### 4.2 Service Layer: `projectService`
**File**: `src/console/services/projectService.ts`

**Functions**:
- `createProject(payload: ProjectCreate): Promise<ProjectConfig>`
- `listProjects(): Promise<ProjectSummary[]>`
- `getProject(id: string): Promise<ProjectConfig>`
- `updateRigor(id: string, rigor: "exploratory" | "conservative"): Promise<ProjectConfig>`
- `safeParseError(error: unknown): string`

**API Client**:
- Uses `apiFetch` utility from `@/lib/api`
- Base URL: `/api/proxy/orchestrator` (client-side) or `http://orchestrator:8000` (server-side)
- Handles `ApiError` with details/hints extraction

---

### 4.3 No React Query / SWR
**Observation**: The codebase does NOT use React Query, SWR, or similar data fetching libraries. All data fetching is done via:
- Direct `fetch()` calls in components
- Zustand store actions that call service functions
- Manual state management with `useState` and `useEffect`

**Implications**:
- No automatic caching
- No automatic refetching
- No optimistic updates
- Manual loading/error state management

---

## 5. Data Models & Schemas

### 5.1 TypeScript Types
**File**: `src/console/types/project.ts`

```typescript
interface ProjectCreate {
  title: string
  thesis: string
  research_questions: string[]
  anti_scope?: string[] | null
  target_journal?: string | null
  seed_files?: string[] | null
}

interface ProjectConfig {
  id: string
  title: string
  thesis: string
  research_questions: string[]
  anti_scope?: string[] | null
  target_journal?: string | null
  seed_files: string[]
  created_at: string // ISO format
  rigor_level?: "exploratory" | "conservative"
}

interface ProjectSummary {
  id: string
  title: string
  created_at: string // ISO format
  seed_files?: string[]
}
```

---

### 5.2 Python Models
**File**: `src/project/types.py`

Matches TypeScript types with Pydantic models:
- `ProjectCreate`
- `ProjectConfig`
- `ProjectSummary`

---

### 5.3 Job Status Enum
**File**: `src/orchestrator/state.py`

```python
class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    FINALIZED = "FINALIZED"
    NEEDS_SIGNOFF = "NEEDS_SIGNOFF"
    # Aliases
    PENDING = QUEUED
    PROCESSING = RUNNING
    COMPLETED = SUCCEEDED
```

---

## 6. Data Flow Diagrams

### 6.1 Project Creation Flow

```
User clicks "New Project"
  ↓
Dialog opens (ProjectsPage)
  ↓
User fills form (title, thesis, RQs, anti-scope)
  ↓
handleCreateProject() called
  ↓
useProjectStore.createProject(payload)
  ↓
projectService.createProject(payload)
  ↓
POST /api/proxy/orchestrator/api/projects
  ↓
Orchestrator: POST /api/projects
  ↓
ProjectService.create_project()
  ↓
ArangoDB: Insert into projects collection
  ↓
Returns ProjectConfig
  ↓
Store updates: projects list + activeProject
  ↓
Navigate to /projects/{newProjectId}
```

---

### 6.2 Knowledge Source Ingestion Flow

```
User uploads PDF (FileUploader)
  ↓
POST /api/proxy/orchestrator/ingest/pdf
  (multipart: file + project_id)
  ↓
Orchestrator: POST /ingest/pdf (DEPRECATED)
  ↓
Extract text from PDF (process_pdf)
  ↓
Add filename to project.seed_files
  ↓
Returns markdown preview
  ↓
onUploadComplete(filename) callback
  ↓
UI updates file list
```

**Note**: This is preview-only. For production workflow:

```
User uploads PDF (FileUploader) OR clicks "Start Research"
  ↓
POST /api/proxy/orchestrator/workflow/submit
  (multipart: file + project_id)
  ↓
Orchestrator: POST /workflow/submit
  ↓
Validate project_id exists
  ↓
Fetch ProjectConfig from ArangoDB
  ↓
Extract text from PDF
  ↓
Create workflow job
  ↓
Start background thread (LangGraph workflow)
  ↓
Returns job_id (202 Accepted)
  ↓
UI polls GET /workflow/status/{job_id}
  ↓
When SUCCEEDED, fetch GET /workflow/result/{job_id}
  ↓
Extract artifact_manifest from result
  ↓
Update ManifestBar + ZenManuscriptEditor
```

---

### 6.3 Manifest Update Flow

```
Workflow completes (SUCCEEDED)
  ↓
GET /workflow/result/{job_id}
  ↓
Response contains result.artifact_manifest
  ↓
ManifestBar receives manifest prop
  ↓
Displays metrics (words, tables, citations, tone flags)
  ↓
ZenManuscriptEditor receives blocks from manifest
  ↓
Renders manuscript blocks
```

**Real-time Updates**:
- Workbench listens for `refresh-manifest` window event
- Can be triggered manually or via SSE (if implemented)

---

## 7. Components to Reuse vs. New Components Needed

### 7.1 Components to Reuse

✅ **Keep as-is**:
- `FileUploader` - Works, but should be updated to use `/workflow/submit` instead of deprecated `/ingest/pdf`
- `ManifestBar` - Good, displays manifest metrics
- `ZenManuscriptEditor` - Advanced editor, keep
- `ZenSourceVault` - PDF viewer, keep
- `LiveGraphWorkbench` - Graph visualization, keep
- UI components (`Button`, `Dialog`, `Card`, etc.) - Shadcn/UI, keep

✅ **Keep but enhance**:
- `ProjectsPage` - Add better loading states, error handling
- `ProjectWorkbenchPage` (`/projects/[id]`) - Add "Start Research" workflow submission
- `ProjectWorkbenchPage` (`/projects/[id]/workbench`) - Ensure manifest updates work correctly

---

### 7.2 New Components Needed

❌ **Missing**:
1. **Workflow Submission Component**
   - Currently, "Start Research" button exists but doesn't submit workflow
   - Need component to handle `/workflow/submit` with file upload
   - Should show job status polling

2. **Job Status Polling Hook/Component**
   - Currently, job status is fetched manually in components
   - Need reusable hook for polling `/workflow/status/{jobId}`
   - Should handle SSE if available

3. **Manifest Refresh Mechanism**
   - Currently relies on window events
   - Need proper SSE or polling for real-time manifest updates

4. **Error Boundary for Project Pages**
   - Better error handling for API failures
   - User-friendly error messages

---

## 8. Risks & Unknowns

### 8.1 Missing Endpoints

⚠️ **Unclear**:
- How to trigger workflow submission from UI? The "Start Research" button exists but doesn't call `/workflow/submit`
- Is there an SSE endpoint for real-time job updates? (`/workflow/status/{jobId}` appears to be polling-only)
- How to update project's `seed_files` after upload? Currently done server-side in `/ingest/pdf`, but what about `/workflow/submit`?

---

### 8.2 State Management Gaps

⚠️ **Issues**:
- No caching: Every page load refetches projects
- No optimistic updates: UI doesn't update until API responds
- Manual loading states: Each component manages its own `isLoading`
- No error recovery: Errors persist until manual clear

---

### 8.3 Component Duplication

⚠️ **Concerns**:
- Two workbench pages: `/projects/[id]/workbench` and `/research-workbench`
  - Which one is canonical?
  - Do they serve different purposes?
  - Should one be removed or consolidated?

---

### 8.4 API Inconsistencies

⚠️ **Issues**:
- `/ingest/pdf` is deprecated but still used by `FileUploader`
- Manifest is embedded in workflow result, not a separate endpoint
- Job status vs. workflow status endpoints (`/jobs/{id}/status` vs. `/workflow/status/{id}`)

---

### 8.5 Missing Features

❌ **Not Implemented**:
- Workflow submission from UI (button exists but no handler)
- Real-time manifest updates (relies on window events)
- Project editing (only creation exists)
- Project deletion
- Batch operations (create multiple projects, delete multiple)

---

## 9. File Path Reference

### 9.1 Routes/Pages
- `src/console/app/page.tsx` - Root redirect to `/projects`
- `src/console/app/projects/page.tsx` - Projects Hub
- `src/console/app/projects/[id]/page.tsx` - Project Workbench (3-column)
- `src/console/app/projects/[id]/workbench/page.tsx` - Project Workbench (3-pane)
- `src/console/app/research-workbench/page.tsx` - Research Workbench (zen-focused)

### 9.2 Components
- `src/console/components/FileUploader.tsx`
- `src/console/components/manifest-bar.tsx`
- `src/console/components/ZenManuscriptEditor.tsx`
- `src/console/components/ZenSourceVault.tsx`
- `src/console/components/LiveGraphWorkbench.tsx`

### 9.3 State & Services
- `src/console/state/useProjectStore.ts`
- `src/console/services/projectService.ts`
- `src/console/types/project.ts`

### 9.4 API Handlers
- `src/orchestrator/server.py` - Main Flask app with project/workflow endpoints
- `src/orchestrator/api/knowledge.py` - Knowledge sideload endpoints
- `src/orchestrator/api/jobs.py` - Job reprocessing endpoints

### 9.5 Models
- `src/project/types.py` - Python Pydantic models
- `src/orchestrator/state.py` - JobStatus enum, ResearchState TypedDict

---

## 10. Next Steps (Recommendations)

1. **Consolidate Workbench Pages**: Decide which workbench is canonical (`/projects/[id]/workbench` vs. `/research-workbench`)

2. **Update FileUploader**: Change from deprecated `/ingest/pdf` to `/workflow/submit`

3. **Implement Workflow Submission**: Add handler for "Start Research" button

4. **Add Job Status Polling**: Create reusable hook for polling job status

5. **Improve State Management**: Consider React Query or SWR for caching/refetching

6. **Add Error Boundaries**: Better error handling across project pages

7. **Document API Contracts**: Create OpenAPI/Swagger spec for orchestrator endpoints

---

**End of Inventory**

