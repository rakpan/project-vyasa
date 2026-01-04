# Nodes.py Public API Inventory

**Generated:** Pre-refactor scan for `src/orchestrator/nodes/nodes.py` decomposition  
**File:** `src/orchestrator/nodes/nodes.py` (2361 lines)

## Summary

Total exported symbols: **17 node functions + 5 helper functions + 3 constants + 1 module-level emitter**

---

## A) Node Entrypoints (LangGraph Workflow Nodes)

### 1. `cartographer_node`
- **Type:** Node entrypoint
- **Import Sites:**
  - `src/orchestrator/workflow.py:14` (workflow graph)
  - `src/orchestrator/nodes/__init__.py:11` (package export)
  - `src/tests/unit/orchestrator/test_prompt_metadata_thread.py:23`
  - `src/tests/unit/orchestrator/test_nodes_use_prompt_registry.py:15`
  - `src/tests/unit/orchestrator/test_phase_transitions.py:17`
  - `src/tests/unit/orchestrator/test_context_injection.py:252`
  - `src/tests/unit/orchestrator/test_cartographer_rag_flow.py:16`
  - `src/tests/unit/orchestrator/test_cartographer_schema.py:10`
  - `src/tests/unit/test_nodes.py:14`
  - `src/tests/unit/test_resilience.py:11`
  - `src/tests/integration/test_pipeline_e2e.py:19`
- **Usage:** Primary extraction node, called first after vision
- **Dependencies:** Qdrant, PromptRegistry, Arango (via ProjectService)

### 2. `critic_node`
- **Type:** Node entrypoint
- **Import Sites:**
  - `src/orchestrator/workflow.py:15` (workflow graph)
  - `src/orchestrator/nodes/__init__.py:12` (package export)
  - `src/tests/unit/orchestrator/test_prompt_metadata_thread.py:24`
  - `src/tests/unit/orchestrator/test_nodes_use_prompt_registry.py:16`
  - `src/tests/unit/orchestrator/test_phase_transitions.py:18`
  - `src/tests/unit/orchestrator/test_context_injection.py:270`
  - `src/tests/unit/orchestrator/test_conflict_determinism.py:22`
  - `src/tests/unit/orchestrator/test_conflict_report_logic.py:16`
- **Usage:** Validation gate, called after cartographer/lead_counsel/logician
- **Dependencies:** Arango (conflict detection), PromptRegistry

### 3. `synthesizer_node`
- **Type:** Node entrypoint
- **Import Sites:**
  - `src/orchestrator/workflow.py:20` (workflow graph)
  - `src/orchestrator/nodes/__init__.py:17` (package export)
  - `src/tests/unit/orchestrator/test_prompt_metadata_thread.py:25`
  - `src/tests/unit/orchestrator/test_nodes_use_prompt_registry.py:17`
  - `src/tests/unit/orchestrator/test_phase_transitions.py:19`
  - `src/tests/unit/orchestrator/test_context_injection.py:261`
  - `src/tests/unit/orchestrator/test_synthesizer_citation_integrity.py:10`
  - `src/tests/unit/test_tone_rewrite_integration.py:4`
- **Usage:** Manuscript generation, called after critic passes
- **Dependencies:** PromptRegistry, CitationIntegrity validator

### 4. `vision_node`
- **Type:** Node entrypoint
- **Import Sites:**
  - `src/orchestrator/workflow.py:22` (workflow graph)
  - `src/orchestrator/nodes/__init__.py:18` (package export)
- **Usage:** Image analysis, entry point of workflow
- **Dependencies:** Vision service (Qwen-VL)

### 5. `saver_node`
- **Type:** Node entrypoint
- **Import Sites:**
  - `src/orchestrator/workflow.py:19` (workflow graph)
  - `src/orchestrator/nodes/__init__.py:16` (package export)
  - `src/tests/unit/orchestrator/test_phase_transitions.py:19`
  - `src/tests/unit/test_saver_manifest_integration.py:6`
  - `src/tests/integration/test_pipeline_e2e.py:128`
