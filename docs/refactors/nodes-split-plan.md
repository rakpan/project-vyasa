# Nodes.py Refactor Plan

**Generated:** Pre-refactor scan for `src/orchestrator/nodes/nodes.py` decomposition  
**File:** `src/orchestrator/nodes/nodes.py` (2361 lines)  
**Target:** Split into domain-specific modules while preserving behavior

---

## Target Module Map

### Proposed Structure

```
src/orchestrator/nodes/
├── __init__.py                    # Re-exports for backward compatibility
├── base.py                        # Already exists: wrap_prompt_with_context, validate_state_schema
├── cartography.py                 # cartographer_node + RQ-scoped retrieval helpers
├── synthesis.py                   # synthesizer_node
├── persistence.py                # saver_node + citation validation helpers
├── vision.py                      # vision_node + select_images_for_vision + build_vision_context
├── governance/
│   ├── __init__.py
│   ├── critic.py                  # critic_node + conflict detection helpers
│   ├── tone.py                    # tone_validator_node (thin wrapper)
│   ├── artifacts.py               # artifact_registry_node
│   ├── reframing.py               # reframing_node + _build_conflict_report
│   └── failure.py                 # failure_cleanup_node
├── strategy/
│   ├── __init__.py
│   ├── lead_counsel.py            # lead_counsel_node
│   └── logician.py                # logician_node
├── utils/
│   ├── __init__.py
│   ├── routing.py                 # route_to_expert, call_expert_with_fallback, check_kv_backpressure
│   ├── context.py                 # hydrate_project_context, _get_project_service
│   └── knowledge.py               # _query_established_knowledge, _query_candidate_knowledge, _filter_conflicting_canonical
└── nodes.py                       # Compatibility shim (re-exports from new modules)
```

---

## Safe Move Order (Lowest Coupling + Best Coverage First)

### Phase 1: Low-Coupling Helpers (Move First)

**1.1 Move `validate_state_schema` → `base.py`**
- **Status:** Already in `base.py` ✅
- **Coupling:** LOW
- **Coverage:** Indirect (via all nodes)
- **Risk:** None (already separated)

**1.2 Move `route_to_expert` → `utils/routing.py`**
- **Coupling:** LOW
- **Coverage:** Well covered via mocking
- **Dependencies:** `ExpertType`, `NODE_EXPERT_MAP` (from `..config`)
- **Risk:** Low
- **Action:** Move function + import ExpertType/NODE_EXPERT_MAP

**1.3 Move `check_kv_backpressure` → `utils/routing.py`**
- **Coupling:** LOW
- **Coverage:** Indirect
- **Dependencies:** `_parse_kv_utilization`, `BACKPRESSURE_THRESHOLD_*` constants
- **Risk:** Low
- **Action:** Move function + constants

**1.4 Move `call_expert_with_fallback` → `utils/routing.py`**
- **Coupling:** MEDIUM
- **Coverage:** Well covered via mocking
- **Dependencies:** `route_to_expert`, `check_kv_backpressure`, LLM client
- **Risk:** Medium (used by all major nodes)
- **Action:** Move after `route_to_expert` and `check_kv_backpressure`

**1.5 Move `hydrate_project_context` → `utils/context.py`**
- **Coupling:** MEDIUM
- **Coverage:** Indirect
- **Dependencies:** `_get_project_service`
- **Risk:** Medium
- **Action:** Move `_get_project_service` with it

**1.6 Move knowledge query helpers → `utils/knowledge.py`**
- **Coupling:** MEDIUM
- **Coverage:** Indirect
- **Dependencies:** `_get_synthesis_service`, Arango
- **Risk:** Medium
- **Action:** Move `_get_synthesis_service` with it

**Phase 1 Tests:** ✅ All helpers already covered via node tests

---

### Phase 2: Well-Covered Nodes (Move Second)

