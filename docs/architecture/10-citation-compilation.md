# Vyasa Citation and Compilation Model

This document defines how Vyasa handles citations while preserving section immutability. It formalizes canonical citation tokens, compiler responsibilities, and the compile-run artifact model.

## 1) Canonical Citation Tokens

- Stored manuscript content uses canonical citation tokens (CCTs), not rendered superscripts.
- CCT format is stable and machine-readable.
- Vyasa canonical chunk citation token: `[[chunk:<chunk_id>]]`
- (Reserved) BibTeX-style citation keys live in `citation_keys` metadata; they are not embedded into prose.
- Numeric superscripts must never appear in stored content because they are:
  - Order-dependent across the full manuscript.
  - A rendering concern, not authorial text.
  - Unstable when sections are added, removed, or reordered.

## 2) Compiler Responsibilities

The compiler is the sole authority for citation rendering and reference list generation.

- Traversal order:
  - Section order strictly follows the Manuscript Blueprint.
  - Citations are numbered in the exact traversal order of their first occurrence.
- Citation numbering:
  - Each CCT is resolved to a canonical evidence anchor.
  - First occurrence receives the next available index; subsequent occurrences reuse the same index.
- Superscript rendering:
  - CCTs are replaced with rendered superscripts in the compiled artifact only.
  - The stored manuscript blocks are not mutated.
- Reference list generation:
  - The compiler produces a reference list keyed by citation indices.
  - The reference list is emitted in the compiled artifact and stored with the compile run.

## 3) Locked Section Guarantees

- Locked sections are immutable in stored prose and citation tokens.
- Visual changes are permitted because they are rendering-level transformations:
  - Superscript numbering can change between compile runs.
  - Layout, typography, and ordering of the reference list can change.
- Safe handling of citation numbering changes:
  - Locked section CCTs remain identical.
  - Only compiled output changes; stored blocks do not.

## 4) Compile Run Artifact

After a compile run, Vyasa stores:

- Compile run metadata:
  - Timestamp, inputs (blueprint version, RetrievalBundles), and checksums.
- Compiled output:
  - Rendered manuscript with superscripts and reference list.
- Citation registry snapshot:
  - Mapping of CCTs to citation indices and evidence anchors.

Compiled output differs from stored blocks in that:
- It contains rendered superscripts and a resolved reference list.
- It may include layout and formatting transformations.
- It never replaces or mutates the stored prose blocks.

Reproducibility guarantees:
- Given the same blueprint, RetrievalBundles, and stored blocks, the compiler must produce identical citation indices and outputs.
- Any change to these inputs triggers a new compile run.

## 5) Example Flow

Scenario: Section written → locked → new evidence added earlier → recompile.

- Initial state:
  - Section A drafted with CCTs: `[[chunk:abc123]]` and `[[chunk:def456]]`.
  - Section A locked.
  - Compile run #1 assigns indices: abc123 = [1], def456 = [2].

- New evidence added earlier:
  - Section 0 is inserted before Section A with `[[chunk:xyz999]]`.
  - Section A remains locked; its CCTs are unchanged.

- Recompile:
  - Compiler traverses Section 0, assigns xyz999 = [1].
  - Section A CCTs are re-numbered in the compiled artifact: abc123 = [2], def456 = [3].
  - Stored Section A content remains identical.

What changes:
- Superscript numbers in the compiled output.
- Reference list ordering and numbering.

What must not change:
- Stored prose blocks for Section A.
- CCTs embedded in Section A.
- Evidence anchors associated with CCTs.
