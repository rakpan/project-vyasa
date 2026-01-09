# Agent Runtime Documentation Inventory

**Purpose**: Comprehensive inventory of files referencing agent runtime concepts, Evidence Pack, RetrievalBundle, RERANKER_ENABLED, max-running-requests, Nemotron-49B, Opik, KV cache/RadixAttention, and citation formats.

**Date**: 2025-01-XX  
**Status**: Research-only inventory

---

## 1. Architecture Documentation

### 1.1 Agent & Orchestration
- **`docs/architecture/07-agent-orchestration-api.md`** (Lines 1-22)
  - **Summary**: Defines LangGraph-based orchestrator with node roles (Cartographer, Critic, Reframer, Synthesizer). Mentions job submission, event streams, artifact manifests, and tone/precision contracts. No explicit mention of "consolidated version" or "Planning Notes" but covers agent orchestration concepts.

### 1.2 Retrieval & Evidence Selection
- **`docs/architecture/09-retrieval-evidence-selection.md`** (Lines 1-85)
  - **Summary**: Authoritative reference for evidence gating and retrieval determinism. Defines RetrievalBundle as first-class artifact with schema, persistence requirements, and determinism guarantees. States Evidence Packet A (top-M reranked chunks) is the only citeable evidence. Mentions RERANKER_ENABLED=true/false behavior and failure modes. References Nemotron 49B consuming Evidence Packet A.

### 1.3 Citation & Compilation
- **`docs/architecture/10-citation-compilation.md`** (Lines 1-89)
  - **Summary**: Defines canonical citation tokens (CCTs) format `[[chunk:<chunk_id>]]`, compiler responsibilities, locked section guarantees, and compile run artifacts. States CCTs are machine-stable and must never be replaced with rendered superscripts in stored content. References RetrievalBundles as compile inputs.

- **`docs/architecture/13-manuscript-compiler-contract.md`** (Lines 1-114)
  - **Summary**: Normative invariants for manuscript assembly. Defines Evidence Packet A as mandatory for citations, RetrievalBundle as audit trail, and CCT format `[[chunk:<chunk_id>]]`. States Analytical Notes are non-citeable and influence-only. Mentions RetrievalBundle staleness triggers and Evidence Packet A changes.

### 1.4 Model Inventory & Configuration
- **`docs/architecture/01-model-inventory.md`** (Lines 9-33)
  - **Summary**: Lists Nemotron-49B (`nvidia/Llama-3_3-Nemotron-Super-49B-v1_5`) for Brain/Worker services. Mentions `--max-running-requests 3` (documented but actual compose uses `1`), `--context-length 32768` (documented but actual compose uses `65536`), and KV cache policy not otherwise specified. References SGLang serving configuration.

- **`docs/architecture/02-model-registry-and-router.md`** (Lines 59-94)
  - **Summary**: Defines model routing and registry. Mentions Nemotron-49B as default TEXT_MODEL_ID. States KV cache policy is configured in docker-compose command flags (not in router). References HuggingFace Hub model paths.

### 1.5 Resource Optimization
- **`docs/architecture/04-resource-optimization.md`** (Lines 3-7)
  - **Summary**: Merged content on memory and KV cache optimization. Mentions KV cache sizing and eviction guidance. References memory optimization patterns.

### 1.6 Observability
- **`docs/architecture/05-telemetry-and-observability.md`** (Lines 1-141)
  - **Summary**: Defines Opik as optional self-hosted "flight data recorder" for Vyasa. States Opik is disabled by default and must never impact runtime decisions. Documents OPIK_ENABLED, OPIK_BASE_URL, OPIK_API_KEY configuration. Mentions kv_cache_fill_pct metric (0-100). References Opik integration as non-blocking.

---

## 2. Refinements Documentation (Planning & Current State)

### 2.1 Agent Runtime Planning
- **`docs/refinements/agent-runtime-plan.md`** (Lines 1-67)
  - **Summary**: **PRIMARY SOURCE** for "Planning Notes (Cartographer, Critic, Lead Counsel)". Defines execution engine (LangGraph + SGLang + Nemotron-49B), observability (Opik focus), retrieval/rerank/Evidence Pack contract, agent protocols (Cartographer two-pass, Critic bounded spot-check, Synthesizer), and scheduling with bounded parallelism. Mentions KV reuse (RadixAttention) for shared prefixes, RERANKER_ENABLED=true as mandatory for blueprint-driven section runs, Evidence Pack as mandatory for heavy calls, and max-running-requests=1 with long context. States RetrievalBundle key = (project_id, ingestion_id, section_id, query_id).