**2.1 Move `cartographer_node` → `cartography.py`**
- **Coupling:** HIGH
- **Coverage:** ✅ Well Covered (8 direct tests)
- **Dependencies:** 
  - `validate_state_schema` (base.py)
  - `hydrate_project_context` (utils/context.py)
  - `call_expert_with_fallback` (utils/routing.py)
  - QdrantStorage, PromptRegistry, ProjectService
- **Risk:** Medium (high coupling, but well tested)
- **Action:** 
  1. Move `cartographer_node` function
  2. Move RQ-scoped retrieval logic (lines 568-602)
  3. Move claim anchor population logic (lines 802-871)
  4. Update imports in `__init__.py`
  5. Run test suite: `test_cartographer_*`

**2.2 Move `synthesizer_node` → `synthesis.py`**
- **Coupling:** HIGH
- **Coverage:** ✅ Well Covered (6 direct tests)
- **Dependencies:**
  - `validate_state_schema` (base.py)
  - `hydrate_project_context` (utils/context.py)
  - `call_expert_with_fallback` (utils/routing.py)
  - CitationIntegrity validator, PromptRegistry
- **Risk:** Medium (high coupling, but well tested)
- **Action:**
  1. Move `synthesizer_node` function
  2. Update imports in `__init__.py`
  3. Run test suite: `test_synthesizer_*`

**2.3 Move `critic_node` → `governance/critic.py`
- **Coupling:** HIGH
- **Coverage:** ✅ Well Covered (6 direct tests)
- **Dependencies:**
  - `validate_state_schema` (base.py)
  - `hydrate_project_context` (utils/context.py)
  - `call_expert_with_fallback` (utils/routing.py)
  - Conflict detection logic, Arango, PromptRegistry
- **Risk:** Medium (high coupling, but well tested)
- **Action:**
  1. Move `critic_node` function
  2. Move conflict detection logic (lines 1301-1450)
  3. Move `_detect_quantization_failure` helper
  4. Update imports in `__init__.py`
  5. Run test suite: `test_conflict_*`, `test_critic_*`

**Phase 2 Tests:** ✅ All nodes well covered, run full test suite after each move

---

### Phase 3: Moderate Coverage Nodes (Move Third)

**3.1 Move `saver_node` → `persistence.py`**
- **Coupling:** HIGH
- **Coverage:** ✅ Moderately Covered (3 direct tests)
- **Dependencies:**
  - Arango (direct connection)
  - ManifestBuilder
  - ManuscriptService
- **Risk:** Medium (persistence logic, add tests first)
- **Action:**
  1. ⚠️ **Add test:** `test_saver_citation_validation_failure`
  2. ⚠️ **Add test:** `test_saver_arango_connection_failure`
  3. Move `saver_node` function
  4. Move `_validate_citations` helper (internal to saver)
  5. Move `_next_block_version` helper (internal to saver)
  6. Update imports in `__init__.py`
  7. Run test suite: `test_saver_*`

**3.2 Move `tone_validator_node` → `governance/tone.py`**
- **Coupling:** LOW
- **Coverage:** ✅ Well Covered (2 direct tests)
- **Dependencies:**
  - ToneGuard (scan_text)
- **Risk:** Low
- **Action:**
  1. Move `tone_validator_node` function
  2. Update imports in `__init__.py`
  3. Run test suite: `test_tone_*`

**Phase 3 Tests:** ⚠️ Add 2 tests for saver_node before move

---

### Phase 4: Minimal Coverage Nodes (Add Tests First)

**4.1 Move `vision_node` → `vision.py`**
- **Coupling:** MEDIUM
- **Coverage:** ❌ Uncovered (0 direct tests)
- **Dependencies:**
  - `call_expert_with_fallback` (utils/routing.py)
  - `select_images_for_vision`, `build_vision_context`
- **Risk:** High (no direct tests)
- **Action:**
  1. ❌ **Add test:** `test_vision_node_image_selection`
  2. ❌ **Add test:** `test_vision_node_context_building`
  3. ❌ **Add test:** `test_vision_node_error_handling`
  4. Move `vision_node` function
  5. Move `select_images_for_vision` helper
  6. Move `build_vision_context` helper
  7. Update imports in `__init__.py`
  8. Run test suite: `test_vision_*`

