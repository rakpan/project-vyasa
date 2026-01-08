# DGX Spark Runtime Runbook

## SGLang Serving Baseline (Quality-First, Stability-First)

### TEXT Model (Brain & Worker) - Identical Configuration
**Baseline values** (applied to both `cortex-brain` and `cortex-worker`):
- `--context-length 65536`: 64K context supports journal workflows (paper sections + extracted claims + instructions) without aggressive truncation. Prioritizes quality over throughput.
- `--max-running-requests 1`: Maximizes KV cache per request and simplifies scheduling for stability. Reduces contention and OOM risk.
- `--mem-fraction-static 0.50`: Conservative DGX Spark baseline, leaves headroom for OS/ArangoDB/Qdrant.
- `--quantization int8`: Balanced precision/performance, optimized for Nemotron architecture.
- `--tp-size 1`: Single tensor parallelism for stability.

**Staged Tuning Rules** (DO NOT apply without documentation and metrics):
1. **Increase `max-running-requests`** only if:
   - KV cache fill < 80%
   - Queue depth < 2
   - Zero watchdog restarts over 24h
   - Document metrics before and after change

2. **Increase `context-length` beyond 64K** only if:
   - UMA/VRAM pressure < 85%
   - Sustained KV cache headroom observed
   - No OOM events in 48h observation window

3. **Adjust `mem-fraction-static`** only if:
   - UMA utilization < 80%
   - VRAM headroom > 15% under peak load
   - Monitor for 48h after change

4. **General tuning protocol**:
   - Change ONE parameter at a time
   - Observe for 48h minimum
   - Document metrics (before/after)
   - Only then consider next parameter change

### Vision Model (cortex-vision)
**Safety configuration**:
- `--context-length 8192`: Explicit safety cap prevents pathological OCR-heavy or high-resolution page workloads
- `--tp-size 1`: Single-GPU tensor parallelism (default). Single GPU via `VISION_GPU_IDS` (default: "0")
- `--quantization int8`: Conservative quantization for vision models
- Keep vision quantization conservative and avoid experimental backends
- **Multi-GPU override**: To use multiple GPUs, set `VISION_GPU_IDS="0,1"` and update `--tp-size 2` in docker-compose.yml

## Resource Budget Targets
- **VRAM utilization**: keep < 90% per GPU under steady state. Trigger back-pressure or reduce batch sizes if sustained higher.
- **Unified Memory (UVM) utilization**: target < 85% of the 128GB pool to avoid swap/oversubscription stalls.
- **SHM**: allocate at least 16GB per model container for tokenizer and intermediate buffers.
- **Mem limits**: Brain 64GB, Worker 32GB container limits to prevent runaway UVM thrash.

## GPU / NUMA Affinity

### GPU Assignment (Single Source of Truth)

GPU assignment is controlled via environment variables in `deploy/.env`:

- **TEXT_GPU_IDS** (default: `"0"`): GPU IDs for `cortex-brain` and `cortex-worker` services
  - Both services share the same GPU assignment (service-level redundancy, same model)
  - Default: Single GPU (0) to avoid VRAM contention
  - Multi-GPU: Set comma-separated IDs (e.g., `"0,1"` for GPUs 0 and 1)

- **VISION_GPU_IDS** (default: `"0"`): GPU IDs for `cortex-vision` service (optional override)
  - Default: Single GPU (0) with tp-size=1
  - Multi-GPU override: Set comma-separated IDs (e.g., `"0,1"`) and update `--tp-size 2` in docker-compose.yml

- **EMBEDDER_GPU_IDS** (default: empty): GPU IDs for `embedder` service
  - **Default: CPU mode** (empty = no GPU) to avoid VRAM contention
  - To enable GPU: Set `EMBEDDER_GPU_IDS="0"` and uncomment GPU config in docker-compose.yml

### Default Configuration (Single GPU)

