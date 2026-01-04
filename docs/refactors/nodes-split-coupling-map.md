# Nodes.py Dependency & Coupling Map

**Generated:** Pre-refactor scan for `src/orchestrator/nodes/nodes.py` decomposition  
**File:** `src/orchestrator/nodes/nodes.py` (2361 lines)

## Coupling Score Methodology

**Low (L):** 0-1 external services, 0-1 globals, 0-2 cross-module imports, 0-2 state mutations  
**Medium (M):** 2-3 external services, 2-3 globals, 3-5 cross-module imports, 3-5 state mutations  
**High (H):** 4+ external services, 4+ globals, 6+ cross-module imports, 6+ state mutations

---

## Node Functions

### 1. `cartographer_node` - **Coupling: HIGH**

**State Read:**
- `job_id`, `project_id`, `raw_text`, `critiques`, `force_refresh_context`, `ingestion_id`, `rigor_level`
- `project_context`, `context_sources`, `corpus_memory`, `evidence_chunks`

**State Write:**
- `extracted_json`, `triples`, `phase` (MAPPING)
- `prompt_manifest`, `context_sources`, `selected_reference_ids`
- `_sglang_usage`, `_expert_name`, `_expert_url`

**External Services:**
- ✅ **Qdrant** (via `QdrantStorage.retrieve_chunks_by_query`)
- ✅ **Arango** (via `ProjectService` for project context)
- ✅ **PromptRegistry** (via `get_active_prompt_with_meta`)
- ✅ **Worker/Brain** (via `call_expert_with_fallback`)

**Module-Level Globals:**
- `role_registry` (RoleRegistry)
- `telemetry_emitter` (TelemetryEmitter)
- `_project_service` (lazy singleton)

**Cross-Module Imports:**
- `..prompts` (PromptRegistry)
- `..storage.qdrant` (QdrantStorage)
- `..storage.arango` (load_claims_for_conflict_detection)
- `..normalize` (normalize_extracted_json)
- `..artifacts.manifest_builder` (build_manifest)
- `..guards.tone_guard` (scan_text)
- `..job_manager` (update_job_status)
- `...project.service` (ProjectService)
- `...shared.*` (config, schema, llm_client, etc.)

**Potential Cycles:**
- ⚠️ Imports from `..prompts` which may import nodes
- ⚠️ Imports from `..storage.*` which may import nodes
- ⚠️ Lazy import of `ProjectService` to avoid cycles

**Coupling Score: HIGH** (4 services, 3 globals, 9+ imports, 8+ state mutations)

---

### 2. `critic_node` - **Coupling: HIGH**

**State Read:**
- `job_id`, `project_id`, `extracted_json`, `raw_text`, `synthesis`
- `project_context`, `rigor_level`, `conflict_flags`, `pdf_path`
- `critiques`, `revision_count`, `critic_status`

**State Write:**
- `critiques`, `revision_count`, `critic_status`, `critic_score`
- `synthesis`, `phase` (VETTING)
- `conflict_detected`, `conflicts`, `needs_human_review`
- `conflict_report_id`, `conflict_report`
- `prompt_manifest`, `_sglang_usage`, `_expert_name`, `_expert_url`

**External Services:**
- ✅ **Arango** (via `load_claims_for_conflict_detection`, `store_conflict_report`)
- ✅ **Arango** (via PDF text cache for snippet verification)
- ✅ **PromptRegistry** (via `get_active_prompt_with_meta`)
- ✅ **Brain** (via `call_expert_with_fallback`)

**Module-Level Globals:**
- `role_registry`
- `telemetry_emitter`
- `_project_service` (lazy)

**Cross-Module Imports:**
- `..prompts` (PromptRegistry)
- `..storage.arango` (load_claims_for_conflict_detection)
- `..conflict_utils` (generate_conflict_explanation, DeterministicConflictType)
- `..schemas.claims` (Claim, SourceAnchor)
- `..job_store` (store_conflict_report)
- `..pdf_text_cache` (load_page_text)
- `...shared.schema` (ConflictItem, ConflictType, etc.)

**Potential Cycles:**
- ⚠️ Imports from `..conflict_utils` (may import nodes)
- ⚠️ Imports from `..storage.arango` (may import nodes)

**Coupling Score: HIGH** (4 services, 3 globals, 8+ imports, 10+ state mutations)

---

### 3. `synthesizer_node` - **Coupling: HIGH**

**State Read:**
- `job_id`, `project_id`, `project_context`, `rigor_level`
- `extracted_json`, `triples`, `synthesis`

**State Write:**
- `synthesis`, `manuscript_blocks`, `phase` (SYNTHESIZING)
- `prompt_manifest`, `synthesis_error`

**External Services:**
- ✅ **PromptRegistry** (via `get_active_prompt_with_meta`)
- ✅ **Brain** (via `call_expert_with_fallback`)

**Module-Level Globals:**
- `role_registry`
- `telemetry_emitter`