**4.2 Move `artifact_registry_node` → `governance/artifacts.py`**
- **Coupling:** MEDIUM
- **Coverage:** ⚠️ Minimal (1 direct test)
- **Dependencies:**
  - ManifestBuilder
- **Risk:** Medium
- **Action:**
  1. ❌ **Add test:** `test_artifact_registry_table_registration`
  2. ❌ **Add test:** `test_artifact_registry_precision_contract`
  3. ❌ **Add test:** `test_artifact_registry_manifest_flags`
  4. Move `artifact_registry_node` function
  5. Update imports in `__init__.py`
  6. Run test suite: `test_artifact_*`, `test_manifest_*`

**Phase 4 Tests:** ❌ Add 6 tests total before moves

---

### Phase 5: Uncovered Nodes (Add Tests First)

**5.1 Move `lead_counsel_node` → `strategy/lead_counsel.py`**
- **Coupling:** LOW
- **Coverage:** ❌ Uncovered (0 direct tests)
- **Dependencies:**
  - None (pure logic)
- **Risk:** Low (pure logic, but add tests for safety)
- **Action:**
  1. ❌ **Add test:** `test_lead_counsel_triage_summary`
  2. ❌ **Add test:** `test_lead_counsel_triage_detail`
  3. ❌ **Add test:** `test_lead_counsel_kernel_overlap`
  4. Move `lead_counsel_node` function
  5. Update imports in `__init__.py`
  6. Run test suite: `test_lead_counsel_*`

**5.2 Move `logician_node` → `strategy/logician.py`**
- **Coupling:** LOW
- **Coverage:** ❌ Uncovered (0 direct tests)
- **Dependencies:**
  - MathSandbox (local tool)
- **Risk:** Low (local tool, but add tests)
- **Action:**
  1. ❌ **Add test:** `test_logician_math_sandbox_execution`
  2. ❌ **Add test:** `test_logician_latex_parsing`
  3. ❌ **Add test:** `test_logician_error_handling`
  4. Move `logician_node` function
  5. Update imports in `__init__.py`
  6. Run test suite: `test_logician_*`

**5.3 Move `reframing_node` → `governance/reframing.py`**
- **Coupling:** MEDIUM
- **Coverage:** ❌ Uncovered (0 direct tests)
- **Dependencies:**
  - `_build_conflict_report` helper
  - Arango (store_reframing_proposal)
- **Risk:** Medium
- **Action:**
  1. ❌ **Add test:** `test_reframing_proposal_generation`
  2. ❌ **Add test:** `test_reframing_signoff_logic`
  3. ❌ **Add test:** `test_reframing_conflict_integration`
  4. Move `reframing_node` function
  5. Move `_build_conflict_report` helper
  6. Move `_stable_fact_id` helper (used by _build_conflict_report)
  7. Update imports in `__init__.py`
  8. Run test suite: `test_reframing_*`

**5.4 Move `failure_cleanup_node` → `governance/failure.py`**
- **Coupling:** LOW
- **Coverage:** ❌ Uncovered (0 direct tests)
- **Dependencies:**
  - JobManager (update_job_status)
  - TelemetryEmitter
- **Risk:** Low (simple cleanup, but add tests)
- **Action:**
  1. ❌ **Add test:** `test_failure_cleanup_job_status`
  2. ❌ **Add test:** `test_failure_cleanup_error_propagation`
  3. ❌ **Add test:** `test_failure_cleanup_telemetry`
  4. Move `failure_cleanup_node` function
  5. Update imports in `__init__.py`
  6. Run test suite: `test_failure_cleanup_*`

**Phase 5 Tests:** ❌ Add 12 tests total before moves

---

## Import Compatibility Strategy

### Option A: Compatibility Shim (Recommended for Gradual Migration)

**Keep `src/orchestrator/nodes/nodes.py` as shim:**

