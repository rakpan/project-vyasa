# Vyasa Agent Runtime: From Conceptual Roles to Production Agents

**Purpose**: Authoritative reference for agent execution engine, protocols, and runtime configuration. This document consolidates implementation-aligned architecture with planning context.

**Status**: Implementation-aligned (main sections) + Planning context (appendix)

**Authoritative References**:
- Retrieval + evidence gating: `docs/architecture/09-retrieval-evidence-selection.md`
- Citation + compilation: `docs/architecture/10-citation-compilation.md`
- Manuscript persistence: `docs/architecture/11-manuscript-persistence-lifecycle.md`
- Compiler contract: `docs/architecture/13-manuscript-compiler-contract.md`

---

## Overview

Vyasa agents execute within a LangGraph-based orchestrator, calling SGLang-served models for structured extraction, synthesis, and critique. The system enforces evidence-bound protocols where Primary Sources (Evidence Packet A) are the only citeable evidence, and Analytical Notes (Packet B) influence style only.

**Core Components**:
- **Execution Engine**: LangGraph orchestrator + SGLang model servers
- **Retrieval Stack**: Embedder (nv-embedqa-e5-v5) → Reranker (llama-3.2-nv-rerankqa-1b-v2) → Evidence Packet A
- **Heavy LLM**: Nemotron-3.3-Super-49B-v1.5 (served by SGLang) - referred to as "Nemotron-49B" throughout this document
- **LLM Services**: Nemotron-49B (Brain/Worker) for extraction, synthesis, critique
- **Observability**: Opik (optional) for tracing and prompt registry

---

## Locked Invariants

These invariants are non-negotiable and enforced at runtime:

### Evidence Gating
- **Primary Sources (Evidence Packet A)**: Only top-M reranked chunks may enter Nemotron's context as citeable evidence.
- **Analytical Notes (Packet B)**: Influence style, analogies, and pedagogy only. Never citeable.
- **RetrievalBundle**: Must be persisted for reproducibility and audit. Key = (project_id, ingestion_id, section_id, query_id).

### Citation Protocol
- **Canonical Citation Tokens (CCTs)**: Format `[[chunk:<chunk_id>]]` is the only citation representation in stored content.
- **Rendered Superscripts**: Compiler-only artifacts, never stored in editor drafts.
- **Evidence Binding**: All factual claims must be grounded in Evidence Packet A.

### Blueprint Governance
- **Section-by-Section Synthesis**: No single-shot manuscript generation.
- **Blueprint-Driven**: Section queries derived from blueprint metadata (RQs, depth intent, visual anchors).
- **Determinism**: Same blueprint + same RetrievalBundles → same compiled output.

### Retrieval Determinism
- **Contract**: Same query + same corpus + same models + same parameters → same RetrievalBundle.
- **Persistence**: RetrievalBundles stored in ArangoDB (system of record), not Qdrant.

### Evidence Scoping
- **Ingestion-scoped synthesis**: Every synthesis run is scoped to `ingestion_id`.
- **RetrievalBundle keys**: Include `(project_id, ingestion_id, section_id, query_id)` for unambiguous identification and reproducibility.

### Heavy Call Contract
- **Evidence Pack requirement**: Any Nemotron-49B call must use an Evidence Pack (unless explicitly flagged as an exceptional deep-read task).
- **64K context is reserved for**: Cached prefix reuse (RadixAttention) and exceptional deep-read tasks.
- **Default heavy calls**: Operate on Evidence Packets (not full 64K context) to maximize efficiency and reuse.

### Citation Stability
- **Canonical tokens in storage**: Manuscript text uses canonical citation tokens (`[[chunk:<chunk_id>]]`).
- **Compiler resolution**: Compiler resolves tokens to rendered superscripts at render time.
- **Locked prose immutability**: Locked prose never changes due to citation renumbering; only rendering changes.

### Bounded Parallelism
- **Nemotron-49B concurrency**: `max-running-requests=1` for Nemotron-49B services.
- **Parallelism concentration**: Parallelism is concentrated in Tier-A steps (retrieval, embedding, snippet packing).

### Evidence Drift Controls
- **RetrievalBundle persistence**: RetrievalBundle persists embedder/reranker model IDs, scores, and downgrade flags (`rerank_skipped`, `rerank_error`) for reproducibility and audit.

### Locking Guidance
- **Locked sections**: Locked sections should never be rewritten by LLM tooling.
- **Citation rendering only**: Only canonical citation rendering (CCT → superscript) may change in locked sections.

---

## Execution Engine

### Current Implementation

**Orchestration**: LangGraph-based orchestrator manages branching, retries, and state transitions.

