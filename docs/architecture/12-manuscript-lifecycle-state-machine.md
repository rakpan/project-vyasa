# Vyasa Manuscript Lifecycle State Machine

This document defines the authoritative lifecycle for manuscript sections and the manuscript as a whole. It is written to be directly convertible into state diagrams and to guide implementation and governance.

## 1) Section Lifecycle States

### NotStarted
- Allowed actions:
  - Create blueprint section metadata.
  - Link research questions and evidence clusters.
  - Add analytical notes (Draft Notes).
- Data may change:
  - Blueprint metadata (heading, depth intent, visual anchors).
  - Analytical Notes (Draft state).
- Forbidden:
  - Compilation or locking.
  - Citation registry creation.

### Draft
- Allowed actions:
  - Editor drafting and revision.
  - LLM-assisted drafting using Packet A (Evidence) and Packet B (Analytical Notes).
  - Add or modify Draft Notes.
- Data may change:
  - Manuscript Blocks for the section.
  - Draft Analytical Notes.
- Forbidden:
  - Locking without review.
  - Using Analytical Notes as citeable evidence.

### UnderReview
- Allowed actions:
  - Critic review and human review.
  - Review comment creation and resolution.
  - Evidence cross-check against Packet A.
- Data may change:
  - Review Comments (Open/Addressed/Deferred).
  - Draft Manuscript Blocks for revisions.
- Forbidden:
  - Section lock until review conditions are satisfied.
  - Altering the RetrievalBundle without re-review.

### Revised
- Allowed actions:
  - Editor updates in response to review.
  - Re-run LLM drafting with updated prompts.
- Data may change:
  - Manuscript Blocks.
  - Review Comments status (Addressed or Deferred).
- Forbidden:
  - Locking without validation that all required comments are resolved.

### Ready
- Allowed actions:
  - Final validation checks (word budget, citation integrity, VisualPlaceholder completeness).
  - Compilation preview (deterministic only).
- Data may change:
  - Citation registry generation for the section.
  - VisualPlaceholder generation (deterministic).
- Forbidden:
  - LLM drafting or mutation.
  - Changing core prose without returning to Draft/Revised.

### Locked
- Allowed actions:
  - Deterministic compilation and rendering.
  - Citation superscript rendering and numbering.
- Data may change:
  - Rendered layout only (formatting without semantic change).
- Forbidden:
  - Any mutation of section prose.
  - Any modification to Evidence Packet A reference set.
  - Any change to VisualPlaceholders.

## 2) Analytical Note Lifecycle

### Draft Note
- Promotion conditions:
  - Critic verifies that note content is supported by Evidence Packet A.
  - Note does not introduce new facts outside evidence.
- Allowed actions:
  - Edit text, tags, and linked RQs.
- Forbidden:
  - Citation or factual attribution.

### Manuscript Note
- Allowed actions:
  - Influence framing, analogies, and pedagogy.
- Forbidden:
  - Serving as evidence or citation source.
- Automatic reversion rules:
  - If RetrievalBundle changes for the linked section.
  - If blueprint metadata changes materially (linked RQs, depth intent, visual anchors).
  - If section is unlocked and recompiled.
  - Reversion state: Reverted Draft.

### Reverted Draft
- Allowed actions:
  - Edit and re-qualify against the latest Evidence Packet A.
- Forbidden:
  - Use in Manuscript Note capacity until re-promoted.

Critic’s role:
- Initiates promotions by validating evidence alignment.
- Triggers reversion when evidence drift is detected.
- Flags notes that introduce unsupported facts.

## 3) Review Comment Lifecycle

### Open
- Created by Critic or human reviewer.
- Must be addressed or deferred before Ready.

### Addressed
- Comment resolved by revisions; evidence check passes.

### Deferred
- Explicitly deferred with rationale; may block locking based on policy.

### Locked
- On section lock, all open comments are either Addressed or Deferred.
- Locked comments are immutable and attached to the compile run.

## 4) Compiler vs Editor Separation

- Transitions involving LLM calls:
  - Draft creation and Draft -> UnderReview preparation.
  - Revised state changes that require new prose or re-synthesis.
- Deterministic compiler actions:
  - Ready -> Locked (validation, citation registry generation, VisualPlaceholder determinism).
  - Locked -> Compile (layout and rendering only).
- Why compilation must never invoke the LLM:
  - Determinism, auditability, and immutability of locked content.
  - Prevents model drift from mutating certified evidence compliance.

## 5) Failure Modes and Safeguards

- Evidence deletion after lock:
  - Safeguard: block deletion; if unavoidable, force section unlock and invalidate compile run.
- Word budget overflow with locked sections:
  - Safeguard: compilation fails; section must be unlocked and revised.
- Stale perspectives (Analytical Notes):
  - Safeguard: auto-revert to Reverted Draft when RetrievalBundle changes.
- Missing predicates for visuals:
  - Safeguard: block Ready -> Locked; require VisualPlaceholder completeness.

## Manuscript-Level Lifecycle (Informative)

- Manuscript progresses by aggregating section states:
  - NotStarted: no sections beyond NotStarted.
  - Draft: at least one section in Draft or UnderReview.
  - Review: at least one section in UnderReview or Revised.
  - Ready: all sections in Ready.
  - Locked: all sections Locked; compilation available.
