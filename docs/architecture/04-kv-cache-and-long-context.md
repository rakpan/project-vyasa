# KV Cache & Long Context Guardrails

Scope: non-invasive defaults with runtime-specific hints. No pipeline rewrite.

## Runtime detection
- Code: `src/shared/runtime.py`
- Detects provider → runtime (`sglang`, `ollama`, `tensorrt-llm`, `vllm`), used to surface hints only.

## Context bands (task defaults)
- `extract`: 8k–32k
- `kg`: 16k–64k
- `adjudicate`: 32k–128k
- `narrative`: 16k–64k
- Location: `src/shared/runtime.py` (`CONTEXT_BANDS`)

## KV policies
- Registry KV hints remain the source (see `src/shared/model_registry.py`).
- `kv_policy_for(model)` returns registry hint or runtime-specific default (SGLang: mem-fraction-static via compose flags).
- Quantization: existing compose flags (e.g., fp4/mxfp4/int8) remain unchanged; router/registry supply model ids only.

## Concurrency hints
- `concurrency_limit_for(context_len)` suggests reducing parallelism at higher contexts (>=128k → 1, >=64k → 2, >=32k → 4).
- Callers can use this to gate long-context fan-out; not enforced globally.

## Behavior
- No changes to request shapes or max context; this adds helpers and documentation only.
- Feature flags and routing remain opt-in; KV settings stay as defined in docker-compose.
