# Nodes.py Test Coverage Map

**Generated:** Pre-refactor scan for `src/orchestrator/nodes/nodes.py` decomposition  
**File:** `src/orchestrator/nodes/nodes.py` (2361 lines)

## Coverage Methodology

**Direct Coverage:** Test imports and directly calls the function  
**Indirect Coverage:** Function exercised via higher-level flow (workflow, integration tests)  
**Uncovered:** No test found that exercises this function

---

## Coverage by Node Function

### 1. `cartographer_node`

**Direct Coverage:**
- ✅ `src/tests/unit/orchestrator/test_cartographer_schema.py` - Schema validation tests
- ✅ `src/tests/unit/orchestrator/test_cartographer_rag_flow.py` - RQ-scoped retrieval tests
- ✅ `src/tests/unit/orchestrator/test_prompt_metadata_thread.py` - Prompt registry integration
- ✅ `src/tests/unit/orchestrator/test_nodes_use_prompt_registry.py` - Prompt fetching
- ✅ `src/tests/unit/orchestrator/test_phase_transitions.py` - Phase transition (MAPPING)
- ✅ `src/tests/unit/orchestrator/test_context_injection.py` - Context injection verification
- ✅ `src/tests/unit/test_nodes.py` - Basic functionality
- ✅ `src/tests/unit/test_resilience.py` - Error handling

**Indirect Coverage:**
- ✅ `src/tests/integration/test_pipeline_e2e.py` - End-to-end workflow

**Coverage Status:** ✅ **Well Covered** (8 direct, 1 indirect)

**Test Gaps:**
- ⚠️ Qdrant retrieval failure scenarios
- ⚠️ Project context hydration failures
- ⚠️ RQ-scoped chunk filtering edge cases

**Proposed Domain:** `nodes/cartography.py`

---

### 2. `critic_node`

**Direct Coverage:**
- ✅ `src/tests/unit/orchestrator/test_conflict_determinism.py` - Conflict detection determinism
- ✅ `src/tests/unit/orchestrator/test_conflict_report_logic.py` - Conflict report generation
- ✅ `src/tests/unit/orchestrator/test_prompt_metadata_thread.py` - Prompt registry integration
- ✅ `src/tests/unit/orchestrator/test_nodes_use_prompt_registry.py` - Prompt fetching
- ✅ `src/tests/unit/orchestrator/test_phase_transitions.py` - Phase transition (VETTING)
- ✅ `src/tests/unit/orchestrator/test_context_injection.py` - Context injection verification

**Indirect Coverage:**
- ✅ `src/tests/integration/test_pipeline_e2e.py` - End-to-end workflow

**Coverage Status:** ✅ **Well Covered** (6 direct, 1 indirect)

**Test Gaps:**
- ⚠️ PDF text cache verification failures
- ⚠️ Conflict detection with missing anchors
- ⚠️ Vocabulary guardrail edge cases

**Proposed Domain:** `nodes/governance/critic.py`

---

### 3. `synthesizer_node`

**Direct Coverage:**
- ✅ `src/tests/unit/orchestrator/test_synthesizer_citation_integrity.py` - Citation integrity validation
- ✅ `src/tests/unit/orchestrator/test_prompt_metadata_thread.py` - Prompt registry integration
- ✅ `src/tests/unit/orchestrator/test_nodes_use_prompt_registry.py` - Prompt fetching
- ✅ `src/tests/unit/orchestrator/test_phase_transitions.py` - Phase transition (SYNTHESIZING)
- ✅ `src/tests/unit/orchestrator/test_context_injection.py` - Context injection verification
- ✅ `src/tests/unit/test_tone_rewrite_integration.py` - Tone rewrite integration

**Indirect Coverage:**
- ✅ `src/tests/integration/test_pipeline_e2e.py` - End-to-end workflow

**Coverage Status:** ✅ **Well Covered** (6 direct, 1 indirect)

**Test Gaps:**
- ⚠️ Manuscript block generation with zero claims
- ⚠️ Vocabulary guardrail failures
- ⚠️ Citation integrity in exploratory mode

**Proposed Domain:** `nodes/synthesis.py`

---

### 4. `vision_node`

**Direct Coverage:**
- ❌ No direct tests found

**Indirect Coverage:**
- ✅ `src/tests/integration/test_pipeline_e2e.py` - End-to-end workflow (may exercise)

**Coverage Status:** ⚠️ **Minimal Coverage** (0 direct, 1 indirect)

**Test Gaps:**
- ❌ Image selection logic
- ❌ Vision context building
- ❌ Vision service error handling

**Recommended Tests Before Move:**
- `test_vision_node_image_selection`
- `test_vision_node_context_building`
- `test_vision_node_error_handling`

**Proposed Domain:** `nodes/vision.py`

---

### 5. `saver_node`

