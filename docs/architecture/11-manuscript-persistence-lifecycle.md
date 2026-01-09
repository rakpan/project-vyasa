# Vyasa Manuscript Persistence and Lifecycle

This document is the authoritative reference for how manuscripts are prepared, reviewed, refined, locked, and compiled in Vyasa. It defines the data ownership model across ArangoDB and Qdrant and establishes invariants that all contributors must follow.

## 1) Design Principle

- ArangoDB is the system of record for manuscript truth and governance.
- Qdrant is a retrieval accelerator, not a source of truth.

## 2) Data Responsibility Matrix

| Artifact | Stored In | Why | Mutability | Versioning Rules |
| --- | --- | --- | --- | --- |
| Primary Source chunks | ArangoDB (metadata) + Qdrant (vectors) | ArangoDB owns chunk identity, provenance, and governance; Qdrant accelerates retrieval | Chunk metadata is mutable only via ingestion pipeline | Re-ingestion creates new chunk versions; old chunks remain addressable or explicitly deprecated |
| Chunk text | ArangoDB | Text is canonical evidence and must be auditable | Immutable after ingestion; updates require re-ingestion | New version required if text changes |
| Chunk embeddings | Qdrant | Fast vector search | Mutable only via re-embedding | Embedding version tied to embedder model ID |
| Analytical Notes | ArangoDB | Governed, non-citeable artifacts with lifecycle state | Mutable until promoted or locked by section | Versioned on edit; promotion creates a new state revision |
| Note promotion state | ArangoDB | Governance decision that must be auditable | Immutable once recorded for a given compile run | Promotion events are append-only; demotions create new events |
| Manuscript Blueprint | ArangoDB | Governs section-by-section synthesis | Mutable until a section is locked | Blueprint revisions are versioned; locks reference a specific blueprint version |
| Manuscript Blocks (per section) | ArangoDB | Canonical draft and compiled text | Mutable until section lock | Each edit creates a new block revision; compile runs reference revision IDs |
| Review Comments | ArangoDB | Human/critic feedback for governance | Mutable (author may edit) | Comments are versioned for audit |
| Section Locks | ArangoDB | Governance gate for immutability | Immutable; unlock creates a new lock state | Lock records are append-only with timestamps |
| RetrievalBundles | ArangoDB | Reproducible evidence selection artifact | Immutable once persisted | New bundle per query/section; bundles are never overwritten |
| VisualPlaceholders | ArangoDB | Deterministic placeholders tied to section and evidence | Immutable once section locked | New placeholder version only on unlock + recompilation |
| Citation Registry | ArangoDB | Canonical mapping from citation tokens to evidence | Mutable only via compile run | Registry is regenerated per compile run; tokens are stable within a run |
| Compile Runs (final artifacts) | ArangoDB (metadata) + object store/file system (rendered) | Governance and audit trail | Immutable | Each compile run is append-only with inputs, outputs, and checksums |

## 3) Persistence Guarantees

- “Locked” at storage level means:
  - The section’s manuscript blocks, associated VisualPlaceholders, and citation registry entries are immutable.
  - Any change requires explicit unlock, which creates a new lock record and invalidates the prior compiled artifact for that section.
- What cannot change without explicit unlock:
  - Locked section text.
  - Evidence Packet A reference set used for citations in that section.
  - VisualPlaceholders tied to that section.
- What may change without touching locked text:
  - Citation rendering (e.g., superscript numbering) as long as the underlying citation registry tokens remain unchanged.
  - Global formatting and layout of the compiled manuscript artifact.

## 4) Anti-patterns (Explicitly Forbidden)

- Storing manuscript text in Qdrant.
- Treating Analytical Notes as citeable evidence.
- Letting LLMs mutate locked content.
- Using retrieval indices as authoritative state.

## Lifecycle Overview (Informative)

- Ingest: Primary Sources are chunked; text and metadata are stored in ArangoDB, embeddings in Qdrant.
- Draft: Manuscript Blocks are authored in the editor; Analytical Notes may influence style only.
- Review: Critic/human review updates Review Comments and promotion states.
- Lock: Section locks are written to ArangoDB, binding blueprint version, RetrievalBundle, and citation registry.
- Compile: Compiler assembles the manuscript from locked sections and produces the final artifact; compile run metadata is persisted.

## Enforcement Summary

- ArangoDB owns all governance and truth-bearing records.
- Qdrant is a performance layer only; it never defines truth.
- Any deviation from these rules is a system integrity failure.
