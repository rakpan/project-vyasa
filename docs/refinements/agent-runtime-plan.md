# Vyasa Agent Runtime: Planning Notes (Cartographer, Critic, Lead Counsel)

Purpose: convert conceptual personas into governed production agents, aligned with current runtime and planned optimizations. Scope is planning-only; no implementation changes implied.

## 0) Goals and non-goals
- Goals: clarify execution engine, observability, retrieval/rerank/Evidence Pack contract, and section synthesis protocols; define near-term migration steps (bounded parallelism, KV reuse, rerank defaults).
- Non-goals: new APIs, code refactors, or schema changes in this document.

## 1) Execution engine (now → next)
- Today: LangGraph orchestrates branching/retries; agents call SGLang-served Nemotron-49B (HTTP: `/v1/chat/completions`, `/generate`, `/v1/vision` when enabled). Qwen2-VL is optional under `VISION_ENABLED`.
- Structured decoding: JSON/regex FSM enforces Compilation Contract outputs (triples, manifests, RetrievalBundles, structured Markdown sections).
- Planned optimization: migrate selected flows (Cartographer extraction) to SGLang programs to leverage `.fork()/.join()` and radix attention reuse explicitly.
- KV reuse (RadixAttention): shared prefixes (system + contract + doc anchor + TOC map + Evidence Pack) cached once; measure reuse benefits via telemetry instead of assuming gains.

## 2) Observability (Opik focus)
- Spans = agent steps; traces = full LangGraph job paths.
- Capture first: Evidence Pack creation, first triple extraction, Critic verify/flag, final compile.
- LLM-as-judge eval: hallucination, relevance, pedagogy vs rigor scored against evidence graph and RetrievalBundles.
- Production monitoring: latency, token-equivalent usage, cost anomalies, regression detection on extraction/synthesis.

## 3) Retrieval, rerank, and Evidence Pack contract
- Components: nv-embedqa-e5-v5 (embedder), llama-3.2-nv-rerankqa-1b-v2 (reranker), Nemotron-49B via SGLang.
- Feature behavior:
  - `RERANKER_ENABLED=true`: mandatory for blueprint-driven section runs; fallback to embed-only if false.
  - Cartography and other paths must still operate when reranker is off.
- Scoping: every section synthesis run is tied to a specific `ingestion_id`; RetrievalBundle key = (project_id, ingestion_id, section_id, query_id).
- Evidence Pack (mandatory for heavy calls):
  - Pointers (doc_id, page, section, chunk_id), quoted snippets (~300–800 tokens, 5–20 items), provenance, task-scoped glossary.
  - Full PDF is excluded by default; only included for special cases.
- Flow per section/query:
  1) Embed recall (top-K, e.g., 64–128).
  2) Optional rerank → top-M (e.g., 16–32).
  3) Build Evidence Pack; persist RetrievalBundle with models/scores for audit.

## 4) Agent protocols
- Cartographer (two-pass):
  - Pass 1: broad, cheap triage (keyword/regex, embeddings, TOC targeting) → candidate mentions + pointers.
  - Pass 2: narrow, schema-locked with small Evidence Pack per entity type → Nemotron-49B emits strict triples (entities/relations/spans/backing chunk_ids).
- Critic (bounded spot-check):
  - For each claim/triple: request top 1–3 snippets; label Verified/Unsupported/Contradicted/Ambiguous.
  - On Ambiguous: at most one additional snippet (bounded retry).
  - Keeps Nemotron calls short even with 64k available.
- Synthesizer:
  - Inputs: blueprint slot metadata, Evidence Pack (Packet A), Analytical Notes (Packet B, style-only), strict schema.
  - Outputs: structured Markdown with canonical citation tokens (`[[chunk:<chunk_id>]]`) and template adherence; no free-form structure.

## 5) Blueprint + citations + visual anchors
- Blueprint governs section queries (RQs + depth intent) and visual placeholders with required triple predicates.
- VisualPlaceholder rule: only triples satisfying required predicates can populate tables/figures; prevents column guessing.
- Compiler resolves canonical citation tokens to rendered superscripts at compile time; locked manuscript text remains unchanged.

## 6) Scheduling and bounded parallelism (Nemotron-49B)
- With `max-running-requests=1` and long context, use a small number of bounded Tier-B calls per section:
  - Stage 0 (offline): doc map + embeddings index.
  - Stage 1 (Tier A, forkable): retrieval + snippet packing (embed + optional rerank + Evidence Pack).
  - Stage 2 (Tier B): Nemotron-49B extraction/normalization (triples).
  - Stage 3 (Tier B): Nemotron-49B Critic spot-checks in batches.
  - Stage 4 (Tier B): Nemotron-49B Synthesizer for unlocked sections under review.
- Most steps stay in Tier A; 49B is reserved for closing evidence → triples → manuscript.

## 7) Open questions / next decisions
- Which Cartographer paths should move to SGLang programs first, and what telemetry thresholds justify it?
- Default top-K/top-M per workflow (Cartographer vs section synthesis) under rerank on/off.
- Opik signal minimal set for GA: which spans/metrics are P0 vs optional?
- Evidence Pack size limits per task (snippet count/length) and per-call budget ceilings.
- Criteria to trigger rerank “required” mode vs optional fallback (e.g., blueprint sections only?).
