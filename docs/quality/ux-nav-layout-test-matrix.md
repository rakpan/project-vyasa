# Vyasa Console Navigation & Layout — Requirements Matrix

| Requirement ID | Requirement | Code Locations | Documentation Location | Unit Test(s) | Notes / Edge cases |
| --- | --- | --- | --- | --- | --- |
| NAV-001 | `/` redirects to `/projects` (canonical entry) | src/console/app/page.tsx | MISSING | MISSING | Ensure redirect works server/client; guard SSR vs CSR |
| NAV-002 | Sidebar links resolve and avoid dead ends; Workbench link context-aware | src/console/components/app-sidebar.tsx, src/console/state/useProjectStore.ts | MISSING | MISSING | Workbench link should disable/redirect if no active job |
| NAV-003 | Active project/job indicator visible in sidebar | src/console/components/app-sidebar.tsx | MISSING | MISSING | Needs consistent icon/badge |
| FLOW-010 | Projects list shows Resume/View Workbench when recent job exists | src/console/app/projects/page.tsx, src/console/components/JobStatusCard.tsx | MISSING | MISSING | Latest job lookup needs mocked API |
| FLOW-011 | Project detail shows Recent Jobs with Open Workbench links | src/console/app/projects/[id]/page.tsx | MISSING | MISSING | Empty-state when no jobs |
| FLOW-012 | Reprocess navigation includes pdfUrl so Workbench loads | src/console/components/JobStatusCard.tsx | MISSING | MISSING | Current guard requires pdfUrl; ensure preserved from job metadata |
| WB-020 | Workbench guards: redirect/toast when jobId/projectId missing | src/console/app/research-workbench/page.tsx | MISSING | MISSING | Single guard (no duplicate checks) |
| WB-021 | Workbench handles missing pdfUrl (conditional rendering) | src/console/app/research-workbench/page.tsx | MISSING | MISSING | Two-panel layout [50/50] when pdfUrl absent |
| WB-022 | Panel sizing totals 100% (e.g., 40/30/30 with pdfUrl) | src/console/app/research-workbench/page.tsx | MISSING | MISSING | Verify default sizes and responsive breakpoints |
| NAV-030 | Resume flow sets Workbench link parameters correctly | src/console/state/useProjectStore.ts, src/console/components/JobStatusCard.tsx | MISSING | MISSING | jobId/projectId/pdfUrl propagated |
| DOC-040 | Docs describe canonical entry and Projects→Job→Workbench flow | docs/runbooks/console-navigation.md | NEW (this doc) | N/A | Update when behavior changes |
| THEME-050 | globals.css is single source; no duplicate theme tokens | src/console/app/globals.css (and imports) | MISSING | Optional lint/test MISSING | Add lint/grep guard if theme touched |

## Coverage Summary
- Covered: Requirements captured in matrix with code/documentation/test gaps identified.
- Not covered: Automated unit tests and some documentation still need implementation; no existing test harness in console package to execute proposed tests. Add Jest/Vitest + React Testing Library baseline before adding tests above.
