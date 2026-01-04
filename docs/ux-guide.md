# Modern Factory UI Guide

Scope: narrative patterns and examples for Vyasa Console. The authoritative checklist lives in `docs/ux-standards.md`. For platform architecture, see `docs/README.md`.

## Applying the standards (examples)
- **Theme tokens in practice:** Use `bg-background text-foreground border-border`; keep SVGs on `currentColor` so they inherit theme changes.
- **Resizable panels:** Show a visible grabber (e.g., 3 stacked dots with `bg-border`) and set `hitAreaMargins={{ coarse: 12, fine: 6 }}` to keep touch targets generous.
- **Navigation state:** `useProjectStore` owns project/job/pdf context; breadcrumbs read from it and Workbench URL params are rewritten so refresh restores state.
- **Tone guardrails:** Status/prose should surface uncertainty (“possible”, “unverified”) and avoid hype; pair UI copy with tone validator/forbidden vocab to enforce neutrality.
- **Performance hygiene:** Memoize heavy panes (graph, manuscript), wrap in `Suspense` with skeletons, and pause polling/animations when tabs are hidden or panels collapsed.
