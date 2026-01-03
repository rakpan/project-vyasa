# UX Standards – Modern Factory

## Light Theme Tokens
- Use Tailwind token classes only: `bg-background`, `text-foreground`, `border-border`, `bg-muted`, `text-primary`.
- No hardcoded hex or legacy brand utilities; SVG/Canvas should inherit `currentColor` or `rgb(var(--primary))`.
- `globals.css` is single source; no duplicate theme tokens. Add lint/grep guard if theme touched.

## Navigation

### Dual-Sidebar Layout
- Slim global rail (Projects/Knowledge/Observatory/Settings) + project context sub-nav.
- Breadcrumbs consume `useProjectStore` state (project/job/pdf) and render `Projects > {ProjectName} > {ActiveContext}` as the single source of truth.

### Navigation Flow
- `/` redirects to `/projects` (canonical entry)
- Sidebar links resolve and avoid dead ends; Workbench link context-aware
- Active project/job indicator visible in sidebar
- Projects → Workbench flow, required params, interrupts overlay
- Sidebar/footer summaries and health indicators

### Navigation Requirements Matrix

| Requirement ID | Requirement | Code Locations | Unit Test(s) | Notes / Edge cases |
| --- | --- | --- | --- | --- |
| NAV-001 | `/` redirects to `/projects` (canonical entry) | src/console/app/page.tsx | MISSING | Ensure redirect works server/client; guard SSR vs CSR |
| NAV-002 | Sidebar links resolve and avoid dead ends; Workbench link context-aware | src/console/components/app-sidebar.tsx, src/console/state/useProjectStore.ts | MISSING | Workbench link should disable/redirect if no active job |
| NAV-003 | Active project/job indicator visible in sidebar | src/console/components/app-sidebar.tsx | MISSING | Needs consistent icon/badge |
| FLOW-010 | Projects list shows Resume/View Workbench when recent job exists | src/console/app/projects/page.tsx, src/console/components/JobStatusCard.tsx | MISSING | Latest job lookup needs mocked API |
| FLOW-011 | Project detail shows Recent Jobs with Open Workbench links | src/console/app/projects/[id]/page.tsx | MISSING | Empty-state when no jobs |
| FLOW-012 | Reprocess navigation includes pdfUrl so Workbench loads | src/console/components/JobStatusCard.tsx | MISSING | Current guard requires pdfUrl; ensure preserved from job metadata |
| WB-020 | Workbench guards: redirect/toast when jobId/projectId missing | src/console/app/research-workbench/page.tsx | MISSING | Single guard (no duplicate checks) |
| WB-021 | Workbench handles missing pdfUrl (conditional rendering) | src/console/app/research-workbench/page.tsx | MISSING | Two-panel layout [50/50] when pdfUrl absent |
| WB-022 | Panel sizing totals 100% (e.g., 40/30/30 with pdfUrl) | src/console/app/research-workbench/page.tsx | MISSING | Verify default sizes and responsive breakpoints |
| NAV-030 | Resume flow sets Workbench link parameters correctly | src/console/state/useProjectStore.ts, src/console/components/JobStatusCard.tsx | MISSING | jobId/projectId/pdfUrl propagated |

## Layout & Theme
- High-density light theme, tokenized colors, manifest/tone/precision surfacing

## Resizable Workbench
- All `PanelResizeHandle` components must set `hitAreaMargins={{ coarse: 12, fine: 6 }}`.
- Provide a visible grabber on hover (e.g., 3 stacked dots with `bg-border`) to signal the resize affordance.

## Interaction & QA
- Resize handles, accessibility, breadcrumbs, hover states
- Test matrix for navigation/state restoration

## Tone & Anti-Sensation
- Agent-generated prose must avoid hyperbole; enforce with `deploy/forbidden_vocab.yaml` and the tone validator node.
- Replace sensational terms ("revolutionary", etc.) with neutral equivalents; surface uncertainty explicitly.

## Accessibility & Performance
- Pause polling/streams when the tab is hidden; use LangGraph v2 event stream for heartbeat (no polling).
- Memoize heavy panes (graph, manuscript), wrap in `Suspense` with skeletons to prevent thrash.

## Coverage Summary
- Covered: Requirements captured in matrix with code/documentation/test gaps identified.
- Not covered: Automated unit tests and some documentation still need implementation; no existing test harness in console package to execute proposed tests. Add Jest/Vitest + React Testing Library baseline before adding tests above.
