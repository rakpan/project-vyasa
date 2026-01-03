# Vyasa UX Flow Documentation

**Version:** 1.1  
**Last Updated:** 2025-01-XX

This document describes the user experience flow for Vyasa v1.0 and v1.1, covering the Project Hub, Creation Wizard, Workbench, and power-user features.

---

## 1. Project Hub

### 1.1 Entry Point
- **Route:** `/projects`
- **Default View:** Row List (table format)
- **Sections:**
  - **Active Research:** Projects updated within last 30 days
  - **Archived Insights:** Projects older than 30 days or manually archived

### 1.2 Views & Filters

**View Toggle:**
- Row List (default): Compact table with columns (Title, Status, Last Updated, Health)
- Card View: Visual cards with project metadata and health indicators

**Filter Bar:**
- **Search:** Full-text search across title, thesis, research questions
- **Tags:** Multi-select tag filter
- **Rigor:** Filter by `exploratory` or `conservative`
- **Status:** Filter by `Idle`, `Processing`, `AttentionNeeded`
- **Date Range:** `from` and `to` ISO timestamps

**Persistence:**
- Filters and view preference stored in localStorage
- Restored on page reload

### 1.3 Project Cards/Rows

**Display Fields:**
- Title (clickable → Workbench)
- Status badge (derived from job states)
- Last updated timestamp
- Manuscript health mini-indicator:
  - Word count
  - Claim density
  - Citation count
  - Tone flags (if any)

**Actions:**
- Click title → Navigate to Workbench
- Archive/Unarchive toggle (advanced)

---

## 2. Project Creation Wizard

### 2.1 Entry Point
- **Route:** `/projects/new`
- **Trigger:** "New Project" button in Hub

### 2.2 Three-Step Flow

**Step 1: Intent**
- Project title (required)
- Thesis statement (required)
- Research questions (1+ required)
- Anti-scope (optional, multi-line)
- Target journal (optional)

**Step 2: Seed Corpus**
- Upload PDF files (drag/drop or file picker)
- Per-file ingestion cards with status
- Duplicate detection (SHA256 hash)
- Retry failed ingestions

**Step 3: Configuration**
- Select template (optional):
  - **Exploratory Research:** Default rigor, broad scope
  - **Conservative Review:** Stricter validation, precision-focused
  - **Custom:** Manual configuration
- Rigor level (Exploratory/Conservative)
- Tags (optional, comma-separated)

**Completion:**
- Creates project in ArangoDB
- Redirects to Workbench (`/projects/{id}/workbench`)

---

## 3. Workbench (3-Pane Layout)

### 3.1 Layout Structure

**Pane 1: Source/Evidence (Left, 30%)**
- PDF viewer (`ZenSourceVault`)
- Page navigation
- Evidence highlighting (triggered by claim clicks)
- Source breadcrumbs

**Pane 2: Manuscript (Center, 40%)**
- Editor (`ZenManuscriptEditor`)
- Pinned Manifest Bar (top)
- Block-level editing
- Claim ID links (clickable)
- Citation keys (badges)
- Block actions: Accept/Reject/Notes/Fork

**Pane 3: Knowledge (Right, 30%)**
- Claims list (`KnowledgePane`)
- Status filters (Proposed/Flagged/Accepted/Needs Review)
- RQ filter
- Provenance breadcrumbs
- Confidence badges

**Bottom Panel:**
- Opik Live Feed (collapsible, default collapsed)

### 3.2 Ingestion Hot Area

**Location:** Top of Workbench (spans Pane 1 + Pane 2)

**Components:**
- `SeedCorpusZone`: Drag/drop PDF upload
- Per-file cards:
  - Filename
  - Status pill (Queued/Extracting/Mapping/Verifying/Completed/Failed)
  - Progress bar
  - Actions: View reason (if failed), Retry, Remove

**Global Status Banner:**
- Visible when any ingestion/job is active
- Shows current phase summary
- Optional "View details" link

**State Feed:**
- Polling via `GET /api/projects/{project_id}/ingest/{ingestion_id}/status`
- Updates: state, progress_pct, error_message, first_glance, confidence_badge

---

## 4. Knowledge Pane (Claims)

