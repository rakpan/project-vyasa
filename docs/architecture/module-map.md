# Orchestrator Nodes Module Map

This document describes the organization of workflow nodes in `src/orchestrator/nodes/` and provides guidance for where new nodes should be added.

## Module Organization

The nodes package is organized by **domain responsibility** rather than technical layer. Each module contains nodes and utilities related to a specific research workflow phase.

### Core Modules

#### `base.py` - Shared Prompt Wrappers
**Purpose**: Base utilities for LLM-powered nodes.

**Contents**:
- `wrap_prompt_with_context()` - Injects ProjectConfig (thesis, RQs, anti-scope) into system prompts

**Dependencies**: None (pure utility)

**When to use**: All LLM-powered nodes should use `wrap_prompt_with_context()` to ensure project context is injected.

---

#### `nodes.py` - Compatibility Shim & Shared Infrastructure
**Purpose**: Compatibility shim providing shared utilities used across node modules.

**Contents**:
- **Shared Utilities** (used by multiple modules):
  - `validate_state_schema()` - Validates ResearchState has required fields
  - `hydrate_project_context()` - Fetches ProjectConfig from DB if missing
  - `route_to_expert()` - Routes nodes to appropriate expert services
  - `call_expert_with_fallback()` - Calls expert services with retry/fallback
  - `check_kv_backpressure()` - Checks KV cache utilization before LLM calls
  - `_get_project_service()` - Lazy singleton for ProjectService
- **Infrastructure Nodes**:
  - `failure_cleanup_node()` - Terminal failure handler
- **Module-level Constants**:
  - `ExpertType`, `NODE_EXPERT_MAP` (from `..config`)
  - `telemetry_emitter`, `logger`, `role_registry`
  - `requests`, `ArangoClient`, `interrupt` (for test compatibility)

**Dependencies**: 
- Imports from `..config`, `..state`, `..telemetry`
- Does NOT import from other node modules (to avoid circular dependencies)

**When to add here**: 
- Shared utilities used by 2+ node modules
- Infrastructure nodes that don't fit a specific domain
- Module-level constants/instances needed for test compatibility

---

#### `cartography.py` - Knowledge Extraction
**Purpose**: Extract structured knowledge from text using RQ-scoped retrieval.

**Contents**:
- `cartographer_node()` - Main extraction node
- Helper functions: `_query_established_knowledge()`, `_query_candidate_knowledge()`, `_filter_conflicting_canonical()`

**Dependencies**:
- Imports from `.base` (for `wrap_prompt_with_context`)
- Imports from `.nodes` (for `validate_state_schema`, `hydrate_project_context`, `route_to_expert`, `call_expert_with_fallback`)
- Imports from `..storage.qdrant`, `..storage.arango`

**When to add here**: Nodes that extract claims, triples, or entities from source documents.

---

#### `quality.py` - Governance & Validation
**Purpose**: Quality gates, conflict detection, and validation.

**Contents**:
- `critic_node()` - Validates extraction quality and detects conflicts
- `reframing_node()` - Proposes research direction pivots
- `tone_validator_node()` - Validates and rewrites tone
- Helper functions: `_detect_quantization_failure()`, `_build_conflict_report()`, `_stable_fact_id()`

**Dependencies**:
- Imports from `.base` (for `wrap_prompt_with_context`)
- Imports from `.nodes` (for shared utilities)
- Imports from `..guards.*`, `..conflict_utils`, `..storage.arango`

**When to add here**: Nodes that validate, critique, or govern outputs from other nodes.

---

#### `synthesis.py` - Manuscript Generation
**Purpose**: Synthesize verified claims into manuscript blocks.

**Contents**:
- `synthesizer_node()` - Generates manuscript blocks with citation integrity
- `lead_counsel_node()` - Strategic triage (summary vs detail)
- `logician_node()` - Mathematical autoformalization

**Dependencies**:
- Imports from `.base` (for `wrap_prompt_with_context`)
- Imports from `.nodes` (for `validate_state_schema`, `hydrate_project_context`)
- Imports from `..validators.citation_integrity`

**When to add here**: Nodes that generate or transform manuscript content.

---

#### `export.py` - Persistence & Artifacts
**Purpose**: Persist extracted graphs and compile artifact manifests.

**Contents**:
- `saver_node()` - Persists extracted graphs to ArangoDB
- `artifact_registry_node()` - Compiles and persists artifact manifests

**Dependencies**:
- Imports from `.nodes` (for `validate_state_schema`)
- Imports from `..artifacts.manifest_builder`
- Imports from `..storage.arango` (via ArangoClient)

**When to add here**: Nodes that persist state to databases or generate artifact summaries.