**Model Serving**: SGLang servers expose OpenAI-style `/v1/chat/completions` endpoints:
- **Brain** (Port 30000): Critic, high-level reasoning, synthesis
- **Worker** (Port 30001): Cartographer extraction, structured JSON output
- **Vision** (Port 30002, optional): OCR/captioning for image-heavy sources

**Structured Decoding**: JSON/regex FSM enforces Compilation Contract outputs:
- Triples (entities/relations/spans/backing chunk_ids)
- Manifests (RetrievalBundles, artifact metadata)
- Structured Markdown sections with CCTs

**Configuration** (DGX Spark baseline):
- Context length: 65536 tokens (64K)
- Max running requests: 1 (maximizes KV cache per request)
- Quantization: w8a8_int8
- Attention backend: flashinfer
- Tensor parallelism: 1 (single GPU)

### Planned Optimizations

**SGLang Program Migration**: Migrate flows that are stable and benefit from fork/join + prefix reuse. Requires telemetry threshold validation before migration:
- `.fork()/.join()` for parallel processing
- RadixAttention for KV cache reuse (shared prefixes: system + contract + doc anchor + TOC map + Evidence Packet A)

**KV Cache Reuse**: Measure reuse benefits via telemetry before assuming gains. Shared prefixes are cached and reused when prefixes are identical across related requests.

**Note**: These optimizations are planned and require telemetry validation before implementation.

---

## Observability (Opik)

**Status**: Optional, disabled by default. Opik traces must never impact runtime decisions.

**Configuration**:
- `OPIK_ENABLED` (default: false)
- `OPIK_BASE_URL` (e.g., `http://opik-api:5000`)
- `OPIK_API_KEY` (if required)
- `OPIK_TIMEOUT_SECONDS` (default: 2)

**Trace Structure**:
- **Spans**: Agent steps (Cartographer extraction, Critic validation, Synthesizer generation)
- **Traces**: Full LangGraph job paths

**Capture Points** (P0 for GA):
- Evidence Packet A creation
- First triple extraction
- Critic verify/flag
- Final compile

**Metrics** (computed, not inferred):
- Latency per agent step (measured from span start/end)
- Token-equivalent usage (counted from model responses)
- Cost anomalies (computed from token counts × model pricing)
- Regression detection (extraction/synthesis quality scored against evidence graph and RetrievalBundles)

**LLM-as-Judge Eval**: 
- **Hallucination**: Defined as any claim lacking backing chunk_id references in the evidence graph / RetrievalBundle.
- Relevance, pedagogy vs rigor scored against evidence graph and RetrievalBundles.

**Integration**: Non-blocking; system continues normally if Opik unavailable.

---

## Retrieval + Rerank + Evidence Packet Contract

### Components

- **Embedder**: nv-embedqa-e5-v5 (generates query/chunk embeddings)
- **Reranker**: llama-3.2-nv-rerankqa-1b-v2 (re-scores top-K → top-M)
- **LLM Consumer**: Nemotron-49B (consumes Evidence Packet A + optional Packet B)

### Feature Behavior

**RERANKER_ENABLED** (default: true):
- `true`: Mandatory for blueprint-driven section runs; fallback to embed-only if reranker unavailable and `RERANKER_REQUIRED=false`.
- `false`: Fallback to embedding-only ranking (degraded but functional).
- Cartography and other paths must still operate when reranker is off.

**RERANKER_REQUIRED** (default: false):
- `true`: Retrieval fails fast if reranker unavailable.
- `false`: If reranker is unavailable, fall back to embed-only ranking and record the downgrade in RetrievalBundle (`rerank_skipped=true`, `rerank_error` field populated).

### Evidence Packet A (Primary Sources)

**Definition**: Top-M reranked chunks after embedding recall (top-K) and optional reranking.

**Content**:
- Pointers: doc_id, page, section, chunk_id
- Quoted snippets: Default 12 snippets, max 600 tokens per snippet
- Hard caps: snippets ≤ 20, snippet_tokens ≤ 800
- Provenance: file_hash, ingestion_id, project_id
- Task-scoped glossary (if applicable)

**Exclusions**: Full PDF excluded by default; only included for special cases.

**Overrides**: Any override of defaults or caps must be explicitly recorded in call metadata and RetrievalBundle.

**Mandatory For**: Nemotron-49B calls (synthesis, critique, extraction with schema locks).

### Retrieval Flow (Per Section/Query)