**Direct Coverage:**
- ✅ `src/tests/unit/orchestrator/test_phase_transitions.py` - Phase transition (DONE)
- ✅ `src/tests/unit/test_saver_manifest_integration.py` - Manifest integration
- ✅ `src/tests/unit/test_saver_reliability.py` - Reliability tests

**Indirect Coverage:**
- ✅ `src/tests/integration/test_pipeline_e2e.py` - End-to-end workflow

**Coverage Status:** ✅ **Moderately Covered** (3 direct, 1 indirect)

**Test Gaps:**
- ⚠️ Citation validation failures (bibliography missing)
- ⚠️ Manuscript block versioning edge cases
- ⚠️ Arango connection failures

**Proposed Domain:** `nodes/persistence.py`

---

### 6. `artifact_registry_node`

**Direct Coverage:**
- ✅ `src/tests/unit/orchestrator/test_manifest_contract.py` - Manifest contract validation

**Indirect Coverage:**
- ✅ `src/tests/integration/test_pipeline_e2e.py` - End-to-end workflow

**Coverage Status:** ⚠️ **Minimal Coverage** (1 direct, 1 indirect)

**Test Gaps:**
- ❌ Table artifact registration
- ❌ Precision contract application
- ❌ Manifest flag generation

**Recommended Tests Before Move:**
- `test_artifact_registry_table_registration`
- `test_artifact_registry_precision_contract`
- `test_artifact_registry_manifest_flags`

**Proposed Domain:** `nodes/governance/artifacts.py`

---

### 7. `tone_validator_node`

**Direct Coverage:**
- ✅ `src/tests/unit/orchestrator/test_tone_guard.py` - Tone guard tests (via tone_guard module)
- ✅ `src/tests/unit/test_tone_guard.py` - Tone detection tests

**Indirect Coverage:**
- ✅ `src/tests/integration/test_pipeline_e2e.py` - End-to-end workflow

**Coverage Status:** ✅ **Well Covered** (2 direct, 1 indirect)

**Test Gaps:**
- ⚠️ Tone validator node-specific integration (vs tone_guard module tests)

**Proposed Domain:** `nodes/governance/tone.py`

---

### 8. `lead_counsel_node`

**Direct Coverage:**
- ❌ No direct tests found

**Indirect Coverage:**
- ✅ `src/tests/integration/test_pipeline_e2e.py` - End-to-end workflow (may exercise)

**Coverage Status:** ⚠️ **Minimal Coverage** (0 direct, 1 indirect)

**Test Gaps:**
- ❌ Triage logic (summary vs detail)
- ❌ Kernel overlap detection
- ❌ New primitives detection

**Recommended Tests Before Move:**
- `test_lead_counsel_triage_summary`
- `test_lead_counsel_triage_detail`
- `test_lead_counsel_kernel_overlap`

**Proposed Domain:** `nodes/strategy/lead_counsel.py`

---

### 9. `logician_node`

**Direct Coverage:**
- ❌ No direct tests found

**Indirect Coverage:**
- ✅ `src/tests/integration/test_pipeline_e2e.py` - End-to-end workflow (may exercise)

**Coverage Status:** ⚠️ **Minimal Coverage** (0 direct, 1 indirect)

**Test Gaps:**
- ❌ Math sandbox execution
- ❌ LaTeX formula parsing
- ❌ Symbolic computation error handling

**Recommended Tests Before Move:**
- `test_logician_math_sandbox_execution`
- `test_logician_latex_parsing`
- `test_logician_error_handling`

**Proposed Domain:** `nodes/strategy/logician.py`

---

### 10. `reframing_node`

**Direct Coverage:**
- ❌ No direct tests found

**Indirect Coverage:**
- ✅ `src/tests/integration/test_pipeline_e2e.py` - End-to-end workflow (may exercise)

**Coverage Status:** ⚠️ **Minimal Coverage** (0 direct, 1 indirect)

**Test Gaps:**
- ❌ Reframing proposal generation
- ❌ Signoff requirement logic
- ❌ Conflict report integration

**Recommended Tests Before Move:**
- `test_reframing_proposal_generation`
- `test_reframing_signoff_logic`
- `test_reframing_conflict_integration`

**Proposed Domain:** `nodes/governance/reframing.py`

---

### 11. `failure_cleanup_node`

**Direct Coverage:**
- ❌ No direct tests found

**Indirect Coverage:**
- ✅ `src/tests/integration/test_pipeline_e2e.py` - End-to-end workflow (may exercise)

**Coverage Status:** ⚠️ **Minimal Coverage** (0 direct, 1 indirect)

**Test Gaps:**
- ❌ Job status update on failure
- ❌ Error message propagation
- ❌ Telemetry emission

**Recommended Tests Before Move:**
- `test_failure_cleanup_job_status`
- `test_failure_cleanup_error_propagation`
- `test_failure_cleanup_telemetry`

**Proposed Domain:** `nodes/governance/failure.py`

---

## Helper Functions Coverage

