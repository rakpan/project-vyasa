# UX Standards – Modern Factory

## Light Theme Tokens
- Use Tailwind token classes only: `bg-background`, `text-foreground`, `border-border`, `bg-muted`, `text-primary`.
- No hardcoded hex or legacy brand utilities; SVG/Canvas should inherit `currentColor` or `rgb(var(--primary))`.

## Navigation
- Dual-sidebar layout: slim global rail (Projects/Knowledge/Observatory/Settings) + project context sub-nav.
- Breadcrumbs consume `useProjectStore` state (project/job/pdf) and render `Projects > {ProjectName} > {ActiveContext}` as the single source of truth.

## Resizable Workbench
- All `PanelResizeHandle` components must set `hitAreaMargins={{ coarse: 12, fine: 6 }}`.
- Provide a visible grabber on hover (e.g., 3 stacked dots with `bg-border`) to signal the resize affordance.

## Tone & Anti-Sensation
- Agent-generated prose must avoid hyperbole; enforce with `deploy/forbidden_vocab.yaml` and the tone validator node.
- Replace sensational terms (“revolutionary”, etc.) with neutral equivalents; surface uncertainty explicitly.

## Accessibility & Performance
- Pause polling/streams when the tab is hidden; use LangGraph v2 event stream for heartbeat (no polling).
- Memoize heavy panes (graph, manuscript), wrap in `Suspense` with skeletons to prevent thrash.