### 2.2 Orchestration Specification
- **`docs/refinements/orchestration-spec-perspectives-blueprint-rerank.md`** (Lines 1-1688)
  - **Summary**: **PRIMARY SOURCE** for detailed orchestration spec. Defines AnalyticalNote, ManuscriptBlueprint, and RetrievalBundle schemas. Documents section synthesis loop (8 steps), failure modes, state diagrams, sequence diagrams, and configuration defaults. References RERANKER_ENABLED, RETRIEVAL_TOP_K (64), RERANK_TOP_M (24), Evidence Packet A, and Nemotron 49B synthesis/critique calls. States RetrievalBundle persistence is non-fatal.

### 2.3 Next Refinement Baseline
- **`docs/refinements/next-refinement-baseline.md`** (Lines 1-79)
  - **Summary**: Locks in model stack, service roles, endpoint contracts, and orchestration invariants. Defines Nemotron-49B for TEXT (Brain/Worker), RERANKER_ENABLED feature flag behavior, Evidence Packet A as only citeable source, RetrievalBundle persistence requirements, and Blueprint-only synthesis. Mentions rollout stages and NIM integration plans.

### 2.4 Current State Research
- **`docs/refinements/retrieval-and-manuscript-current-state.md`** (Lines 1-607)
  - **Summary**: Documents current implementation of chunking, retrieval, manuscript storage, LangGraph context assembly, and UI data flows. Describes chunk ID generation, Qdrant storage, embedding model (nv-embedqa-e5-v5), retrieval function, manuscript block storage, and job store. Mentions RetrievalBundle could be stored in ResearchState or job.result field. References Opik for prompt registry.

---

## 3. Runtime/Configuration Documentation

### 3.1 DGX Runtime Runbook
- **`deploy/runbooks/dgx-runtime.md`** (Lines 1-155)
  - **Summary**: **PRIMARY SOURCE** for runtime configuration. Defines SGLang serving baseline with `--max-running-requests 1`, `--context-length 65536`, `--mem-fraction-static 0.50`, and staged tuning rules. Documents KV cache fill monitoring (< 80% threshold), UMA/VRAM pressure targets, and GPU/NUMA affinity. States max-running-requests increase criteria (KV cache fill < 80%, queue depth < 2, zero watchdog restarts).

### 3.2 Docker Compose Configuration
- **`deploy/docker-compose.yml`** (Lines 4-140)
  - **Summary**: **PRIMARY SOURCE** for actual runtime configuration. Defines cortex-brain and cortex-worker with `--max-running-requests 1`, `--context-length 65536`, `--quantization w8a8_int8`, `--attention-backend flashinfer`, and Nemotron-49B model path. Comments mention KV cache fill monitoring, queue depth, and watchdog restarts. States max-running-requests 1 maximizes KV cache per request and simplifies scheduling.

### 3.3 Configuration Reference
- **`docs/configuration/config-reference.md`** (Lines 5-79)
  - **Summary**: Documents environment variables including OPIK_ENABLED, OPIK_BASE_URL, OPIK_API_KEY, OPIK_TIMEOUT_SECONDS, and PROMPT_REGISTRY_ENABLED. Mentions Opik integration and prompt registry configuration.

---

## 4. Code Implementation Files

### 4.1 Retrieval & Evidence Pack
- **`src/orchestrator/storage/qdrant.py`** (Lines 405-543)
  - **Summary**: Implements `retrieve_chunks_by_query()` with RERANKER_ENABLED logic. Handles use_reranker parameter, top-K/top-M limits, and fallback to embed-only when reranker disabled. References Evidence Packet A construction.

- **`src/orchestrator/retrieval/retrieval_service.py`** (Lines 1-219)
  - **Summary**: Implements RetrievalService with `retrieve_for_section()` method. Handles retrieval + rerank integration, RetrievalBundle persistence, and RERANKER_ENABLED/RERANKER_REQUIRED flags. Returns reranked chunks and bundle_id.

