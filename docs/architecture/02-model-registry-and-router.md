# Model Registry (current state)

This registry provides a **single source of truth for model identifiers and semantic purpose only**. It does NOT control deployment optimizations such as quantization, attention backend, memory fraction, tensor parallelism, or context length—these are deployment concerns owned by `deploy/docker-compose.yml`.

**Registry Authority:**
- ✅ Model IDs (which model to load)
- ✅ Semantic purpose (what the model is used for)
- ✅ Provider/runtime type (SGLang, Ollama, sentence-transformers)
- ✅ Endpoint configuration (which service URL to call)

**NOT Registry Authority (deployment concerns):**
- ❌ Quantization (int8, fp4, mxfp4, etc.) — configured in docker-compose command flags
- ❌ KV cache policy (mem-fraction-static, etc.) — configured in docker-compose command flags
- ❌ Tensor parallelism (tp-size) — configured in docker-compose command flags
- ❌ Context length limits — configured in docker-compose command flags
- ❌ Memory fraction — configured in docker-compose command flags

Routing logic will be layered on later.

## The Functional Router

Project Vyasa does not use a proxy-based router (like LiteLLM). Instead, it uses Orchestrator-Native Routing.

- **Logic**: The LangGraph state machine decides which model "Expert" handles a specific State transition.
- **Benefit**: This minimizes network hops and allows for "Expert-Specific" prompt engineering (e.g., using SGLang regex constraints on the Worker but not on the Brain).

## Location
- Code: `src/shared/model_registry.py`
- Backed by existing env defaults from `src/shared/config.py` and docker-compose.

## Schema
```python
@dataclass(frozen=True)
class ModelConfig:
    key: str                    # Registry key (e.g., "brain", "worker")
    model_id: str               # Model identifier (authoritative)
    provider: str               # Runtime provider (e.g., "sglang", "ollama")
    purpose: str                # Semantic purpose (authoritative)
    default_context: Optional[int]  # Context hint (non-authoritative, for reference only)
    max_context: Optional[int]     # Context hint (non-authoritative, for reference only)
    kv_policy: Optional[str]       # Deployment hint (non-authoritative, see docker-compose)
    quantization: Optional[str]    # Deployment hint (non-authoritative, see docker-compose)
    endpoint_env: Optional[str]     # Endpoint configuration (authoritative)
```

**Field Authority:**
- **Authoritative fields**: `model_id`, `purpose`, `provider`, `endpoint_env` — these are enforced by the registry
- **Non-authoritative fields**: `quantization`, `kv_policy`, `default_context`, `max_context` — these are deployment hints only, actual values come from docker-compose.yml

Validation runs at import:
- missing `model_id` -> error
- invalid context lengths -> error (if provided, but not enforced at runtime)

## Current entries (from registry)

**Authoritative fields only** (quantization/optimization details are in docker-compose.yml):

- `brain`: 
  - `model_id`: `TEXT_MODEL_ID` (default `nvidia/Llama-3_3-Nemotron-Super-49B-v1_5`)
  - `provider`: `sglang`
  - `purpose`: `critic / high-level reasoning`
  - `endpoint_env`: `BRAIN_URL`
  - Deployment optimizations (quantization, kv_policy, tp-size, etc.) are configured in `deploy/docker-compose.yml` service `cortex-brain`

- `worker`: 
  - `model_id`: `TEXT_MODEL_ID` (same as Brain - default `nvidia/Llama-3_3-Nemotron-Super-49B-v1_5`)
  - `provider`: `sglang`
  - `purpose`: `extraction / cartographer`
  - `endpoint_env`: `WORKER_URL`
  - Note: Both Brain and Worker use the same `TEXT_MODEL_ID` (same model, different services for redundancy, optimized for DGX Spark)
  - Deployment optimizations (quantization, kv_policy, tp-size, context-length, etc.) are configured in `deploy/docker-compose.yml` service `cortex-worker`

- `vision`: 
  - `model_id`: `VISION_MODEL_ID` (default `Qwen/Qwen2-VL-7B-Instruct`)
  - `provider`: `sglang`
  - `purpose`: `vision / OCR`
  - `endpoint_env`: `VISION_URL`
  - Deployment optimizations (quantization, kv_policy, tp-size, etc.) are configured in `deploy/docker-compose.yml` service `cortex-vision`

- `embedder`: 
  - `model_id`: `EMBEDDER_MODEL_ID` (default `nvidia/nv-embedqa-e5-v5`)
  - `provider`: `sentence-transformers`
  - `purpose`: `embeddings`
  - `endpoint_env`: `SENTENCE_TRANSFORMER_URL`
  - Deployment configuration is in `deploy/docker-compose.yml` service `embedder`

Note: Prose writing (previously handled by `drafter` service) now routes to the TEXT model (Brain) via `ExpertType.PROSE_WRITING` with a draft prompt profile. No separate drafter service is required.

**Model Configuration**: Use canonical environment variables:
- `TEXT_MODEL_ID`: Used by both Brain and Worker services (default: `nvidia/Llama-3_3-Nemotron-Super-49B-v1_5`, optimized for DGX Spark)
- `VISION_MODEL_ID`: Used by Vision service (default: `Qwen/Qwen2-VL-7B-Instruct`)
- `EMBEDDER_MODEL_ID`: Used by Embedder service (default: `nvidia/nv-embedqa-e5-v5`)

**Model Download**: All SGLang and embedder models download from [HuggingFace Hub](https://huggingface.co/) on first container start. Set `HF_TOKEN` environment variable for authenticated downloads (required for some gated models). Model paths can be HuggingFace Hub paths (e.g., `nvidia/Llama-3_3-Nemotron-Super-49B-v1_5`) or local filesystem paths.

## Usage (read-only)

**Registry Usage:**
- Orchestrator nodes and synthesis resolve model IDs via `get_model_config(key).model_id` instead of hardcoded constants.
- The registry provides semantic purpose and endpoint configuration.
- **Deployment optimizations (quantization, memory, parallelism) are NOT read from the registry** — they are configured in `deploy/docker-compose.yml` and applied at container startup.

**Separation of Concerns:**
- Registry: "Which model?" and "What is it used for?"
- Docker Compose: "How is it optimized?" (quantization, memory, parallelism, context length)

## Router (opt-in)
- Code: `src/shared/model_router.py`
- Feature flag: router is disabled by default; callers can instantiate `ModelRouter(enabled=True)` or use `DEFAULT_ROUTER` and toggle `enabled`.
- Route inputs: `RouteRequest(task_type, context_needed=None, deterministic=False)`
- Example routes (when enabled):
  - `extract` / `kg` → worker
  - `qa` / `summarize` → brain
  - `adjudicate` → brain
  - `vision` → vision
  - `embeddings` / `rerank` → embedder
- When disabled, routing mirrors existing defaults (worker for extract/kg, brain for critic/adjudicate/qa/summarize, vision for vision, embedder for embeddings).

## Tests
- `src/shared/tests/test_model_router.py` exercises default vs enabled routing and example task mappings.