- **Usage:** Persistence, final node before END
- **Dependencies:** Arango (extraction persistence), ManifestBuilder

### 6. `artifact_registry_node`
- **Type:** Node entrypoint
- **Import Sites:**
  - `src/orchestrator/workflow.py:17` (workflow graph)
  - `src/orchestrator/nodes/__init__.py:14` (package export)
  - `src/tests/unit/orchestrator/test_manifest_contract.py:10`
- **Usage:** Table artifact registration, called after tone_guard
- **Dependencies:** ManifestBuilder, PrecisionContract validator

### 7. `tone_validator_node`
- **Type:** Node entrypoint
- **Import Sites:**
  - `src/orchestrator/workflow.py:18` (workflow graph)
  - `src/orchestrator/nodes/__init__.py:15` (package export)
- **Usage:** Final tone validation, called after artifact_registry
- **Dependencies:** ToneGuard

### 8. `lead_counsel_node`
- **Type:** Node entrypoint
- **Import Sites:**
  - `src/orchestrator/workflow.py:23` (workflow graph)
  - `src/orchestrator/nodes/__init__.py:19` (package export)
- **Usage:** Strategic triage (summary vs detail), optional path
- **Dependencies:** None (pure logic)

### 9. `logician_node`
- **Type:** Node entrypoint
- **Import Sites:**
  - `src/orchestrator/workflow.py:24` (workflow graph)
  - `src/orchestrator/nodes/__init__.py:20` (package export)
- **Usage:** Mathematical autoformalization, optional path
- **Dependencies:** MathSandbox

### 10. `reframing_node`
- **Type:** Node entrypoint
- **Import Sites:**
  - `src/orchestrator/workflow.py:16` (workflow graph)
  - `src/orchestrator/nodes/__init__.py:13` (package export)
- **Usage:** Conflict resolution proposal, called when critic fails
- **Dependencies:** Arango (conflict report storage)

### 11. `failure_cleanup_node`
- **Type:** Node entrypoint
- **Import Sites:**
  - `src/orchestrator/workflow.py:21` (workflow graph)
  - `src/orchestrator/nodes/__init__.py:25` (package export)
- **Usage:** Terminal failure handler, marks job failed
- **Dependencies:** JobManager (update_job_status)

---

## B) Helper Functions (Exported for Testing/Mocking)

### 12. `route_to_expert`
- **Type:** Helper (routing logic)
- **Import Sites:**
  - `src/orchestrator/nodes/__init__.py:21` (package export)
  - `src/orchestrator/api/manuscript.py:22`
  - `src/orchestrator/api/knowledge.py:36`
  - `src/tests/unit/orchestrator/test_prompt_metadata_thread.py:175`
  - `src/tests/unit/orchestrator/test_nodes_use_prompt_registry.py:81`
- **Usage:** Routes node to appropriate expert service (Worker/Brain/Vision)
- **Dependencies:** ExpertType enum, NODE_EXPERT_MAP

### 13. `call_expert_with_fallback`
- **Type:** Helper (LLM call wrapper)
- **Import Sites:**
  - `src/orchestrator/nodes/__init__.py:22` (package export)
  - `src/orchestrator/api/manuscript.py:22`
  - `src/orchestrator/api/knowledge.py:36`
  - Multiple test files (mocked extensively)
- **Usage:** Calls expert with fallback logic and backpressure handling
- **Dependencies:** LLM client, KV cache metrics, ExpertType

### 14. `hydrate_project_context`
- **Type:** Helper (state hydration)
- **Import Sites:**
  - `src/orchestrator/nodes/__init__.py:45` (package export)
  - Used internally by all major nodes
- **Usage:** Fetches ProjectConfig from DB and injects into state
- **Dependencies:** ProjectService, Arango