### 4.1 Claim List View

**Each Claim Item Shows:**
- Short claim text (truncated)
- Status badge (Proposed/Flagged/Accepted/Needs Review)
- Linked RQ badge
- Confidence badge (High/Medium/Low)
- Provenance breadcrumb: "Proposed by: Cartographer → Verified by: Brain"
- Flags indicator (if any)

**Filters:**
- Status dropdown (multi-select)
- RQ dropdown (single-select)
- Status counts displayed

### 4.2 Claim Detail Drawer

**Trigger:** Click claim item

**Content:**
- Full claim text
- Status, confidence, linked RQ
- Provenance breadcrumb
- Sources list:
  - doc_hash
  - page number
  - snippet
- Citations
- Evidence text
- Conflict data (if flagged)

---

## 5. Conflict Resolution

### 5.1 Conflict Detection

**Backend:**
- Critic flags conflicting claims
- Conflict report stored in ArangoDB
- Deterministic explanation generated (no LLM)

**Frontend:**
- Flagged claims show conflict badge
- "Why" tooltip on badge shows explanation

### 5.2 Side-by-Side Comparison

**When User Opens Conflicted Claim:**
- Center pane splits:
  - **Left:** Source A excerpt + page ref
  - **Right:** Source B excerpt + page ref
- `ConflictCompareView` component
- Deterministic explanation displayed

**Conflict Payload:**
```json
{
  "conflict": {
    "source_a": { "doc_hash": "...", "page": 5, "excerpt": "..." },
    "source_b": { "doc_hash": "...", "page": 12, "excerpt": "..." },
    "explanation": "Source A asserts X, while Source B contradicts this on page Y."
  }
}
```

---

## 6. Manuscript Context Anchor

### 6.1 Cross-Pane Communication

**Evidence Context:**
- React Context (`EvidenceContext`) manages highlight state
- Coordinates between Manuscript and Source panes

**Behavior:**
- Clicking a `claim_id` link in Manuscript:
  1. Fetches `source_pointer` from claim data
  2. Calls `setHighlight(coordinates)` from context
  3. Source pane scrolls to page
  4. Highlights exact bbox area
  5. No modal, no navigation

**Implementation:**
- `ClaimIdLink` component wraps claim IDs
- `ZenSourceVault` consumes `useEvidence` hook
- Uses PDF.js `highlightPluginInstance.jumpToHighlightArea`

---

## 7. Manuscript Forking

### 7.1 Fork Flow

**Trigger:**
- "Fork" action on a manuscript block (advanced)

**Steps:**
1. User clicks "Fork" → `ForkDialog` opens
2. Select rigor level (Exploratory/Conservative)
3. System calls `POST /api/projects/{project_id}/blocks/{block_id}/fork`
4. Synthesizer generates alternate block content
5. Forked block displayed as read-only preview
6. User can:
   - **Accept Fork:** Creates new block version
   - **Discard:** Closes preview

**Original Block:**
- Remains unchanged until fork acceptance
- No mutation until explicit user action

---

## 8. Manuscript Health & Rigor Toggle

### 8.1 Manifest Bar

**Location:** Pinned to top of Manuscript pane

**Metrics:**
- Word count
- Table count
- Neutrality score (0-100%)
- Tone flags count
- Claim density (per 100 words)
- Citation count

**Actions:**
- Download Manifest (JSON)

### 8.2 Rigor Badge

**Location:** Right side of Manifest Bar

**Display:**
- Current rigor level (Exploratory/Conservative)
- Clickable badge

**Modal (`RigorToggleModal`):**
- Current rigor display
- Radio group for selection
- Explanations for each level
- **Warning:** "This change will only affect future jobs"
- Save/Cancel actions

**Backend:**
- `PATCH /api/projects/{project_id}/rigor`
- Updates `ProjectConfig.rigor_level`
- Orchestrator injects into job `initial_state` at creation

---

## 9. Opik Live Feed Panel

### 9.1 Panel Behavior

**Location:** Bottom of Workbench (collapsible)

**Default State:** Collapsed

**When Expanded:**
- List of `node_execution` events:
  - Node name
  - Duration (ms)
  - Status (Success/Failed/Running)
  - Timestamp