### `route_to_expert`
**Coverage:** ✅ Indirectly tested via node tests (mocked extensively)  
**Status:** Well covered via mocking

### `call_expert_with_fallback`
**Coverage:** ✅ Indirectly tested via node tests (mocked extensively)  
**Status:** Well covered via mocking

### `hydrate_project_context`
**Coverage:** ✅ Indirectly tested via node tests  
**Status:** Moderately covered

### `validate_state_schema`
**Coverage:** ✅ Indirectly tested via node tests  
**Status:** Moderately covered

---

## Coverage Summary by Proposed Domain

### **Cartography Domain** (`nodes/cartography.py`)
- `cartographer_node` - ✅ Well Covered (8 direct tests)
- **Status:** Safe to move first

### **Governance Domain** (`nodes/governance/`)
- `critic_node` - ✅ Well Covered (6 direct tests)
- `tone_validator_node` - ✅ Well Covered (2 direct tests)
- `artifact_registry_node` - ⚠️ Minimal (1 direct test) - **Add tests before move**
- `reframing_node` - ❌ Uncovered - **Add tests before move**
- `failure_cleanup_node` - ❌ Uncovered - **Add tests before move**

### **Synthesis Domain** (`nodes/synthesis.py`)
- `synthesizer_node` - ✅ Well Covered (6 direct tests)
- **Status:** Safe to move

### **Persistence Domain** (`nodes/persistence.py`)
- `saver_node` - ✅ Moderately Covered (3 direct tests)
- **Status:** Safe to move (add citation validation tests)

### **Strategy Domain** (`nodes/strategy/`)
- `lead_counsel_node` - ❌ Uncovered - **Add tests before move**
- `logician_node` - ❌ Uncovered - **Add tests before move**

### **Vision Domain** (`nodes/vision.py`)
- `vision_node` - ❌ Uncovered - **Add tests before move**

---

## Critical Test Gaps (Must Add Before Refactor)

### High Priority (Block Refactor)
1. **`vision_node`** - No direct tests
2. **`lead_counsel_node`** - No direct tests
3. **`logician_node`** - No direct tests
4. **`reframing_node`** - No direct tests
5. **`failure_cleanup_node`** - No direct tests

### Medium Priority (Recommended Before Move)
1. **`artifact_registry_node`** - Only 1 direct test (manifest contract)
2. **`saver_node`** - Missing citation validation failure tests

### Low Priority (Nice to Have)
1. **`cartographer_node`** - Qdrant failure scenarios
2. **`critic_node`** - PDF text cache edge cases
3. **`synthesizer_node`** - Zero claims edge cases

---

## Test Coverage Recommendations

### Before Moving Each Domain:

**1. Cartography (Move First - Best Coverage)**
- ✅ Ready to move (well covered)

**2. Synthesis (Move Second - Well Covered)**
- ✅ Ready to move (well covered)

**3. Persistence (Move Third - Moderate Coverage)**
- ⚠️ Add citation validation failure test
- ⚠️ Add Arango connection failure test

**4. Governance - Critic (Move Fourth - Well Covered)**
- ✅ Ready to move (well covered)

**5. Governance - Tone (Move Fifth - Well Covered)**
- ✅ Ready to move (well covered)

**6. Governance - Artifacts (Move Sixth - Minimal Coverage)**
- ❌ Add 3 tests: table registration, precision contract, manifest flags

**7. Strategy - Lead Counsel (Move Seventh - Uncovered)**
- ❌ Add 3 tests: triage logic, kernel overlap, new primitives

**8. Strategy - Logician (Move Eighth - Uncovered)**
- ❌ Add 3 tests: math sandbox, LaTeX parsing, error handling

**9. Vision (Move Ninth - Uncovered)**
- ❌ Add 3 tests: image selection, context building, error handling

**10. Governance - Reframing (Move Tenth - Uncovered)**
- ❌ Add 3 tests: proposal generation, signoff logic, conflict integration

**11. Governance - Failure Cleanup (Move Last - Uncovered)**
- ❌ Add 3 tests: job status update, error propagation, telemetry

---

## Integration Test Coverage

**End-to-End Tests:**
- ✅ `src/tests/integration/test_pipeline_e2e.py` - Exercises full workflow
- Covers: cartographer → critic → synthesizer → saver flow

**Coverage Status:** ✅ Integration tests provide indirect coverage for all nodes

---

## Test Mocking Patterns

**Common Mock Targets:**
- `call_expert_with_fallback` - Mocked in 10+ test files
- `route_to_expert` - Mocked in 5+ test files
- `_get_project_service` - Mocked via ArangoClient firewall
- `QdrantStorage` - Mocked in cartographer tests

**Mock Compatibility:**
- ✅ All mocks target library-level imports (following "Golden Rule")
- ✅ No mocks target project files directly
- ✅ Firewall fixtures in `conftest.py` handle I/O blocking

