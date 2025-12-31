# Model Registry (current state)

This registry provides a single source of truth for model identifiers and metadata without changing runtime behavior. Routing logic will be layered on later.

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
    key: str
    model_id: str
    provider: str
    purpose: str
    default_context: Optional[int]
    max_context: Optional[int]
    kv_policy: Optional[str]
    quantization: Optional[str]
    endpoint_env: Optional[str]
```

Validation runs at import:
- missing `model_id` -> error
- invalid context lengths -> error

## Current entries (from registry)
- `brain`: model_id from `BRAIN_MODEL_NAME` (default `meta-llama/Llama-3.3-70B-Instruct` from HuggingFace Hub), provider `sglang`, purpose critic/reasoning, quantization/kv policy from compose comments (`mxfp4`, mem-fraction-static), endpoint env `BRAIN_URL`.
- `worker`: model_id from `WORKER_MODEL_NAME` (default `nvidia/Llama-3_3-Nemotron-Super-49B-v1_5` from HuggingFace Hub), provider `sglang`, purpose extraction/cartographer, default_context 16384 (compose flag), quantization `fp4`, endpoint env `WORKER_URL`.
- `vision`: model_id from `VISION_MODEL_NAME` (default `Qwen/Qwen2-VL-72B-Instruct` from HuggingFace Hub), provider `sglang`, purpose vision/OCR, quantization `int8`, endpoint env `VISION_URL`.
- `embedder`: `all-MiniLM-L6-v2` (from HuggingFace Hub via sentence-transformers), provider sentence-transformers, purpose embeddings, endpoint env `SENTENCE_TRANSFORMER_URL`.
- `drafter`: model id not set in repo (Ollama), provider `ollama`, purpose prose/drafting, endpoint env `DRAFTER_URL`. Uses Ollama's model registry (separate from HuggingFace).

**Model Download**: All SGLang and embedder models download from [HuggingFace Hub](https://huggingface.co/) on first container start. Set `HF_TOKEN` environment variable for authenticated downloads (required for some gated models). Model paths can be HuggingFace Hub paths (e.g., `meta-llama/Llama-3.3-70B-Instruct`) or local filesystem paths.

## Usage (read-only)
- Orchestrator nodes and synthesis now resolve model IDs via `get_model_config(key).model_id` instead of hardcoded constants.
- No runtime behavior changes; endpoints, quantization flags, and compose settings remain as before.

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