- Auto-scrolls to bottom on new events
- Click event → Detail drawer (optional)

**Data Source:**
- `GET /api/jobs/{job_id}/events`
- Polling interval: 2 seconds
- Filters `event_type: "node_execution"`

### 9.2 Empty States

**Opik Disabled:**
- Shows: "Enable Opik to view traces"
- Link to documentation

**No Events:**
- Shows: "No execution events yet"
- Appears when job is queued or just started

---

## 10. Screenshots Placeholders

### 10.1 Project Hub
- **Placeholder:** Screenshot of Hub with Active/Archived sections, filter bar, and Row List view
- **Placeholder:** Screenshot of Card View with project cards and health indicators

### 10.2 Creation Wizard
- **Placeholder:** Screenshot of Step 1 (Intent) form
- **Placeholder:** Screenshot of Step 2 (Seed Corpus) with drag/drop zone and ingestion cards
- **Placeholder:** Screenshot of Step 3 (Configuration) with template selector

### 10.3 Workbench
- **Placeholder:** Screenshot of 3-pane layout with PDF viewer, manuscript editor, and knowledge pane
- **Placeholder:** Screenshot of Manifest Bar with metrics and rigor badge
- **Placeholder:** Screenshot of Ingestion Hot Area with active jobs

### 10.4 Knowledge Pane
- **Placeholder:** Screenshot of Claims list with filters and status badges
- **Placeholder:** Screenshot of Claim Detail Drawer with sources and citations

### 10.5 Conflict Resolution
- **Placeholder:** Screenshot of side-by-side conflict comparison view
- **Placeholder:** Screenshot of "Why" tooltip on conflict badge

### 10.6 Context Anchor
- **Placeholder:** Screenshot of claim ID link in manuscript
- **Placeholder:** Screenshot of highlighted evidence in PDF viewer

### 10.7 Manuscript Forking
- **Placeholder:** Screenshot of Fork Dialog with rigor selection
- **Placeholder:** Screenshot of forked block preview with Accept/Discard actions

### 10.8 Rigor Toggle
- **Placeholder:** Screenshot of Rigor Toggle Modal with explanations and warning

### 10.9 Opik Live Feed
- **Placeholder:** Screenshot of expanded Opik panel with node execution events
- **Placeholder:** Screenshot of event detail drawer

---

## 11. Navigation Flow

```
/projects (Hub)
  ├─> /projects/new (Wizard)
  │     └─> /projects/{id}/workbench
  │
  └─> /projects/{id}/workbench (Workbench)
        ├─> Click claim → Detail drawer
        ├─> Click claim_id → Highlight evidence
        ├─> Click Fork → Fork dialog
        ├─> Click rigor badge → Rigor modal
        └─> Expand Opik panel → Live feed
```

---

## 12. Key UX Principles

1. **Project-First:** All actions require a project context
2. **Future-Only Changes:** Rigor updates affect future jobs only
3. **No Navigation on Context:** Evidence highlighting stays in place
4. **Deterministic Explanations:** Conflicts explained without LLM calls
5. **Progressive Disclosure:** Advanced features (Fork, Opik) are opt-in
6. **State Persistence:** Filters, views, and preferences survive reloads
7. **Real-Time Updates:** Ingestion status and Opik events poll actively

---

## 13. API Endpoints Reference

**Project Management:**
- `GET /api/projects?query=&tags=&rigor=&status=&from=&to=&view=hub`
- `POST /api/projects` (create)
- `PATCH /api/projects/{project_id}/rigor`

**Ingestion:**
- `POST /api/projects/{project_id}/ingest/check-duplicate`
- `GET /api/projects/{project_id}/ingest/{ingestion_id}/status`
- `POST /api/projects/{project_id}/ingest/{ingestion_id}/retry`

**Workflow:**
- `POST /workflow/submit`
- `GET /workflow/result/{job_id}`
- `GET /api/jobs/{job_id}/events`

**Manuscript:**
- `POST /api/projects/{project_id}/blocks/{block_id}/fork`
- `POST /api/projects/{project_id}/blocks/{block_id}/accept-fork`

---

**End of Document**

