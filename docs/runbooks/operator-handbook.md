# Operator Handbook

Content merged from `getting-started.md` and `user-guide.md`.

## Prerequisites
- Environment setup, .env configuration, GPU requirements

## Start/Stop/Status
- Running the stack, stopping services, checking health

## Projects and Jobs
- Creating projects, uploading documents, launching jobs

## Troubleshooting
- Common errors, logs to inspect, how to restart failing services

## Service Configuration Notes

### Vision Service (cortex-vision)
- **Context-length cap**: 8192 tokens (safety limit)
  - Prevents pathological workloads from OCR-heavy or high-resolution pages
  - Configured in `deploy/docker-compose.yml` via `--context-length 8192`
  - If Vision service fails with context errors, consider reducing image resolution or splitting large pages

### Embedder Service
- **Embedding dimension**: 1024 (for nvidia/nv-embedqa-e5-v5)
  - Dimension guardrail enforced by orchestrator startup validation
  - If dimension mismatch detected, orchestrator health check will return 503
  - Check Qdrant collection dimensions match `EMBEDDING_DIMENSION=1024`
- **Chunking responsibility**: Upstream services (orchestrator) must chunk text before embedding
  - Embedder service does not perform chunking
  - Text should be pre-chunked to appropriate sizes before calling `/embed` or `/embeddings`
- **No quantization or performance tuning**: Service remains simple and deterministic