```python
# src/orchestrator/nodes/nodes.py (compatibility shim)
"""Compatibility shim - re-exports from new module structure."""

from .cartography import cartographer_node
from .synthesis import synthesizer_node
from .governance.critic import critic_node
from .governance.tone import tone_validator_node
from .governance.artifacts import artifact_registry_node
from .governance.reframing import reframing_node
from .governance.failure import failure_cleanup_node
from .vision import vision_node
from .strategy.lead_counsel import lead_counsel_node
from .strategy.logician import logician_node
from .persistence import saver_node
from .utils.routing import route_to_expert, call_expert_with_fallback
from .utils.context import hydrate_project_context
from ..config import ExpertType, NODE_EXPERT_MAP

# Re-export for backward compatibility
__all__ = [
    "cartographer_node",
    "critic_node",
    "synthesizer_node",
    # ... etc
]
```

**Pros:**
- ✅ Zero breaking changes
- ✅ Gradual migration possible
- ✅ Tests continue to work

**Cons:**
- ⚠️ Temporary file to maintain
- ⚠️ Can remove after migration period

### Option B: Direct Migration (Cleaner, Requires Coordinated Change)

**Update all imports to new paths:**

```python
# Old
from src.orchestrator.nodes import cartographer_node

# New
from src.orchestrator.nodes.cartography import cartographer_node
```

**Pros:**
- ✅ Clean structure immediately
- ✅ No shim file

**Cons:**
- ⚠️ Requires updating all import sites simultaneously
- ⚠️ Higher risk of breaking changes

**Recommendation:** Use Option A (compatibility shim) for Phase 1-3, then migrate to Option B in Phase 4-5.

---

## Missing Tests to Add (Before Moving Each Slice)

### Before Phase 3 (saver_node):
1. `test_saver_citation_validation_failure` - Test bibliography missing scenario
2. `test_saver_arango_connection_failure` - Test DB unavailable scenario

### Before Phase 4 (vision_node):
1. `test_vision_node_image_selection` - Test image selection logic
2. `test_vision_node_context_building` - Test vision context construction
3. `test_vision_node_error_handling` - Test vision service failures

### Before Phase 4 (artifact_registry_node):
1. `test_artifact_registry_table_registration` - Test table artifact registration
2. `test_artifact_registry_precision_contract` - Test precision contract application
3. `test_artifact_registry_manifest_flags` - Test manifest flag generation

### Before Phase 5 (lead_counsel_node):
1. `test_lead_counsel_triage_summary` - Test summary path
2. `test_lead_counsel_triage_detail` - Test detail path
3. `test_lead_counsel_kernel_overlap` - Test kernel overlap detection

### Before Phase 5 (logician_node):
1. `test_logician_math_sandbox_execution` - Test math sandbox execution
2. `test_logician_latex_parsing` - Test LaTeX formula parsing
3. `test_logician_error_handling` - Test sandbox unavailable scenario

### Before Phase 5 (reframing_node):
1. `test_reframing_proposal_generation` - Test proposal creation
2. `test_reframing_signoff_logic` - Test signoff requirement (revision_count >= 2)
3. `test_reframing_conflict_integration` - Test conflict report integration

### Before Phase 5 (failure_cleanup_node):
1. `test_failure_cleanup_job_status` - Test job status update to FAILED
2. `test_failure_cleanup_error_propagation` - Test error message handling
3. `test_failure_cleanup_telemetry` - Test telemetry emission

**Total Tests to Add: 17**

---

## Refactor Execution Checklist

### Pre-Refactor (Do Now):
- [x] Create analysis reports (this document)
- [ ] Add refactor guard tests (see `test_refactor_guards.py`)
- [ ] Add missing tests for uncovered nodes (17 tests)
- [ ] Verify all existing tests pass

### Phase 1: Helpers (Low Risk)
- [ ] Move `route_to_expert` → `utils/routing.py`
- [ ] Move `check_kv_backpressure` → `utils/routing.py`
- [ ] Move `call_expert_with_fallback` → `utils/routing.py`
- [ ] Move `hydrate_project_context` → `utils/context.py`
- [ ] Move knowledge helpers → `utils/knowledge.py`
- [ ] Update `__init__.py` imports
- [ ] Run test suite: `pytest src/tests/unit/orchestrator/ -v`
- [ ] Verify workflow still compiles