- **`src/orchestrator/schemas/retrieval.py`** (Lines 1-82)
  - **Summary**: Defines RetrievalBundle Pydantic schema with candidate_chunks, reranked_chunks, embedder_model_id, reranker_model_id, top_k_embed, top_k_rerank, and rerank_skipped fields. Documents Evidence Packet A (top-M chunks after reranking).

- **`src/orchestrator/services/retrieval_bundle_service.py`**
  - **Summary**: Implements RetrievalBundleService for persisting RetrievalBundle objects in ArangoDB. Handles save_bundle, get_bundle, and list_bundles operations.

### 4.2 Section Synthesis
- **`src/orchestrator/section_synthesis/section_orchestrator.py`** (Lines 1-960)
  - **Summary**: Implements section synthesis loop with query building, retrieval + rerank, Packet A/B construction, Nemotron 49B synthesizer/critic calls, and persistence. Uses RERANKER_ENABLED flag, builds Evidence Packet A from reranked chunks, and generates citations in `[[chunk:<chunk_id>]]` format. References RetrievalBundle persistence.

- **`src/orchestrator/services/section_synthesis_service.py`** (Lines 1-259)
  - **Summary**: Implements `persist_section_run()` for saving RetrievalBundle, ManuscriptBlock, and AnalyticalNote promotions. Handles provenance fields (retrieval_bundle_id, chunk_ids, note_ids, model_ids).

### 4.3 Configuration
- **`src/shared/config.py`** (Lines 100-201)
  - **Summary**: Defines RERANKER_ENABLED (default: true), RERANKER_REQUIRED (default: false), RETRIEVAL_TOP_K (default: 64), RERANK_TOP_M (default: 24), TEXT_MODEL_ID (default: Nemotron-49B), OPIK_ENABLED, OPIK_BASE_URL, OPIK_API_KEY, MAX_KV_CACHE_GB, and related configuration.

### 4.4 Observability & Metrics
- **`src/orchestrator/collectors/sglang_metrics.py`** (Lines 78-149)
  - **Summary**: Collects SGLang metrics including kv_cache_usage, kv_cache_usage_ratio, kv_cache_fill_id, and computes kv_cache_fill_pct (0-100).

- **`src/orchestrator/metrics_service.py`** (Lines 272-676)
  - **Summary**: Aggregates metrics including kv_cache_fill_pct from hardware_raw data. Exposes kv_cache_fill_pct in observatory response schema.

- **`src/orchestrator/observability.py`** (Lines 17-106)
  - **Summary**: Implements observability functions including `_kv_cache_reserved_gb()` using MAX_KV_CACHE_GB config.

- **`src/orchestrator/nodes/nodes.py`** (Lines 174-203)
  - **Summary**: Implements `check_kv_backpressure()` function that extracts kv_cache_utilization from Prometheus exposition and enforces backpressure (retry_later if >95%, delay if >85%).

### 4.5 Prompts & Opik
- **`src/orchestrator/prompts/registry.py`**
  - **Summary**: Implements prompt registry with Opik integration. Fetches prompts from Opik with fallback to local defaults. Uses OPIK_ENABLED, OPIK_BASE_URL, OPIK_API_KEY configuration.

- **`src/orchestrator/prompts/defaults.py`** (Lines 1-166)
  - **Summary**: Defines default prompt templates as fallbacks when Opik unavailable. Includes DEFAULT_SECTION_WRITER_PROMPT and DEFAULT_CROSS_EXAMINER_PROMPT with instructions to use `[[chunk:<chunk_id>]]` citations.

### 4.6 Citation Handling
- **`src/orchestrator/section_synthesis/section_orchestrator.py`** (Lines 878-909)
  - **Summary**: Extracts chunk citations from section_text using patterns `[[chunk:<id>]]` (preferred) and `[[<id>]]` (backward compatible). Stores chunk_ids separately from claim_ids.

- **`src/console/components/manuscript/CompiledManuscriptView.tsx`** (Lines 116-138)
  - **Summary**: Processes citation markers `[[chunk:<id>]]`, `[[claim:<id>]]`, or simple `[[<id>]]` and renders them as highlighted spans in ReactMarkdown.

---

## 5. Test Files