By default, all GPU services use GPU 0:
- `cortex-brain`: GPU 0 (via `TEXT_GPU_IDS=0`)
- `cortex-worker`: GPU 0 (via `TEXT_GPU_IDS=0`)
- `cortex-vision`: GPU 0 (via `VISION_GPU_IDS=0`, optional)
- `embedder`: CPU (no GPU, `EMBEDDER_GPU_IDS` empty)

**Note**: This default configuration may cause VRAM contention if all services run simultaneously. Consider:
- Disabling vision (default) to reduce GPU usage
- Using separate GPUs for different services (multi-GPU setup)

### Multi-GPU Override

To use multiple GPUs or separate GPUs for different services:

```bash
# In deploy/.env:
# Separate GPUs for TEXT and VISION services
TEXT_GPU_IDS=0          # Brain and Worker on GPU 0
VISION_GPU_IDS=1         # Vision on GPU 1
EMBEDDER_GPU_IDS=        # Embedder on CPU (default)

# Or use multiple GPUs for a single service:
TEXT_GPU_IDS=0,1         # Brain and Worker on GPUs 0 and 1 (requires tp-size adjustment)
VISION_GPU_IDS=2,3       # Vision on GPUs 2 and 3 (tp-size=2)
```

**Important**: When using multiple GPUs, ensure `tp-size` in docker-compose.yml matches the number of GPUs assigned.

### CPU Pinning

- Prefer CPU pinning to keep model processes on the same NUMA node as their GPU (see `cpuset` in compose)
- Avoid cross-NUMA chatter for Brain/Worker
- Performance cores (10-19): GPU services (cortex-brain, cortex-worker, cortex-vision)
- Efficiency cores (0-9): CPU services (graph, vector, console, orchestrator, embedder)

## Vision Service Management (Optional Accelerator)

Vision is **disabled by default** and can be enabled/disabled to reclaim GPU memory.

**Vision OFF (Default):**
```bash
docker compose up -d
```

**Turn Vision ON:**
```bash
docker compose --profile vision up -d cortex-vision
```

**Turn Vision OFF (Reclaim GPU Memory):**
```bash
docker compose stop cortex-vision
```

**Configuration:**
- Set `VISION_ENABLED=true` in `deploy/.env` to enable vision processing in orchestrator
- Vision service runs under Docker Compose profile `vision` (not started by default)
- Stopping vision immediately reclaims GPU memory (single GPU by default)
- UI toggle (`VISION_ENABLED`) reflects config/health only; it does NOT start/stop containers

## I/O Paths
- All caches and data live under `/raid/vyasa/`:
  - HuggingFace cache: `/raid/vyasa/hf_cache`
  - Model cache: `/raid/vyasa/model_cache`
  - Telemetry JSONL: `/raid/vyasa/telemetry/events.jsonl`
  - ArangoDB data: `/raid/vyasa/arangodb`
  - Qdrant data: `/raid/vyasa/qdrant`
  - Scratch: `/raid/vyasa/scratch`

## Monitoring & Metrics

### Critical Metrics to Watch
1. **KV cache fill %**: Monitor via observability endpoints. Should stay < 80% under normal load.
2. **Queue depth**: Track pending requests. Should stay < 2 for baseline stability.
3. **Watchdog restarts**: Zero restarts over 24h indicates stable operation.
4. **UMA/VRAM pressure**: 
   - UMA utilization should stay < 85%
   - VRAM headroom should be > 15% under peak load
5. **OOM events**: Any OOM indicates need to reduce context-length or mem-fraction-static

### Operational Guidance
- Watch `uma_utilization_pct` and `kv_cache_fill_pct` from the observatory; scale back context lengths or concurrency if thresholds are breached.
- Quality-first approach: prioritize journal quality (less truncation) and stability over throughput.
- Keep logs and telemetry rotated; avoid large JSONL growth on the root filesystem.
- Any tuning must be staged and documented; no aggressive concurrency increases.