### Phase 2: Well-Covered Nodes (Medium Risk)
- [ ] Move `cartographer_node` → `cartography.py`
- [ ] Run tests: `pytest src/tests/unit/orchestrator/test_cartographer* -v`
- [ ] Move `synthesizer_node` → `synthesis.py`
- [ ] Run tests: `pytest src/tests/unit/orchestrator/test_synthesizer* -v`
- [ ] Move `critic_node` → `governance/critic.py`
- [ ] Run tests: `pytest src/tests/unit/orchestrator/test_conflict* -v`
- [ ] Update `__init__.py` imports
- [ ] Run full test suite

### Phase 3: Moderate Coverage (Medium Risk)
- [ ] Add 2 tests for `saver_node`
- [ ] Move `saver_node` → `persistence.py`
- [ ] Run tests: `pytest src/tests/unit/test_saver* -v`
- [ ] Move `tone_validator_node` → `governance/tone.py`
- [ ] Run tests: `pytest src/tests/unit/orchestrator/test_tone* -v`
- [ ] Update `__init__.py` imports
- [ ] Run full test suite

### Phase 4: Minimal Coverage (Higher Risk)
- [ ] Add 6 tests (vision + artifacts)
- [ ] Move `vision_node` → `vision.py`
- [ ] Run tests: `pytest src/tests/unit/orchestrator/test_vision* -v`
- [ ] Move `artifact_registry_node` → `governance/artifacts.py`
- [ ] Run tests: `pytest src/tests/unit/orchestrator/test_artifact* -v`
- [ ] Update `__init__.py` imports
- [ ] Run full test suite

### Phase 5: Uncovered Nodes (Highest Risk)
- [ ] Add 12 tests (lead_counsel + logician + reframing + failure)
- [ ] Move `lead_counsel_node` → `strategy/lead_counsel.py`
- [ ] Run tests: `pytest src/tests/unit/orchestrator/test_lead_counsel* -v`
- [ ] Move `logician_node` → `strategy/logician.py`
- [ ] Run tests: `pytest src/tests/unit/orchestrator/test_logician* -v`
- [ ] Move `reframing_node` → `governance/reframing.py`
- [ ] Run tests: `pytest src/tests/unit/orchestrator/test_reframing* -v`
- [ ] Move `failure_cleanup_node` → `governance/failure.py`
- [ ] Run tests: `pytest src/tests/unit/orchestrator/test_failure_cleanup* -v`
- [ ] Update `__init__.py` imports
- [ ] Run full test suite

### Post-Refactor (Cleanup)
- [ ] Remove compatibility shim `nodes.py` (after migration period)
- [ ] Update all import sites to new paths
- [ ] Update documentation
- [ ] Run integration tests
- [ ] Verify workflow end-to-end

---

## Risk Mitigation

### High-Risk Areas:
1. **Circular Import Prevention:**
   - Keep lazy imports for `ProjectService`, `SynthesisService`
   - Use `__getattr__` pattern in `__init__.py` if needed
   - Test import smoke test (see guard tests)

2. **State Mutation Contracts:**
   - All nodes must return new dict (immutable pattern)
   - Verify state schema validation still works
   - Test phase transitions still work

3. **Workflow Compatibility:**
   - Ensure `workflow.py` imports still work
   - Verify LangGraph node registration unchanged
   - Test workflow compilation after each phase

4. **Test Mock Compatibility:**
   - Ensure mocks still target library-level imports
   - Verify firewall fixtures still work
   - Test that existing mocks don't break

---

## Success Criteria

✅ All existing tests pass  
✅ Workflow compiles and runs  
✅ No circular import errors  
✅ Import compatibility maintained (via shim or migration)  
✅ Code coverage maintained or improved  
✅ No behavior changes (deterministic outputs unchanged)

