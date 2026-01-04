# Nodes Module Split (Consolidated)

Single reference for breaking down `src/orchestrator/nodes/nodes.py`. Backward-compat imports remain via `nodes/__init__.py`.

## Current Status
- `nodes.py` partially split; domain modules exist (`synthesis.py`, `base.py`, helpers), but many nodes still live in the shim.
- Compatibility path is `from src.orchestrator.nodes import ...`; keep re-exports until all imports migrate.
- High-coupling nodes (cartographer, critic, synthesizer, saver) and helpers still drive most workflow wiring.

## Planned Moves (order of execution)
1) **Helpers (low risk):** `route_to_expert`, `check_kv_backpressure`, `call_expert_with_fallback` → `utils/routing.py`; `hydrate_project_context`/project service → `utils/context.py`; knowledge helpers → `utils/knowledge.py`. Update shim exports.
2) **Well-covered nodes:** `cartographer_node` → `cartography.py`; `synthesizer_node` already in `synthesis.py`; `critic_node` → `governance/critic.py`. Run cartographer/critic/synth tests.
3) **Persistence/governance:** `saver_node` → `persistence.py` (add citation validation + Arango failure tests); `tone_validator_node` → `governance/tone.py`.
4) **Minimal coverage:** `vision_node` → `vision.py`; `artifact_registry_node` → `governance/artifacts.py`.
5) **Uncovered tail:** `lead_counsel_node`/`logician_node` → `strategy/`; `reframing_node`/`failure_cleanup_node` → `governance/`. Remove `nodes.py` shim after imports migrate.

## Coupling Notes
- **High coupling:** cartographer, critic, synthesizer, saver (multiple services + globals). Move with tests in place; watch for Arango/PromptRegistry cycles.
- **Medium coupling:** vision, artifact_registry, reframing, routing helpers (LLM + metrics).
- **Low coupling:** tone validator, lead_counsel, logician (pure/near-pure logic).

## Test Coverage Checklist (add before moves where missing)
- **Vision:** image selection, context build, error handling.
- **Artifacts:** table registration, precision contract, manifest flags.
- **Persistence:** saver citation validation failure; Arango connection failure.
- **Strategy:** lead_counsel triage paths; logician math sandbox/LaTeX/error.
- **Reframing:** proposal generation, signoff logic, conflict integration.
- **Failure cleanup:** job status update, error propagation, telemetry emission.

## Run/Test after each slice
- Slice-specific suites: `pytest src/tests/unit/orchestrator/test_cartographer*`, `test_synthesizer*`, `test_conflict*`, `test_tone*`, `test_manifest*`, etc.
- Full regression: `pytest src/tests/unit/orchestrator/ -v` then integration `test_pipeline_e2e.py`.
