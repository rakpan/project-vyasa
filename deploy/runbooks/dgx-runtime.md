# DGX Spark Runtime Runbook

## Resource Budget Targets
- **VRAM utilization**: keep < 90% per GPU under steady state. Trigger back-pressure or reduce batch sizes if sustained higher.
- **Unified Memory (UVM) utilization**: target < 85% of the 128GB pool to avoid swap/oversubscription stalls.
- **SHM**: allocate at least 16GB per model container for tokenizer and intermediate buffers.
- **Mem limits**: Brain 64GB, Worker 32GB container limits to prevent runaway UVM thrash.

## GPU / NUMA Affinity
- Cortex-BRAIN pinned to GPU 0, Cortex-WORKER to GPU 1. Drafter (Ollama) shares GPU 0; Embedder shares GPU 1.
- Prefer CPU pinning to keep model processes on the same NUMA node as their GPU (see `cpuset` in compose). Avoid cross-NUMA chatter for Brain/Worker.

## I/O Paths
- All caches and data live under `/raid/vyasa/`:
  - HuggingFace cache: `/raid/vyasa/hf_cache`
  - Model cache: `/raid/vyasa/model_cache`
  - Telemetry JSONL: `/raid/vyasa/telemetry/events.jsonl`
  - ArangoDB data: `/raid/vyasa/arangodb`
  - Qdrant data: `/raid/vyasa/qdrant`
  - Ollama data: `/raid/vyasa/ollama`
  - Scratch: `/raid/vyasa/scratch`

## Operational Guidance
- Watch `uma_utilization_pct` and `kv_cache_fill_pct` from the observatory; scale back context lengths or concurrency if thresholds are breached.
- Favor FP8/INT4 for Worker where quality allows; keep Brain at the minimum precision that passes acceptance.
- Keep logs and telemetry rotated; avoid large JSONL growth on the root filesystem.
