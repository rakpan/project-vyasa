# Vyasa Refinement Baseline (Next)

Purpose: lock in the model stack, service roles, endpoint contracts, and orchestration invariants for the next refinement. This is a planning document only; no code changes implied.

## Model-to-Service Mapping

| Role (Vyasa) | Model ID | Service | Endpoint | Notes |
| --- | --- | --- | --- | --- |
| TEXT (Brain/Worker) | nvidia/Llama-3_3-Nemotron-Super-49B-v1_5 | SGLang | /v1/chat/completions | OpenAI-style chat API. Used for extraction, synthesis, and critique. |
| Embedder | nvidia/nv-embedqa-e5-v5 | NeMo Retriever Embedding NIM (preferred) or current embedder service | /embed (current) or /v1/embeddings (NIM) | Current embedder service exposes /embed and /embeddings. |
| Reranker | llama-3.2-nv-rerankqa-1b-v2 | NeMo Retriever Rerank NIM | /v1/ranking | OpenAI-style ranking API. Adapter required if current client expects /rerank. |
| Vision (optional) | Qwen/Qwen2-VL-7B-Instruct | SGLang (vision profile) | /v1/chat/completions | Only for scanned/image-heavy sources. |

## Feature Flags

- RERANKER_ENABLED (planned):
  - true: retrieval must execute reranking before Evidence Packet A is finalized.
  - false: retrieval falls back to embedding-only ranking (degraded but functional).
- VISION_ENABLED (existing pattern):
  - true: allow vision routing for scanned/image-heavy pages.
  - false: skip vision and treat pages as text-only.
- NIM_EMBEDDER_ENABLED (planned):
  - true: route embeddings to NeMo Retriever NIM /v1/embeddings.
  - false: use current embedder service /embed.

## Orchestration Invariants (Non-Negotiable)

- Primary Sources (Evidence) are citeable. Analytical Notes (Perspectives) are influence-only.
- Prompt contract is enforced:
  - Packet A (Primary Sources) supplies all facts and citations.
  - Packet B (Analytical Notes) may influence style, analogies, and pedagogy only.
- RetrievalBundle is persisted for reproducibility:
  - Must record query, candidate set, reranked set, scores, and model versions.
- Blueprint governs synthesis:
  - Manuscript generation is section-by-section via blueprint sections.
  - No single-shot manuscript generation.

## Endpoint Contracts

This baseline intentionally avoids duplicating full request/response schemas. Treat the following as the authoritative references:

- SGLang TEXT: `docs/architecture/07-agent-orchestration-api.md`
- Retrieval + evidence gating: `docs/architecture/09-retrieval-evidence-selection.md`
- Citation + compile invariants: `docs/architecture/10-citation-compilation.md`
- Full orchestration spec (planning): `docs/refinements/orchestration-spec-perspectives-blueprint-rerank.md`

## Health Checks (Required vs Optional)

- Required for core operation:
  - TEXT service (Brain/Worker SGLang)
  - Vector store (Qdrant)
  - Graph store (ArangoDB)
- Optional but strongly recommended (degraded if absent):
  - Embedder (fallback to zero-vector retrieval is unacceptable for production, but system remains online)
  - Reranker (fallback to embedding-only ranking allowed when RERANKER_ENABLED=false)
  - Vision (only for scanned/image-heavy workflows)

## Rollout Stages

1) Baseline (current):
   - TEXT via SGLang /v1/chat/completions.
   - Embedder service /embed and /embeddings.
   - Reranker optional; adapter supports /rerank.

2) NIM Integration:
   - Switch embeddings to NeMo Retriever Embedding NIM /v1/embeddings behind NIM_EMBEDDER_ENABLED.
   - Introduce Reranker NIM /v1/ranking behind RERANKER_ENABLED; maintain adapter until migration complete.

3) Governance Hardening:
   - Enforce RetrievalBundle persistence for all section queries.
   - Enforce Blueprint-only synthesis (no one-shot manuscript paths).
   - Automated audits: verify Packet A citation compliance and Packet B influence-only policy.

## Notes

- The reranker is mandatory in the retrieval loop when enabled; the system must still function when disabled or unavailable.
- All analytical notes are non-citeable by definition and must never be used as evidence.
- Evidence Packet A is the only valid source for citations and factual claims.