### 5.1 Retrieval & Rerank Tests
- **`src/tests/unit/orchestrator/test_retrieval_service.py`**
  - **Summary**: Tests RetrievalService with reranker success, required failure, optional fallback, and without reranker scenarios. Uses RERANKER_ENABLED, RERANKER_REQUIRED config.

- **`src/tests/unit/orchestrator/test_retrieval_bundle_service.py`**
  - **Summary**: Tests RetrievalBundleService save/get/list operations with ArangoDB mocks.

- **`src/tests/unit/orchestrator/test_section_synthesis.py`**
  - **Summary**: Tests section synthesis loop including RetrievalBundle creation, Packet A/B building, citation extraction, and order_index assignment.

### 5.2 Opik & Prompt Registry Tests
- **`src/tests/unit/orchestrator/test_prompt_registry.py`**
  - **Summary**: Tests prompt registry with Opik enabled/disabled, timeout handling, and fallback to defaults.

---

## 6. Key Findings

### 6.1 "Consolidated Version" and "Planning Notes"
- **Primary Location**: `docs/refinements/agent-runtime-plan.md` (Line 1)
  - Title: "Vyasa Agent Runtime: Planning Notes (Cartographer, Critic, Lead Counsel)"
  - This is the **consolidated planning document** referenced in the query.

### 6.2 Evidence Pack vs Evidence Packet A
- **Terminology**: "Evidence Pack" appears in planning docs (`agent-runtime-plan.md`), while "Evidence Packet A" appears in implementation and architecture docs.
- **Consistency**: Both refer to the same concept (top-M reranked chunks), but "Evidence Packet A" is the canonical term in code and architecture docs.

### 6.3 Citation Formats
- **Canonical Format**: `[[chunk:<chunk_id>]]` (documented in architecture/10-citation-compilation.md, architecture/13-manuscript-compiler-contract.md)
- **Backward Compatible**: `[[<id>]]` pattern also supported in code
- **No `\cite{}` Format**: LaTeX `\cite{}` format is **not found** in the codebase
- **No "Citation Paradox"**: This term is **not found** in the codebase

### 6.4 KV Cache / RadixAttention
- **KV Cache**: Extensively documented in `dgx-runtime.md`, `docker-compose.yml`, metrics collectors, and observability code
- **RadixAttention**: Only mentioned once in `agent-runtime-plan.md` (Line 13) as planned optimization for KV reuse with shared prefixes
- **Implementation Status**: RadixAttention is **planned**, not implemented

### 6.5 max-running-requests
- **Documented vs Actual**: Architecture docs mention `--max-running-requests 3`, but actual `docker-compose.yml` uses `1`
- **Primary Source**: `deploy/runbooks/dgx-runtime.md` and `deploy/docker-compose.yml` define actual runtime values

### 6.6 Nemotron-49B
- **Model ID**: `nvidia/Llama-3_3-Nemotron-Super-49B-v1_5`
- **Usage**: Brain (Critic/high-level reasoning) and Worker (Cartographer/extraction) services
- **Context Length**: 65536 tokens (actual), 32768 tokens (documented in some places - discrepancy)

### 6.7 Opik
- **Status**: Optional, disabled by default
- **Purpose**: Self-hosted "flight data recorder" for observability and prompt registry
- **Configuration**: OPIK_ENABLED, OPIK_BASE_URL, OPIK_API_KEY, OPIK_TIMEOUT_SECONDS
- **Integration**: Non-blocking, must never impact runtime decisions

---

## 7. Documentation Gaps & Inconsistencies

1. **Context Length Discrepancy**: Architecture docs mention 32768 tokens, but docker-compose.yml uses 65536
2. **max-running-requests Discrepancy**: Architecture docs mention 3, but docker-compose.yml uses 1
3. **Evidence Pack vs Evidence Packet A**: Terminology inconsistency between planning and implementation docs
4. **RadixAttention**: Mentioned as planned but no implementation details or timeline
5. **Citation Paradox**: Term not found - may be external concept or future consideration

---

## 8. Recommended Next Steps

1. **Consolidate Terminology**: Standardize on "Evidence Packet A" across all docs
2. **Update Architecture Docs**: Align context-length and max-running-requests with actual runtime values
3. **Document RadixAttention Plan**: Add implementation timeline and telemetry requirements
4. **Clarify Citation Strategy**: Document why `\cite{}` format is not used (if intentional)