### 15. `validate_state_schema`
- **Type:** Helper (state validation)
- **Import Sites:**
  - Used internally by all nodes (not exported)
- **Usage:** Ensures required state fields exist
- **Dependencies:** None (pure validation)

### 16. `select_images_for_vision`
- **Type:** Helper (vision preprocessing)
- **Import Sites:**
  - `src/orchestrator/nodes/__init__.py:26` (package export)
- **Usage:** Selects images for vision node processing
- **Dependencies:** None (pure logic)

### 17. `_build_conflict_report`
- **Type:** Helper (internal, exported for test mocking)
- **Import Sites:**
  - `src/orchestrator/nodes/__init__.py:31` (package export, for test compatibility)
- **Usage:** Builds ConflictReport from detected conflicts
- **Dependencies:** ConflictItem schema, Arango (storage)

---

## C) Constants

### 18. `ExpertType`
- **Type:** Enum/constant
- **Import Sites:**
  - `src/orchestrator/nodes/__init__.py:23` (package export)
  - `src/orchestrator/api/manuscript.py:22`
  - `src/orchestrator/api/knowledge.py:36`
- **Source:** `src/orchestrator/config.py`
- **Usage:** Expert type classification (EXTRACTION_SCHEMA, LOGIC_REASONING, etc.)

### 19. `NODE_EXPERT_MAP`
- **Type:** Dict constant
- **Import Sites:**
  - `src/orchestrator/nodes/__init__.py:24` (package export)
- **Source:** `src/orchestrator/config.py`
- **Usage:** Maps node names to expert types

### 20. `BACKPRESSURE_THRESHOLD_DELAY` / `BACKPRESSURE_THRESHOLD_RETRY`
- **Type:** Float constants
- **Import Sites:**
  - Not exported (internal use)
- **Usage:** KV cache backpressure thresholds

---

## D) Module-Level Globals (Side-Effect Initializers)

### 21. `telemetry_emitter`
- **Type:** Module-level instance
- **Import Sites:**
  - `src/orchestrator/nodes/__init__.py:32` (package export, for test compatibility)
- **Usage:** Telemetry emission (JSONL sink)
- **Dependencies:** TelemetryEmitter class

### 22. `logger`
- **Type:** Module-level logger
- **Import Sites:**
  - Not exported (internal use)
- **Usage:** Structured logging

### 23. `role_registry`
- **Type:** Module-level instance
- **Import Sites:**
  - Not exported (internal use)
- **Usage:** Role/prompt registry access

### 24. `_project_service` / `_synthesis_service`
- **Type:** Module-level lazy singletons
- **Import Sites:**
  - Not exported (internal use)
- **Usage:** Lazy-initialized service instances to avoid circular deps

---

## E) Internal Helper Functions (Not Exported)

- `_parse_kv_utilization` - KV cache metrics parsing
- `check_kv_backpressure` - Backpressure check
- `_get_synthesis_service` - Lazy service getter
- `_query_established_knowledge` - Knowledge base query
- `_query_candidate_knowledge` - Candidate facts query
- `_filter_conflicting_canonical` - Conflict filtering
- `_get_project_service` - Lazy service getter
- `_detect_quantization_failure` - FP4 failure detection
- `_stable_fact_id` - Fact ID generation
- `build_vision_context` - Vision context builder

---

## Import Compatibility Strategy

**Current Import Pattern:**
```python
from src.orchestrator.nodes import cartographer_node
from src.orchestrator.nodes.nodes import cartographer_node  # Also works
```

**Recommended Post-Split Pattern:**
```python
# Keep backward compatibility via __init__.py re-exports
from src.orchestrator.nodes import cartographer_node  # Still works
from src.orchestrator.nodes.cartography import cartographer_node  # New explicit path
```

**Compatibility Shim:**
- Keep `src/orchestrator/nodes/nodes.py` as a compatibility shim that re-exports from new modules
- Or migrate all imports to new module paths and remove shim after migration period

