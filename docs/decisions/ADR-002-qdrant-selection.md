# ADR 002: Selection of Qdrant for Vector Storage

* **Status**: Accepted
* **Date**: 2025-12-29

## Context
We need a vector database to store embeddings for the 24 PDF corpus. The original template used Pinecone.

## Decision
We will remove Pinecone and use **Qdrant** running locally in Docker.

## Consequences
* **Positive**: Data remains strictly local on the DGX (Privacy). No API costs.
* **Positive**: Zero latency network calls.
* **Negative**: We must manage the storage volume/backups ourselves (unlike managed Pinecone).
