# Vyasa Retrieval and Evidence Selection

This document defines how evidence enters Nemotron’s context and why that selection is reproducible. It is the authoritative reference for evidence gating and retrieval determinism.

## 1) Retrieval Stack Overview

- Embedder: nv-embedqa-e5-v5
  - Generates query and chunk embeddings for recall.
  - Supplies the initial candidate set (top-K) from Qdrant.
- Reranker: NeMo Retriever 1B (llama-3.2-nv-rerankqa-1b-v2)
  - Re-scores the top-K candidate set to produce top-M evidence.
  - Mandatory when enabled; optional when disabled via feature flag.
- Nemotron 49B (nvidia/Llama-3_3-Nemotron-Super-49B-v1_5)
  - Consumes only the final Evidence Packet A (top-M) plus optional Analytical Notes.

## 2) RetrievalBundle as a First-Class Artifact

RetrievalBundle is the canonical record of evidence selection. It is persisted and referenced by section compilation and audit.

### Schema (Logical)

- Identifiers:
  - bundle_id
  - project_id
  - section_id (optional)
  - query_id (optional)
- Query metadata:
  - query_text
  - query_source (e.g., blueprint_section)
  - linked_rqs
- Retrieval pipeline results:
  - candidate_chunks (top-K)
  - reranked_chunks (top-M)
- Scores:
  - embed_scores (per candidate)
  - rerank_scores (per reranked)
- Model versions:
  - embedder_model_id
  - reranker_model_id
- Parameters:
  - top_k_embed
  - top_k_rerank
- Timestamp:
  - created_at

### Why it must be persisted in ArangoDB

- ArangoDB is the system of record for manuscript truth and governance.
- RetrievalBundles must be auditable, versioned, and referentially stable.
- Qdrant is a retrieval accelerator, not a source of truth.

## 3) Determinism Guarantees

- Determinism contract:
  - Same query + same corpus + same models + same parameters → same RetrievalBundle.
- Why this matters:
  - Peer review: evidence selection must be reproducible and inspectable.
  - Audit: reviewers can verify what evidence was considered and why.
  - Integrity: prevents silent drift in evidence selection across runs.

## 4) Interaction with Blueprint

- Section metadata (heading, depth intent, linked RQs, visual anchors) shapes the query.
- Retrieval is section-scoped, not manuscript-scoped, because:
  - Evidence relevance is context-sensitive to section intent.
  - It prevents cross-section contamination and supports targeted audits.
- Each section produces its own RetrievalBundle, referenced during compilation.

## 5) Failure and Fallback Rules

- Reranker unavailable:
  - If RERANKER_ENABLED=true: retrieval fails fast and reports degraded state.
  - If RERANKER_ENABLED=false: return top-M from embedding scores only.
- Embedder mismatch (dimension or model ID):
  - Retrieval fails; ingestion or re-embedding is required before proceeding.
- Evidence drift after retrieval:
  - If the corpus changes, RetrievalBundles are stale.
  - Sections tied to stale bundles must be re-retrieved and recompiled.

## Evidence Gating Summary

- Only Evidence Packet A (top-M reranked chunks) may enter Nemotron’s context as citeable evidence.
- Analytical Notes are separate and influence-only.
- The RetrievalBundle is the audit trail that makes this process reproducible.