**Cross-Module Imports:**
- `..prompts` (PromptRegistry)
- `..validators.citation_integrity` (validate_manuscript_blocks, extract_claim_ids_from_text)
- `..guards.tone_guard` (scan_text)
- `..guards.tone_rewrite` (rewrite_to_neutral)
- `...shared.vocab_guard` (get_vocab_guard)
- `...shared.schema` (ManuscriptBlock)

**Potential Cycles:**
- ⚠️ Imports from `..validators.*` (may import nodes)
- ⚠️ Imports from `..guards.*` (may import nodes)

**Coupling Score: HIGH** (2 services, 2 globals, 6+ imports, 5+ state mutations)

---

### 4. `vision_node` - **Coupling: MEDIUM**

**State Read:**
- `job_id`, `image_paths`, `project_id`

**State Write:**
- `vision_results`, `raw_text` (from vision analysis)

**External Services:**
- ✅ **Vision** (Qwen-VL via `call_expert_with_fallback`)

**Module-Level Globals:**
- `role_registry`
- `telemetry_emitter`

**Cross-Module Imports:**
- `..config` (ExpertType, route_to_expert)
- `...shared.*` (config, llm_client)

**Coupling Score: MEDIUM** (1 service, 2 globals, 3 imports, 2 state mutations)

---

### 5. `saver_node` - **Coupling: HIGH**

**State Read:**
- `job_id`, `project_id`, `extracted_json`, `critiques`, `critic_status`
- `vision_results`, `manuscript_blocks`, `rigor_level`

**State Write:**
- `phase` (DONE)
- Persists to Arango (extraction, manifest)

**External Services:**
- ✅ **Arango** (direct `ArangoClient` connection)
- ✅ **ManifestBuilder** (build_manifest, persist_manifest)

**Module-Level Globals:**
- `telemetry_emitter`

**Cross-Module Imports:**
- `..artifacts.manifest_builder` (build_manifest, persist_manifest)
- `..job_manager` (update_job_status)
- `...shared.config` (get_memory_url, ARANGODB_*)

**Potential Cycles:**
- ⚠️ Imports from `..artifacts.manifest_builder` (may import nodes)

**Coupling Score: HIGH** (2 services, 1 global, 4 imports, 1 state mutation + persistence)

---

### 6. `artifact_registry_node` - **Coupling: MEDIUM**

**State Read:**
- `job_id`, `project_id`, `rigor_level`, `project_context`

**State Write:**
- `manifest_flags` (from manifest builder)

**External Services:**
- ✅ **ManifestBuilder** (build_manifest)

**Module-Level Globals:**
- None

**Cross-Module Imports:**
- `..artifacts.manifest_builder` (build_manifest)
- `..job_manager` (update_job_status)

**Coupling Score: MEDIUM** (1 service, 0 globals, 2 imports, 1 state mutation)

---

### 7. `tone_validator_node` - **Coupling: LOW**

**State Read:**
- `synthesis`, `final_text`

**State Write:**
- None (read-only validation)

**External Services:**
- None

**Module-Level Globals:**
- None

**Cross-Module Imports:**
- `..guards.tone_guard` (scan_text)

**Coupling Score: LOW** (0 services, 0 globals, 1 import, 0 state mutations)

---

### 8. `lead_counsel_node` - **Coupling: LOW**

**State Read:**
- `librarian_summary`, `summary`, `project_kernel`, `project_context`, `extracted_json`

**State Write:**
- `lead_counsel` (triage decision)

**External Services:**
- None

**Module-Level Globals:**
- None

**Cross-Module Imports:**
- None (pure logic)

**Coupling Score: LOW** (0 services, 0 globals, 0 imports, 1 state mutation)

---

### 9. `logician_node` - **Coupling: LOW**

**State Read:**
- `latex_formula`, `logician_input`

**State Write:**
- `logic_validation` (math sandbox result)

**External Services:**
- ✅ **MathSandbox** (local tool, not external service)

**Module-Level Globals:**
- None

**Cross-Module Imports:**
- `.tools.math_sandbox` (MathSandbox)

**Coupling Score: LOW** (0 external services, 0 globals, 1 import, 1 state mutation)

---

### 10. `reframing_node` - **Coupling: MEDIUM**

**State Read:**
- `conflict_report`, `revision_count`, `project_id`, `job_id`, `doc_hash`

**State Write:**
- `needs_signoff` (if revision_count >= 2)
- Persists to Arango (reframing proposal)

**External Services:**
- ✅ **Arango** (via `store_reframing_proposal`)

**Module-Level Globals:**
- None

**Cross-Module Imports:**
- `..job_store` (store_reframing_proposal)
- `..job_manager` (update_job_status)
- `...shared.schema` (ReframingProposal)

**Coupling Score: MEDIUM** (1 service, 0 globals, 3 imports, 1 state mutation + persistence)

---

### 11. `failure_cleanup_node` - **Coupling: LOW**

**State Read:**
- `job_id`, `error`, `critic_status`

**State Write:**
- `status` ("fail")

**External Services:**
- ✅ **JobManager** (update_job_status)

**Module-Level Globals:**
- `telemetry_emitter`