1. **Embed Recall**: Query → embedding → Qdrant search → top-K candidates (default: 64)
2. **Optional Rerank**: Reranker re-scores → top-M results (default: 24)
3. **Build Evidence Packet A**: Assemble top-M chunks with snippets and provenance
4. **Persist RetrievalBundle**: Store query, candidates, reranked set, scores, model versions in ArangoDB

### Defaults

- `RETRIEVAL_TOP_K`: 64 (candidates from Qdrant)
- `RERANK_TOP_M`: 24 (final evidence chunks)
- Top-M=24 fits within 64K context window for Nemotron-49B (allows room for prompts, Packet B, system context)

### Scoping

Every section synthesis run is tied to a specific `ingestion_id`. RetrievalBundle key = (project_id, ingestion_id, section_id, query_id).

---

## Agent Protocols

### Cartographer (Two-Pass Extraction)

**Pass 1 (Broad Triage)**:
- Keyword/regex matching
- Embedding-based recall
- TOC targeting
- Output: Candidate mentions + pointers

**Pass 2 (Narrow, Schema-Locked)**:
- Small Evidence Packet A per entity type
- Nemotron-49B emits strict triples:
  - Entities/relations/spans
  - Backing chunk_ids
- Structured JSON output enforced

**Current Implementation**: LangGraph node calling Worker service with Cartographer prompt profile.

**Planned Optimization**: Migrate to SGLang programs for `.fork()/.join()` parallelism (requires telemetry validation).

### Critic (Bounded Spot-Check)

**Protocol**:
- For each claim/triple: request top 1–3 snippets from Evidence Packet A
- Label: Verified / Unsupported / Contradicted / Ambiguous
- On Ambiguous: at most one additional snippet (bounded retry)

**Context Budget**: Keeps Nemotron calls short even with 64K available.

**Current Implementation**: LangGraph node calling Brain service with Critic prompt profile.

### Synthesizer (Section Writer)

**Inputs**:
- Blueprint slot metadata (heading, depth intent, linked RQs, visual anchors)
- Evidence Packet A (Primary Sources - MUST be cited)
- Analytical Notes (Packet B - style-only, never cited)
- Strict schema (section structure, word budget)

**Outputs**:
- Structured Markdown with canonical citation tokens (`[[chunk:<chunk_id>]]`)
- Template adherence (hook, proof, so-what structure)
- No free-form structure

**Current Implementation**: Section synthesis loop in `src/orchestrator/section_synthesis/section_orchestrator.py`.

### Lead Counsel (Strategic Triage)

**Role**: Strategic triage and format selection (Summary vs. Detail). Lead Counsel is the supervisory agent; Synthesizer is the manuscript-generation node it invokes.

**Current Status**: Conceptual role; implementation details pending.

**Planned**: Decision logic for routing to appropriate agent based on task complexity and evidence coverage.

---

## Blueprint + Citations + Visual Anchors

### Blueprint Governance

**Section Queries**: Derived from blueprint metadata:
- Research Questions (linked_rqs)
- Depth intent (overview, detailed, comprehensive)
- Visual anchors (required triple predicates)

**Section-by-Section Synthesis**: Blueprint governs manuscript structure; no single-shot generation.

### Citation Resolution

**Canonical Citation Tokens (CCTs)**: Format `[[chunk:<chunk_id>]]` stored in manuscript blocks.

**Compiler Responsibility**: Resolves CCTs to rendered superscripts at compile time. Locked manuscript text remains unchanged.

**Evidence Binding**: CCTs must map to Evidence Packet A only. Analytical Notes never receive CCTs.

### Visual Anchors

**VisualPlaceholder Rule**: Only triples satisfying required predicates can populate tables/figures. Prevents column guessing.

**Determinism**: VisualPlaceholders must be deterministic from:
- Blueprint section metadata
- Evidence cluster IDs
- Visual anchor specifications

**Placeholder Format**: Markdown markers `[[FIGURE:<anchor_id>]]` and `[[TABLE:<anchor_id>]]` injected into section text.

---

## Scheduling under Bounded Parallelism

### Tier Model

**Tier A (Forkable, CPU/Embedder-Bound)**:
- Document mapping + embeddings index (offline)
- Retrieval + snippet packing (embed + optional rerank + Evidence Packet A)

**Tier B (GPU-Bound, Nemotron-49B)**:
- Extraction/normalization (triples)
- Critic spot-checks (batches)
- Synthesizer for unlocked sections under review

### Concurrency Constraints

**Current Configuration** (`max-running-requests=1`):
- Maximizes KV cache per request
- Simplifies scheduling for stability
- Reduces contention and OOM risk

