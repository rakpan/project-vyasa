# Model Inventory (Auto-Derived)

This inventory lists every model reference found in the repository as of this scan. Unknown fields are noted explicitly. Providers/runtimes are inferred from docker-compose, env defaults, and call sites.

## Functional Model Inventory

| Role | Model Path (HF) | Service | Purpose |
| --- | --- | --- | --- |
| Brain | nvidia/Llama-3_3-Nemotron-Super-49B-v1_5 | SGLang (30000) | Complex reasoning & routing |
| Worker | nvidia/Llama-3_3-Nemotron-Super-49B-v1_5 | SGLang (30001) | Fast JSON extraction (same model as Brain) |
| Vision | Qwen/Qwen2-VL-7B-Instruct | SGLang (30002) | Vision OCR/captioning |
| Embedder | nvidia/nv-embedqa-e5-v5 | Transformers (30010) | High-recall semantic search (1024 dims) |

| model_id | purpose | provider/runtime | quantization / KV policy | context (default / max) | where configured | where used |
| --- | --- | --- | --- | --- | --- | --- |
| `nvidia/Llama-3_3-Nemotron-Super-49B-v1_5` (Brain) | Critic / high-level reasoning | SGLang server (`deploy/docker-compose.yml` service `cortex-brain`) | `--quantization int8`, `--mem-fraction-static 0.50`, `--tp-size 1`, `--max-running-requests 3`, `--context-length 32768`; KV policy not otherwise specified | Context length: 32768 tokens (explicit limit, Nemotron supports up to 128K but 32K is safer for DGX Spark) | `deploy/.env.example` (`TEXT_MODEL_ID`), `src/shared/config.py` (`TEXT_MODEL_ID`), `deploy/docker-compose.yml` command | `src/orchestrator/nodes.py` (critic_node, entity resolution), `src/orchestrator/synthesis_service.py` (entity resolution), network via `get_brain_url()` |
| `nvidia/Llama-3_3-Nemotron-Super-49B-v1_5` (Worker) | Extraction / Cartographer | SGLang server (`cortex-worker`) | `--quantization int8`, `--mem-fraction-static 0.50`, `--tp-size 1`, `--max-running-requests 3`, `--context-length 32768`; KV policy otherwise unspecified | Context length: 32768 tokens (explicit limit, Nemotron supports up to 128K but 32K is safer for DGX Spark) | `deploy/.env.example` (`TEXT_MODEL_ID`), `src/shared/config.py` (`TEXT_MODEL_ID`), `deploy/docker-compose.yml` command | `src/orchestrator/nodes.py` (cartographer_node), network via `get_worker_url()`. Note: Same model as Brain, different service for redundancy. Optimized for DGX Spark with increased mem-fraction and concurrency (49B model has smaller footprint than 70B). |
| `Qwen/Qwen2-VL-7B-Instruct` (Vision) | Vision OCR/captioning | SGLang server (`cortex-vision`) | `--quantization int8`, `--mem-fraction-static 0.75`, `--tp-size 1`, `--max-running-requests 2`, `--context-length 8192`; KV policy not otherwise specified | Context limit: 8192 tokens (safety limit for OCR-heavy or high-resolution pages) | `deploy/.env.example` (`VISION_MODEL_ID`), `src/shared/config.py` (`VISION_MODEL_ID`), `deploy/docker-compose.yml` command | `src/orchestrator/nodes.py` (vision_node), network via `get_vision_url()`. Note: Vision runs only via triage (not every page). Single-GPU default (tp-size=1). Context-length cap prevents pathological workloads. |
| `nvidia/Llama-3_3-Nemotron-Super-49B-v1_5` (Prose Writing) | Prose / drafting | SGLang server (`cortex-brain`) | Same as Brain (see above) | Same as Brain (32768 tokens) | Uses `TEXT_MODEL_ID` via Brain service | `src/orchestrator/nodes.py` (route_to_expert with PROSE_WRITING), `src/orchestrator/supervisor.py` (draft_content). Note: Prose writing routes to TEXT model (Brain) with draft prompt profile, no separate drafter service. |
| `nvidia/nv-embedqa-e5-v5` (embedder) | Text embeddings | Sentence-Transformers (local) | No quantization (simple, deterministic service); KV not applicable | Max sequence per model default (not specified). Chunking responsibility: upstream services must chunk text before embedding. | `deploy/.env.example` (`EMBEDDER_MODEL_ID`), `src/embedder/app.py` (`EMBEDDER_MODEL_ID` env), `deploy/docker-compose.yml` service `embedder` | `src/embedder/app.py` endpoints `/embed`, `/embeddings`; referenced by console via `SENTENCE_TRANSFORMER_URL`. Embedding dimension: 1024 (configured via `EMBEDDING_DIMENSION`). Dimension guardrail enforced by orchestrator startup validation. |
| `nvidia/llama-3.2-nv-embedqa-1b-v2` (optional) | Text embeddings (remote) | NVIDIA API (frontend-configurable) | Not specified | Not specified | Frontend localStorage (`src/console/components/settings-modal.tsx`, `.../configureTab.tsx`) | Console embeddings UI toggles; no backend config observed |
| Vision endpoint payload model (same as Vision above) | Vision inference call payload | SGLang | Uses `VISION_MODEL_PATH` in request body | Context not specified | `src/orchestrator/nodes.py` vision_node | `vision_node` request JSON includes model |

## Provider/runtime reference
- **SGLang servers**: configured via `deploy/docker-compose.yml` (`cortex-brain`, `cortex-worker`, `cortex-vision`); env defaults in `deploy/.env.example`; model names in `src/shared/config.py`. Models download from **HuggingFace Hub** using `HF_TOKEN` environment variable. Model paths use HuggingFace Hub format (e.g., `nvidia/Llama-3_3-Nemotron-Super-49B-v1_5`) or local filesystem paths.
- **Sentence-Transformers (Embedder)**: `src/embedder/app.py`, `deploy/docker-compose.yml` service `embedder`. Downloads from **HuggingFace Hub** via `sentence-transformers` library (uses `HF_TOKEN` if available).
- **Optional NVIDIA embeddings** (frontend-only config): `src/console/components/settings-modal.tsx`, `src/console/components/tabs/ConfigureTab.tsx`.

## Model Download Sources

All models are downloaded automatically on first container start:

- **SGLang models** (Brain, Worker, Vision): Download from [HuggingFace Hub](https://huggingface.co/) using the `HF_TOKEN` environment variable. Use canonical variables: `TEXT_MODEL_ID` (for Brain and Worker), `VISION_MODEL_ID` (for Vision). Model paths should be HuggingFace Hub paths (e.g., `nvidia/Llama-3_3-Nemotron-Super-49B-v1_5`) or local filesystem paths.
- **Embedder**: Downloads from HuggingFace Hub via `sentence-transformers` library. Default model is `nvidia/nv-embedqa-e5-v5`.

**Authentication**: Set `HF_TOKEN` in your `.env` file (get token from https://huggingface.co/settings/tokens) to download gated models or avoid rate limits.

## Notes on unknowns
- KV cache precision/paging beyond SGLang CLI flags is not specified.
- Max context for Brain/Vision not declared; defaults depend on SGLang/model configs.
- No reranker models or external API LLMs are configured server-side in this scan.