**Cross-Module Imports:**
- `..job_manager` (update_job_status)

**Coupling Score: LOW** (1 service, 1 global, 1 import, 1 state mutation)

---

## Helper Functions

### 12. `route_to_expert` - **Coupling: LOW**

**Dependencies:**
- `ExpertType` enum, `NODE_EXPERT_MAP` dict
- Pure routing logic, no external services

**Coupling Score: LOW**

### 13. `call_expert_with_fallback` - **Coupling: MEDIUM**

**Dependencies:**
- LLM client (HTTP calls)
- KV cache metrics (Prometheus scraping)
- Backpressure thresholds (module constants)
- `check_kv_backpressure` helper

**Coupling Score: MEDIUM** (2 services conceptually, 1 global threshold, 3+ imports)

### 14. `hydrate_project_context` - **Coupling: MEDIUM**

**Dependencies:**
- `_get_project_service()` (lazy singleton)
- Arango (via ProjectService)
- State mutation (injects `project_context`)

**Coupling Score: MEDIUM** (1 service, 1 global, 2 imports, 1 state mutation)

### 15. `validate_state_schema` - **Coupling: LOW**

**Dependencies:**
- None (pure validation)
- State normalization only

**Coupling Score: LOW**

---

## Internal Helpers (Not Exported)

### `_query_established_knowledge` - **Coupling: MEDIUM**
- Arango (canonical knowledge), `_get_synthesis_service()`
- **Score: MEDIUM**

### `_query_candidate_knowledge` - **Coupling: MEDIUM**
- Arango (candidate_knowledge collection)
- **Score: MEDIUM**

### `_filter_conflicting_canonical` - **Coupling: LOW**
- Pure logic (conflict filtering)
- **Score: LOW**

### `_get_project_service` / `_get_synthesis_service` - **Coupling: MEDIUM**
- Lazy singletons, Arango connections
- **Score: MEDIUM**

### `_detect_quantization_failure` - **Coupling: LOW**
- Pure logic (regex-based detection)
- **Score: LOW**

### `_build_conflict_report` - **Coupling: MEDIUM**
- Schema construction, Arango storage
- **Score: MEDIUM**

---

## Summary by Coupling Level

**HIGH Coupling (Move Last):**
- `cartographer_node` (4 services, 9+ imports)
- `critic_node` (4 services, 8+ imports)
- `synthesizer_node` (2 services, 6+ imports)
- `saver_node` (2 services, persistence logic)

**MEDIUM Coupling (Move Middle):**
- `vision_node` (1 service, 3 imports)
- `artifact_registry_node` (1 service, 2 imports)
- `reframing_node` (1 service, 3 imports)
- `call_expert_with_fallback` (routing/fallback logic)
- `hydrate_project_context` (state hydration)
- Internal knowledge query helpers

**LOW Coupling (Move First):**
- `tone_validator_node` (read-only validation)
- `lead_counsel_node` (pure logic)
- `logician_node` (local tool only)
- `failure_cleanup_node` (simple cleanup)
- `route_to_expert` (pure routing)
- `validate_state_schema` (pure validation)
- `_detect_quantization_failure` (pure detection)

---

## Cross-Module Import Dependencies

**Critical Import Paths (Potential Cycles):**
1. `..prompts` → may import nodes (used by cartographer, critic, synthesizer)
2. `..storage.*` → may import nodes (used by cartographer, critic)
3. `..artifacts.manifest_builder` → may import nodes (used by saver, artifact_registry)
4. `..validators.*` → may import nodes (used by synthesizer)
5. `..guards.*` → may import nodes (used by synthesizer, tone_validator)
6. `..conflict_utils` → may import nodes (used by critic)
7. `...project.service` → lazy import to avoid cycles (used by hydrate_project_context)

**Safe Imports (No Cycle Risk):**
- `...shared.*` (shared utilities, config, schema)
- `..normalize` (normalization utilities)
- `..job_manager` (job status updates)
- `..job_store` (job storage)

---

## Module-Level Globals Analysis

**Globals Used:**
- `logger` - Used by all nodes (safe, no coupling)
- `telemetry_emitter` - Used by all nodes (safe, no coupling)
- `role_registry` - Used by cartographer, critic, synthesizer (safe, no coupling)
- `_project_service` - Lazy singleton (medium coupling, Arango dependency)
- `_synthesis_service` - Lazy singleton (medium coupling, Arango dependency)
- `BACKPRESSURE_THRESHOLD_*` - Constants (safe, no coupling)

**Global Access Pattern:**
- Most nodes access `telemetry_emitter` and `logger` (can be injected)
- `_project_service` and `_synthesis_service` are lazy-initialized to avoid circular deps
- Consider dependency injection for services to reduce coupling

---

## Flask/FastAPI Request Context

**No Flask/FastAPI Dependencies Found:**
- ✅ No `request.` or `g.` usage
- ✅ No Flask context dependencies
- ✅ All nodes operate on `ResearchState` dict (pure functions)

**Safe for Refactoring:**
- Nodes are stateless functions that take `ResearchState` as input
- No request context coupling