**Bounded Calls Per Section**:
- Stage 0 (offline): doc map + embeddings index
- Stage 1 (Tier A): retrieval + Evidence Packet A
- Stage 2 (Tier B): Nemotron-49B extraction/normalization
- Stage 3 (Tier B): Nemotron-49B Critic spot-checks
- Stage 4 (Tier B): Nemotron-49B Synthesizer

**Most Steps Stay in Tier A**: 49B reserved for closing evidence → triples → manuscript.

### KV Cache Monitoring

**Thresholds**:
- KV cache fill < 80%: Normal operation
- KV cache fill 80-95%: Delay new requests
- KV cache fill > 95%: Retry later (backpressure)

**Tuning Rules** (from `deploy/runbooks/dgx-runtime.md`):
- Increase `max-running-requests` only if: KV cache fill < 80%, queue depth < 2, zero watchdog restarts over 24h
- Increase `context-length` beyond 64K only if: UMA/VRAM pressure < 85%, sustained KV cache headroom observed

---

## API Surface

### Job Submission and Status

- **POST** `/api/jobs`: Submit LangGraph job
- **GET** `/api/jobs/:job_id`: Get job status
- **GET** `/api/jobs/:job_id/status`: Polling endpoint with stage/progress

### Event Stream

- **SSE** `/api/jobs/:job_id/events`: `astream_events` v2 for UI heartbeat and interrupts
- **Integration**: Console consumes SSE for real-time updates

### Manifest Download

- **GET** `/api/jobs/:job_id/manifest`: Download artifact manifest (claims, citations, density)

### Section Synthesis Endpoints

- **POST** `/api/projects/:project_id/sections/:section_id/run`: Trigger section synthesis
- **GET** `/api/projects/:project_id/sections/:section_id/status`: Get synthesis status with stage/progress

---

## Contracts and Rigor

### Artifact Manifest Contract

- Claims with priority tags (HIGH/LOW)
- Citations (CCTs → evidence anchors)
- Density metrics (claims per section, evidence coverage)

### Tone/Precision Contracts

- **Conservative Mode**: Strict schema enforcement, citation validation required
- **Exploratory Mode**: Relaxed constraints for initial discovery

### Compilation Contract

- Structured Markdown with CCTs
- Template adherence (hook, proof, so-what)
- Word budget enforcement
- Section locking semantics

---

## Integration Notes

### Proxy Expectations (Console)

- Console → Orchestrator: HTTP proxy via `/api/proxy/orchestrator/*`
- Authentication: NextAuth session tokens
- Error Handling: Graceful degradation if services unavailable

### SSE/Event Stream Consumption

- Console polls `/api/jobs/:job_id/events` for real-time updates
- Exponential backoff for polling (1s → 2s → 4s → 8s capped)
- Max duration: 10 minutes (safety cap)
- Max polls: 300 (worst-case ~40 minutes with backoff)

---

## Appendix: Open Questions / Next Decisions

**Note**: This section contains planning-only items and unresolved decisions. Implementation should not depend on these items.

### Execution Engine Optimizations

- **Q1**: Which Cartographer paths should move to SGLang programs first, and what telemetry thresholds justify it?
- **Q2**: KV reuse (RadixAttention) benefits: measure reuse benefits via telemetry instead of assuming gains. What are the telemetry requirements?

### Retrieval Defaults

- **Q3**: Default top-K/top-M per workflow (Cartographer vs section synthesis) under rerank on/off. Current defaults (K=64, M=24) are section synthesis defaults; Cartographer may need different values.

### Observability

- **Q4**: Opik signal minimal set for GA: which spans/metrics are P0 vs optional?

### Evidence Packet Limits

- **Q5**: Evidence Packet A size limits per task (snippet count/length) and per-call budget ceilings. Current guidance: ~300–800 tokens, 5–20 items.

### Reranker Configuration

- **Q6**: Criteria to trigger rerank "required" mode vs optional fallback (e.g., blueprint sections only?). Current: `RERANKER_REQUIRED=false` (optional fallback).

### Lead Counsel Implementation

- **Q7**: Strategic triage logic: when to route to Summary vs Detail format? What are the decision criteria?

---

## Planning Notes Disclaimer

**Original Planning Document**: `docs/refinements/agent-runtime-plan.md`

The planning notes document ("Vyasa Agent Runtime: Planning Notes (Cartographer, Critic, Lead Counsel)") has been integrated into this consolidated architecture document. Items marked as "planned" or "open questions" in the original planning notes are preserved in the "Planned Optimizations" and "Open Questions / Next Decisions" sections above.

**Scope**: This document is implementation-aligned for main sections. Planning-only items are clearly marked and should not be treated as implementation requirements until validated.
