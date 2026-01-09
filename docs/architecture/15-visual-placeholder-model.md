# Vyasa Visual Placeholder Model

This document defines how tables and figures are planned, constrained, and generated without hallucination. It establishes the VisualPlaceholder object, its lifecycle, compiler rules, and the external rendering workflow.

## 1) VisualPlaceholder Object

A VisualPlaceholder is a deterministic, evidence-bound placeholder for a table or figure. It is not the rendered visual; it is the contract for what a visual may contain.

### Required Fields

- placeholder_id: unique identifier
- project_id
- section_id
- kind: table | figure | diagram
- title: human-readable label
- evidence_cluster_ids: list of evidence cluster identifiers
- predicate_filters: list of required triple predicates (mandatory)
- schema: declared columns or axes (for tables/figures)
- status: Planned | Drafted | Finalized | Locked
- created_at
- version

### Mandatory Triple Predicate Filters

- predicate_filters must be defined for every VisualPlaceholder.
- The compiler may only populate values derived from triples whose predicates match these filters.
- If no matching predicates exist, the placeholder remains empty and is flagged.

### Relationship to Evidence Clusters

- Each placeholder references one or more evidence clusters.
- Clusters define the eligible triple set.
- Predicate filters further constrain what can be extracted or summarized.

## 2) Why Predicate Filters Are Mandatory

- Prevents column hallucination:
  - Tables cannot invent columns beyond the declared schema and predicate filters.
- Prevents overreach:
  - Figures cannot include metrics or relationships not grounded in filtered evidence.
- Ensures reproducibility:
  - Given the same evidence clusters and filters, placeholders resolve deterministically.

## 3) Placeholder Lifecycle

### Planned
- Placeholder defined with fields and filters.
- No data binding yet.
- Allowed: edits to schema, filters, and evidence clusters.

### Drafted
- Data binding attempted against eligible triples.
- Draft values may be incomplete.
- Allowed: refine filters, adjust schema, re-run binding.

### Finalized
- Data binding successful with no missing required fields.
- Ready for section compilation.
- Allowed: cosmetic metadata changes only (title, caption text).

### Locked
- Placeholder bound and immutable for the section.
- Any change requires explicit section unlock and regeneration.

## 4) Compiler Rules

- When placeholders are filled:
  - Only when predicate filters resolve against the referenced evidence clusters.
  - Only when required schema fields can be populated.
- When placeholders remain empty:
  - If required predicates are missing or evidence clusters are empty.
  - If schema cannot be satisfied.
- How data gaps are surfaced:
  - Compiler emits explicit “missing predicate” or “missing evidence” flags.
  - Section cannot be locked if required placeholders are unresolved.

## 5) External Rendering Workflow

Vyasa exports a deterministic payload for external rendering tools (tables, diagrams, plots). The payload includes:

- VisualPlaceholder metadata (id, title, kind)
- Evidence cluster references
- Predicate filters applied
- Resolved data rows or series (if Drafted/Finalized)
- Required schema fields and units

Vyasa never attempts to render automatically:
- Complex charts or diagrams that require design choices beyond the schema.
- Visuals that require inference or synthesis beyond the filtered triples.
- Any graphic that would require introducing new data not present in Evidence Packet A.

## Enforcement Summary

- Visuals are evidence-driven, predicate-filtered, and deterministic.
- Placeholders are contracts, not drawings.
- Any missing data results in an explicit, surfaced gap—not a hallucinated fill.
