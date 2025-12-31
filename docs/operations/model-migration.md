# Model Migration Runbook (Embeddings)

When swapping embedding models (e.g., moving to BGE-Large 1024D), follow these steps to avoid silent failures.

1) Update configuration
- Edit `.env` (and deploy/.env) with the new `EMBEDDING_MODEL_PATH` and `EMBEDDING_DIMENSION` (e.g., 1024).
- Ensure `HF_TOKEN` is set if the model is gated.

2) Wipe vector collections
- Drop or clear the existing vector collections in Qdrant/Arango so dimensions match the new model.
- If using Qdrant: delete the collection or recreate with the new vector size.

3) Re-ingest corpus
- Run the re-index/re-ingestion script (e.g., `scripts/reindex_corpus.sh`) to repopulate vectors with the new embedding size.
- Confirm collection dimensions match `EMBEDDING_DIMENSION` before resuming production traffic.
