# Model Inventory (Auto-Derived)

This inventory lists every model reference found in the repository as of this scan. Unknown fields are noted explicitly. Providers/runtimes are inferred from docker-compose, env defaults, and call sites.

## Functional Model Inventory

| Role | Model Path (HF) | Service | Purpose |
| --- | --- | --- | --- |
| Brain | meta-llama/Llama-3.3-70B-Instruct | SGLang (30000) | Complex reasoning & routing |
| Worker | meta-llama/Llama-3.3-70B-Instruct | SGLang (30001) | Fast JSON extraction (same model as Brain) |
| Vision | Qwen/Qwen2-VL-7B-Instruct | SGLang (30002) | Vision OCR/captioning |
| Embedder | nvidia/nv-embedqa-e5-v5 | Transformers (30010) | High-recall semantic search (1024 dims) |
| Drafter | mistral-nemo | Ollama (11435) | Research prose & synthesis |

| model_id | purpose | provider/runtime | quantization / KV policy | context (default / max) | where configured | where used |
| --- | --- | --- | --- | --- | --- | --- |
| `meta-llama/Llama-3.3-70B-Instruct` (Brain) | Critic / high-level reasoning | SGLang server (`deploy/docker-compose.yml` service `cortex-brain`) | `--quantization int8`, `--mem-fraction-static 0.45`, `--tp-size 1`, `--max-running-requests 2`; KV policy not otherwise specified | Context length not specified (SGLang default); max not declared | `deploy/.env.example` (`TEXT_MODEL_ID`), `src/shared/config.py` (`TEXT_MODEL_ID`), `deploy/docker-compose.yml` command | `src/orchestrator/nodes.py` (critic_node, entity resolution), `src/orchestrator/synthesis_service.py` (entity resolution), network via `get_brain_url()` |
| `meta-llama/Llama-3.3-70B-Instruct` (Worker) | Extraction / Cartographer | SGLang server (`cortex-worker`) | `--quantization fp4`, `--mem-fraction-static 0.70`, `--tp-size 1`, `--max-running-requests 4`, `--context-length 16384`; KV policy otherwise unspecified | Default 16k from command; max not declared | `deploy/.env.example` (`TEXT_MODEL_ID`), `src/shared/config.py` (`TEXT_MODEL_ID`), `deploy/docker-compose.yml` command | `src/orchestrator/nodes.py` (cartographer_node), network via `get_worker_url()`. Note: Same model as Brain, different service for redundancy. |
| `Qwen/Qwen2-VL-7B-Instruct` (Vision) | Vision OCR/captioning | SGLang server (`cortex-vision`) | `--quantization int8`, `--mem-fraction-static 0.75`, `--tp-size 2`, `--max-running-requests 2`, `--context-length 8192`; KV policy not otherwise specified | Context limit: 8192 tokens (safety limit for OCR-heavy or high-resolution pages) | `deploy/.env.example` (`VISION_MODEL_ID`), `src/shared/config.py` (`VISION_MODEL_ID`), `deploy/docker-compose.yml` command | `src/orchestrator/nodes.py` (vision_node), network via `get_vision_url()`. Note: Vision runs only via triage (not every page). Context-length cap prevents pathological workloads. |
| Drafter (Ollama model not specified) | Prose / drafting | Ollama container (`drafter` service) | Quantization/KV not specified; uses `DRAFTER_IMAGE` | Context not specified | `deploy/.env.example` (`DRAFTER_IMAGE`, `DRAFTER_GPU_IDS`), `deploy/docker-compose.yml` service `drafter` | `src/orchestrator/config.py` URLs, `src/orchestrator/supervisor.py` draft placeholders; actual model name not set in repo |
| `nvidia/nv-embedqa-e5-v5` (embedder) | Text embeddings | Sentence-Transformers (local) | No quantization (simple, deterministic service); KV not applicable | Max sequence per model default (not specified). Chunking responsibility: upstream services must chunk text before embedding. | `deploy/.env.example` (`EMBEDDER_MODEL_ID`), `src/embedder/app.py` (`EMBEDDER_MODEL_ID` env), `deploy/docker-compose.yml` service `embedder` | `src/embedder/app.py` endpoints `/embed`, `/embeddings`; referenced by console via `SENTENCE_TRANSFORMER_URL`. Embedding dimension: 1024 (configured via `EMBEDDING_DIMENSION`). Dimension guardrail enforced by orchestrator startup validation. |
| `nvidia/llama-3.2-nv-embedqa-1b-v2` (optional) | Text embeddings (remote) | NVIDIA API (frontend-configurable) | Not specified | Not specified | Frontend localStorage (`src/console/components/settings-modal.tsx`, `.../configureTab.tsx`) | Console embeddings UI toggles; no backend config observed |
| Vision endpoint payload model (same as Vision above) | Vision inference call payload | SGLang | Uses `VISION_MODEL_PATH` in request body | Context not specified | `src/orchestrator/nodes.py` vision_node | `vision_node` request JSON includes model |

## Provider/runtime reference
- **SGLang servers**: configured via `deploy/docker-compose.yml` (`cortex-brain`, `cortex-worker`, `cortex-vision`); env defaults in `deploy/.env.example`; model names in `src/shared/config.py`. Models download from **HuggingFace Hub** using `HF_TOKEN` environment variable. Model paths use HuggingFace Hub format (e.g., `meta-llama/Llama-3.3-70B-Instruct`).
- **Ollama (Drafter)**: `deploy/docker-compose.yml` service `drafter`; model not defined in repo. Uses Ollama's own model registry (separate from HuggingFace).
- **Sentence-Transformers (Embedder)**: `src/embedder/app.py`, `deploy/docker-compose.yml` service `embedder`. Downloads from **HuggingFace Hub** via `sentence-transformers` library (uses `HF_TOKEN` if available).
- **Optional NVIDIA embeddings** (frontend-only config): `src/console/components/settings-modal.tsx`, `src/console/components/tabs/ConfigureTab.tsx`.

## Model Download Sources

All models are downloaded automatically on first container start:

- **SGLang models** (Brain, Worker, Vision): Download from [HuggingFace Hub](https://huggingface.co/) using the `HF_TOKEN` environment variable. Use canonical variables: `TEXT_MODEL_ID` (for Brain and Worker), `VISION_MODEL_ID` (for Vision). Model paths should be HuggingFace Hub paths (e.g., `meta-llama/Llama-3.3-70B-Instruct`) or local filesystem paths.
- **Embedder**: Downloads from HuggingFace Hub via `sentence-transformers` library. Default model is `all-MiniLM-L6-v2`.
- **Drafter (Ollama)**: Uses Ollama's model registry (not HuggingFace). Models are pulled via Ollama CLI/API when needed.

**Authentication**: Set `HF_TOKEN` in your `.env` file (get token from https://huggingface.co/settings/tokens) to download gated models or avoid rate limits.

## Notes on unknowns
- KV cache precision/paging beyond SGLang CLI flags is not specified.
- Max context for Brain/Vision not declared; defaults depend on SGLang/model configs.
- Drafter model/tag and quantization are not set in codebase.
- No reranker models or external API LLMs are configured server-side in this scan.
