# Project Vyasa Architecture Overview

## What this system does
- Multi-model, multi-workload research engine (extraction, KG, QA, vision, embedding).
- Context is treated as a budget; KV cache is the primary bottleneck.
- Determinism is prioritized for structured tasks; high-quality generation remains available.

## High-level diagram (mermaid)
```mermaid
flowchart LR
    Console(Next.js Console) -->|HTTP| Orchestrator(API + LangGraph)
    Orchestrator -->|Worker (extract)| CortexWorker[SGLang Worker]
    Orchestrator -->|Brain (critic/QA)| CortexBrain[SGLang Brain]
    Orchestrator -->|Vision| CortexVision[SGLang Vision]
    Orchestrator -->|Draft| Drafter[Ollama]
    Orchestrator --> ArangoDB[(ArangoDB)]
    Orchestrator --> Qdrant[(Qdrant)]
    Orchestrator --> Embedder[Sentence-Transformers]
```

## Quickstart pointers
- Model registry: `src/shared/model_registry.py`
- Router (opt-in): `src/shared/model_router.py`
- Context budget: `src/shared/context_budget.py`
- Context packing (opt-in for extraction): `src/orchestrator/context_packer.py`
- Runtime/KV helpers: `src/shared/runtime.py`
- Telemetry hooks: `src/orchestrator/nodes.py`
- Eval harness: `src/tests/eval/test_eval_harness.py`

## Docs map
- [01-model-inventory](01-model-inventory.md)
- [02-model-registry-and-router](02-model-registry-and-router.md)
- [03-context-packing-and-rag](03-context-packing-and-rag.md)
- [04-resource-optimization](04-resource-optimization.md)
- [05-telemetry-and-observability](05-telemetry-and-observability.md)
- [06-evaluation-and-regression](06-evaluation-and-regression.md)
