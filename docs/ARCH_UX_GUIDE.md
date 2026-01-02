# Modern Factory UI Standards

## Theme Tokens
- Use Tailwind tokens only: `bg-background`, `text-foreground`, `border-border`, `bg-muted`, `text-primary`. No hardcoded hex or legacy brand classes.
- SVG/Canvas must inherit current color or CSS vars (`rgb(var(--primary))`), never fixed hex.

## Resizable Panels
- All `PanelResizeHandle` instances must include `hitAreaMargins={{ coarse: 12, fine: 6 }}` for touch/trackpad accessibility.
- Provide a visible grabber on hover (e.g., 3-dot stack with `bg-border`) to signal affordance.

## Navigation & Breadcrumbs
- `useProjectStore` is the single source for project/job/pdf context.
- Breadcrumbs render `Projects > {ProjectName} > {ActiveContext}` and update immediately on tab switches; never re-derive from URL alone.
- When setting a project/job, rewrite the workbench URL params so refresh restores state.

## Anti-Sensation Rule
- Agent-generated prose must avoid hyperbole or fabricated certainty. Summaries and statuses should be factual, with uncertainty surfaced explicitly (e.g., “possible”, “unverified”) and without marketing language.

## Component Hygiene
- Memoize heavy panes (graph, manuscript) and wrap in `Suspense` with skeletons to prevent thrash during hydration/resizes.
- Pause polling/animations when tabs are hidden or panels collapsed to reduce flicker and CPU use.*** End Patch***" json explanation to=functions.apply_patch code sure? Need proper patch syntax. Use no quotes. Let's redo. remove json. Use apply_patch format. Let's send. Apologies. We'll re-run.႕
