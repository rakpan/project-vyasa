# Context Packing (opt-in, single pipeline)

This pass adds a layered prompt composition for the extraction pipeline only, behind a feature flag.

## Layers
- **Corpus/Document memory**: structured summaries + metadata + provenance pointers (`corpus_memory` in state).
- **Evidence window**: top-K retrieved chunks with citations (`evidence_chunks` in state or stubbed).
- **Working state**: schema/constraints/conflicts (built from current state).

When enabled (`ENABLE_CONTEXT_PACKING_EXTRACT=true`), the Cartographer user prompt is augmented with these layers. Defaults still use the original prompt when the flag is off.

## Implementation
- Code: `src/orchestrator/context_packer.py`
  - `build_extraction_layers(corpus_memory, evidence_chunks, working_state)` to compose sections.
  - `stub_retrieve_evidence` placeholder (returns empty list).
- Hooked into: `src/orchestrator/nodes.py` (cartographer_node). Feature flag: `ENABLE_CONTEXT_PACKING_EXTRACT`.
- Provenance: evidence chunks include `source_id`/`doc_id` and optional citation tags; user prompt includes them so outputs can carry citations forward.

## Retrieval
- Minimal/stubbed for now: no new dependencies added; callers may populate `state["evidence_chunks"]` to inject retrieved context.

## Scope
- Only applies to the extraction pipeline.
- No changes to other nodes or global RAG layers. Defaults remain unchanged when the flag is disabled.
