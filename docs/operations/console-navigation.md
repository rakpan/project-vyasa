# Console Navigation & Workbench Runbook

## Canonical Entry
- Root (`/`) must redirect to `/projects`. Treat `/projects` as the landing/home for the Console.

## Primary Journey
1. Projects list (`/projects`)  
   - Create/see projects.  
   - If a recent job exists, show “Resume” / “View Workbench” CTA with the latest `jobId`, `projectId`, and `pdfUrl`.
2. Project detail (`/projects/[id]`)  
   - Show recent jobs with “Open Workbench” links.  
   - Empty state when no jobs exist.
3. Workbench (`/research-workbench`)  
   - Requires `jobId` and `projectId` query params.  
   - If missing, redirect to `/projects` and surface a toast/banner explaining the requirement.  
   - `pdfUrl` is optional; if missing, render a 2-panel layout and skip PDF viewer.

## Sidebar Behavior
- Sidebar links must never be dead ends.  
- Workbench link is context-aware:  
  - If no active job, redirect to `/projects` with a toast “Select a project/job to open Workbench.”  
  - When an active job exists, link directly to `/research-workbench?jobId=...&projectId=...&pdfUrl=...` (if available).  
- Active project/job should be indicated (badge or highlight) in the sidebar.

## Workbench Layout Rules
- With `pdfUrl`: render three panels with sizes summing to 100% (e.g., `[40, 30, 30]`).  
- Without `pdfUrl`: render two panels `[50, 50]`.  
- Guards must be single-pass (no duplicate checks) for missing params.

## Resume Behavior
- Projects list and Project detail should surface the latest job as a “Resume” action linking to Workbench with correct params.  
- Reprocess flows must preserve `pdfUrl`; otherwise Workbench will guard and redirect.

## Source of Truth / APIs
- Latest job per project endpoint feeds “Resume” CTAs.  
- Workbench expects: `jobId`, `projectId`, optional `pdfUrl`.

## Testing Guidance
- Add navigation tests (redirect `/` → `/projects`; sidebar Workbench guard; Workbench param guard).  
- Add Workbench layout tests (panel counts/sizes with/without `pdfUrl`).  
- Add resume flow tests (projects list and project detail CTAs).  
- Mock all API calls; tests must run offline.