---

#### `utils.py` - Cross-Cutting Utilities
**Purpose**: Utility nodes that don't fit a specific domain.

**Contents**:
- `vision_node()` - Processes images using vision models
- Helper functions: `select_images_for_vision()`, `build_vision_context()`

**Dependencies**:
- Imports from `.nodes` (for `validate_state_schema`)
- Imports from `..config`, `..telemetry`

**When to add here**: Utility nodes that provide cross-cutting functionality (e.g., vision, audio processing).

---

## Dependency Rules

### ✅ Allowed Dependencies

1. **Node modules → `base.py`**: All LLM-powered nodes should use `wrap_prompt_with_context()`
2. **Node modules → `nodes.py`**: Can import shared utilities (`validate_state_schema`, `hydrate_project_context`, `route_to_expert`, `call_expert_with_fallback`)
3. **Node modules → Parent modules**: Can import from `..storage.*`, `..guards.*`, `..validators.*`, `..artifacts.*`, etc.
4. **Node modules → Shared**: Can import from `...shared.*`

### ❌ Prohibited Dependencies

1. **Node modules → Other node modules**: 
   - `cartography.py` must NOT import from `quality.py`, `synthesis.py`, `export.py`
   - `quality.py` must NOT import from `cartography.py`, `synthesis.py`, `export.py`
   - `synthesis.py` may import from `quality.py` validators (one-way dependency)
   - `export.py` must NOT import from other node modules
   
   **Rationale**: Prevents circular imports and maintains clear domain boundaries.

2. **`nodes.py` → Node modules**: 
   - `nodes.py` must NOT import node functions from other modules (except for re-exports in comments)
   - Re-exports are handled in `__init__.py` to avoid circular dependencies

### Exception: One-Way Dependencies

- **Synthesis → Quality**: `synthesis.py` may call quality validators (e.g., citation integrity) but quality must not import synthesis.

---

## Adding New Nodes

### Step 1: Identify the Domain

Ask: "What is this node's primary responsibility?"

- **Extraction** → `cartography.py`
- **Validation/Governance** → `quality.py`
- **Generation/Synthesis** → `synthesis.py`
- **Persistence** → `export.py`
- **Utility** → `utils.py`
- **Infrastructure** → `nodes.py` (if used by multiple modules)

### Step 2: Check Dependencies

- Can you implement it using only `.base`, `.nodes` utilities, and parent modules?
- If you need functionality from another node module, consider:
  - Moving shared logic to `nodes.py` (if used by 2+ modules)
  - Creating a new shared utility module
  - Re-evaluating the domain assignment

### Step 3: Update Exports

1. Add the function to the appropriate module
2. Update `nodes/__init__.py` to import and re-export
3. Add to `__all__` in `__init__.py`
4. Update `nodes.py` comments if needed (for documentation)

### Step 4: Write Tests

- Create tests in `src/tests/unit/orchestrator/test_<module>_<node>.py`
- Import from `src.orchestrator.nodes` (package level) for backward compatibility
- Mock dependencies at their source (see test mocking protocol in repo rules)

---

## Module Size Guidelines

- **Target**: Each module should be 200-500 lines
- **Maximum**: 800 lines (if exceeded, consider splitting)
- **`nodes.py`**: Should remain a thin shim (< 400 lines)

---

## Backward Compatibility

All node functions are re-exported from `nodes/__init__.py`, so existing imports continue to work:

```python
# These all work:
from src.orchestrator.nodes import cartographer_node
from src.orchestrator.nodes import critic_node
from src.orchestrator.nodes import synthesizer_node
from src.orchestrator.nodes import saver_node
```

Internal imports (for shared utilities) should use explicit module paths:

```python
# In cartography.py:
from .nodes import validate_state_schema, hydrate_project_context
from .base import wrap_prompt_with_context
```

---

## Migration History

- **v1.0**: Monolithic `nodes.py` (~2000 lines)
- **v1.1**: Extracted `cartography.py` (knowledge extraction)
- **v1.2**: Extracted `quality.py` (governance), `utils.py` (vision utilities)
- **v1.3**: Extracted `synthesis.py` (manuscript generation)
- **v1.4**: Extracted `export.py` (persistence), `nodes.py` reduced to compatibility shim

---

## Future Considerations

Potential future modules:
- `routing.py` - If routing logic grows beyond `route_to_expert()`
- `checkpointing.py` - If checkpoint/state management becomes complex
- `monitoring.py` - If telemetry/observability nodes are added

When considering a new module, ensure:
1. It has a clear domain boundary
2. It won't create circular dependencies
3. It will be used by multiple nodes or is a distinct workflow phase

