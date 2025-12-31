# Performance & Observability Guardrails

This pass adds lightweight guardrails without changing pipeline behavior.

## Context budgeting
- Code: `src/shared/context_budget.py`
- Provides per-task soft/hard limits (tokens) and rough token estimation.
- Budgets are generous by default (e.g., extract/kg 64k soft / 128k hard) and constrain to model.max_context when set.
- Validation: Model configs are validated on import; budgets can be checked to warn/block on clearly oversized inputs.

## Telemetry
- LLM calls in `src/orchestrator/nodes.py` now log structured payloads:
  - `model_id`, `task_type`, `tokens_in_est`, `tokens_out_est`, `latency_ms`, `kv_policy`
- Vision calls log model_id, task_type, latency, kv_policy.
- Purpose: detect runaway context/latency and tie back to model/KV settings.

## Model registry
- Code: `src/shared/model_registry.py`
- Source of truth for model ids, provider, purpose, quantization/kv hints, endpoint envs.
- Validates missing/invalid context on import to fail fast.

## How to use the guardrails
- Use `get_context_budget(task, model_cfg)` and `estimate_tokens(text)` to warn/block before sending a prompt.
- Telemetry is emitted via logger payloads; aggregate in your log stack to monitor tokens, latency, and model usage.

No router or context rewriting is added in this step; only budgeting helpers and telemetry hooks. Guardrail defaults are intentionally conservative to avoid breaking existing flows. 
