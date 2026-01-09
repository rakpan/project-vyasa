# Orchestration Specification: Perspectives, Blueprint, and Rerank Integration

**Purpose**: Exact specification of orchestration behavior for Analytical Notes, Manuscript Blueprint, and Reranker integration in section synthesis loop.

**Date**: 2025-01-XX  
**Status**: Planning-only (no code changes)

**Author**: Architecture Team  
**Review Status**: Draft

Authoritative references (for “should”):
- Retrieval + evidence gating: `docs/architecture/09-retrieval-evidence-selection.md`
- Citation + compilation: `docs/architecture/10-citation-compilation.md`
- Manuscript persistence + lifecycle: `docs/architecture/11-manuscript-persistence-lifecycle.md`

Note: schema excerpts below are illustrative; canonical schemas live in code under `src/orchestrator/schemas/`.

---

## Table of Contents

1. [New Pipeline Objects](#1-new-pipeline-objects)
2. [Section Synthesis Loop](#2-section-synthesis-loop)
3. [Failure Modes](#3-failure-modes)
4. [State Diagrams](#4-state-diagrams)
5. [Sequence Diagrams](#5-sequence-diagrams)
6. [Configuration Defaults](#6-configuration-defaults)
7. [Data Flow Contracts](#7-data-flow-contracts)

---

## 1. New Pipeline Objects

### 1.1 AnalyticalNote Schema

**Location**: `src/orchestrator/schemas/analytical_notes.py`

**Purpose**: User-authored perspectives, analogies, glossaries, and framing ideas. **NEVER directly citeable as evidence**. Influences style and pedagogy only.

**Schema**:
```python
class NoteState(str, Enum):
    DRAFT = "Draft"              # Initial state, not yet cross-examined
    MANUSCRIPT = "Manuscript"    # After Critic cross-examination and promotion

class AnalyticalNote(BaseModel):
    # Identifiers
    note_id: str                 # UUID (primary key)
    project_id: str              # Project identifier (indexed, required)
    
    # Content
    text: str                    # Note text content (required, non-empty)
    tags: List[str]              # Tags for categorization (default: [])
    
    # State and promotion
    state: NoteState             # State: DRAFT (default) or MANUSCRIPT
    critic_flags: List[str]      # Flags from Critic cross-examination (default: [])
    promotion_reason: Optional[str]  # Reason for promotion (if MANUSCRIPT, required)
    
    # Linking
    linked_rq: Optional[str]     # Linked research question ID (e.g., "RQ1", "RQ2")
    source_ref: Optional[str]    # External source reference (not citeable, for context only)
    
    # Metadata
    created_at: str              # ISO timestamp (UTC, required)
    updated_at: str              # ISO timestamp (UTC, required)
    created_by: Optional[str]    # User identifier (if available)
```

**Storage**: ArangoDB collection `"analytical_notes"` (indexed by `project_id`, `linked_rq`, `state`, `tags`)

**Invariants**:
- `text` must be non-empty
- `state = MANUSCRIPT` → `promotion_reason` must be present
- `state = MANUSCRIPT` → `critic_flags` may be empty (no flags) or non-empty (flagged but promoted)
- `note_id` is stable (UUIDv4)

**State Transitions**: See Section 4.1 (State Diagram)

---

### 1.2 ManuscriptBlueprint Schema

**Location**: `src/orchestrator/schemas/blueprint.py`

**Purpose**: Governor for section-driven synthesis. Defines structure and constraints for manuscript generation.

**Schema**:
```python
class JournalSlot(str, Enum):
    INTRODUCTION = "introduction"
    METHODS = "methods"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"
    ABSTRACT = "abstract"
    BACKGROUND = "background"
    RELATED_WORK = "related_work"

class DepthIntent(str, Enum):
    HOOK = "hook"        # Attention-grabbing opening
    PROOF = "proof"      # Detailed evidence and citations
    SO_WHAT = "so_what"  # Interpretation and implications

class VisualAnchor(BaseModel):
    anchor_id: str                           # UUID (unique within section)
    anchor_type: str                         # "table", "figure", or "equation"
    placeholder_text: str                    # Placeholder text for manual completion
    candidate_evidence_cluster_ids: List[str] # Evidence cluster IDs that could fill this anchor (default: [])
    auto_generate: bool                      # Whether to auto-generate from evidence (default: False)

class BlueprintSection(BaseModel):
    section_id: str                    # UUID (unique within blueprint)
    heading: str                       # Section heading (required, non-empty)
    journal_slot: JournalSlot          # Journal section slot (required)
    linked_rqs: List[str]              # Research question IDs (e.g., ["RQ1", "RQ2"], default: [])
    evidence_cluster_ids: List[str]    # Evidence cluster IDs for this section (default: [])
    depth_intent: DepthIntent          # Depth intent for synthesis (default: PROOF)
    visual_anchors: List[VisualAnchor] # Visual anchors (tables/figures) for this section (default: [])
    conclusion_rules: Optional[str]    # Rules for section conclusion (optional)

class ManuscriptBlueprint(BaseModel):
    # Identifiers
    blueprint_id: str                  # UUID (primary key)
    project_id: str                    # Project identifier (indexed, required)
    
    # Structure
    sections: List[BlueprintSection]   # Blueprint sections (ordered, default: [])
    
    # Metadata
    target_journal: Optional[str]      # Target journal profile (optional)
    created_at: str                    # ISO timestamp (UTC, required)
    updated_at: str                    # ISO timestamp (UTC, required)
    version: int                       # Blueprint version (default: 1, increments on update)
```

**Storage**: ArangoDB collection `"manuscript_blueprints"` (indexed by `project_id`, `version`)

**Invariants**:
- `project_id` must reference existing project
- `sections` list determines synthesis order (preserve order)
- Each `section_id` must be unique within blueprint
- `linked_rqs` must reference valid RQ IDs from `ProjectConfig.research_questions`

**Validation Rules**:
- `heading` must be non-empty
- `journal_slot` must be valid enum value
- `linked_rqs` must be non-empty for sections with `depth_intent = PROOF`
- `visual_anchors` may be empty (placeholders can be added later)

---

### 1.3 RetrievalBundle Schema

**Location**: `src/orchestrator/schemas/retrieval.py`

**Purpose**: Reproducible evidence selection artifact. Tracks full retrieval pipeline for audit and reproducibility.

**Schema**:
```python
class RetrievalBundle(BaseModel):
    # Identifiers
    bundle_id: str                     # UUID (primary key)
    query_id: Optional[str]            # Query identifier (if part of a query sequence)
    project_id: str                    # Project identifier (indexed, required)
    section_id: Optional[str]          # Blueprint section ID (if applicable, indexed)
    
    # Query metadata
    query_text: str                    # The search query used (required, non-empty)
    query_source: str                  # Source of query: "blueprint_section", "manual", "rq_scoped" (required)
    linked_rqs: List[str]              # Research question IDs linked to this query (default: [])
    
    # Retrieval pipeline results
    candidate_chunks: List[Dict[str, Any]]  # Top-K chunks from Qdrant (before reranking, default: [])
    reranked_chunks: List[Dict[str, Any]]   # Top-M chunks after reranking (Evidence Packet A, default: [])
    
    # Scores and metadata
    embed_scores: Optional[List[float]]     # Embedding scores for candidate_chunks (optional)
    rerank_scores: Optional[List[float]]    # Reranker scores for reranked_chunks (optional)
    
    # Model versions (for reproducibility)
    embedder_model_id: str             # Embedder model ID (e.g., "nvidia/nv-embedqa-e5-v5", required)
    reranker_model_id: str             # Reranker model ID (e.g., "nvidia/llama-3.2-nv-rerankqa-1b-v2", required)
    
    # Pipeline parameters
    top_k_embed: int                   # Number of chunks retrieved from Qdrant (K, required, >= 1)
    top_k_rerank: int                  # Number of chunks returned after reranking (M, required, >= 1)
    
    # Timestamps
    created_at: str                    # ISO timestamp (UTC, required)
    version: int                       # Bundle version (default: 1, increments on update)
    
    # Provenance markers
    rerank_skipped: bool               # True if reranker was skipped (default: False)
    rerank_error: Optional[str]        # Error message if reranker failed (optional)
```

**Storage**: ArangoDB collection `"retrieval_bundles"` (indexed by `project_id`, `section_id`, `created_at`)

**Chunk Format** (in `candidate_chunks` and `reranked_chunks`):
```python
{
    "chunk_id": str,                   # SHA256 hash of {file_hash}|{page_number}|{chunk_index}
    "text_content": str,               # Chunk text content
    "payload": Dict[str, Any],         # Full Qdrant payload:
    #   - file_hash: str
    #   - ingestion_id: str
    #   - project_id: str
    #   - page_number: int
    #   - chunk_index: int
    #   - bbox: Optional[Dict[str, float]]
    "score": float,                    # Embedding score (for candidate_chunks)
    "rerank_score": Optional[float],   # Reranker score (for reranked_chunks)
    "rerank_rank": Optional[int],      # Reranker rank (1-based, for reranked_chunks)
}
```

**Invariants**:
- `top_k_embed >= top_k_rerank` (K >= M)
- `len(candidate_chunks) <= top_k_embed`
- `len(reranked_chunks) <= top_k_rerank`
- `rerank_skipped = True` → `rerank_error` may be present, `rerank_scores = None`
- `rerank_skipped = False` → `rerank_error = None`, `rerank_scores` may be present

**Reproducibility**:
- `embedder_model_id` and `reranker_model_id` enable reproducibility
- `query_text` and `linked_rqs` enable query reconstruction
- `candidate_chunks` and `reranked_chunks` enable evidence traceability

---

## 2. Section Synthesis Loop

### 2.1 Overview

The section synthesis loop processes each blueprint section sequentially, producing a manuscript block with full provenance. The loop is executed once per section in the blueprint's `sections` list, preserving order.

**Entry Point**: `blueprint_synthesis_node(state: ResearchState) -> ResearchState`

**Location**: `src/orchestrator/nodes/blueprint_synthesis.py` (to be created)

**Input**: `ResearchState` with:
- `project_id`: str
- `project_config`: ProjectConfig
- `blueprint`: ManuscriptBlueprint (optional, loaded from DB if not present)
- `ingestion_id`: Optional[str] (required for retrieval)

**Output**: `ResearchState` with:
- `manuscript_blocks`: List[ManuscriptBlock] (one per section)
- `retrieval_bundles`: List[RetrievalBundle] (one per section)
- `analytical_note_promotions`: List[Dict] (promotions from Critic)

---

### 2.2 Step-by-Step Process (Per Section)

#### Step 1: Build Section Query

**Function**: `_build_section_query(section: BlueprintSection, project_config: ProjectConfig) -> str`

**Process**:
1. Extract `heading` from section
2. Extract `journal_slot` from section
3. Extract `linked_rqs` from section → resolve RQ texts from `project_config.research_questions`
4. Extract `depth_intent` from section

**Query Template**:
```
For {journal_slot} section "{heading}":
- Research Questions: {rq_texts (joined with "; ")}
- Depth Intent: {depth_intent}
- Goal: {hook/proof/so-what description based on depth_intent}
```

**Examples**:
- `depth_intent = HOOK`: "Attention-grabbing opening for Introduction section 'Background': Research Questions: What are the most common injection vulnerabilities?; How effective are input validation mechanisms?"
- `depth_intent = PROOF`: "Detailed evidence and citations for Results section 'Experimental Findings': Research Questions: What are the most common injection vulnerabilities?"
- `depth_intent = SO_WHAT`: "Interpretation and implications for Discussion section 'Analysis': Research Questions: How effective are input validation mechanisms?"

**Output**: `query_text: str` (the constructed query string)

---

#### Step 2: Retrieve Candidates (Embed Recall)

**Function**: `_retrieve_candidates(query_text: str, project_id: str, ingestion_id: str, top_k: int) -> List[Dict]`

**Process**:
1. **Embed Query**:
   - Call embedder service: `POST {EMBEDDER_URL}/embed`
   - Payload: `{"texts": [query_text]}`
   - Extract: `query_vector = response["embeddings"][0]`
   - **Timeout**: 10 seconds
   - **Error Handling**: If embedder fails, raise `RetrievalError("Embedder service unavailable")`

2. **Qdrant Search**:
   - Build filter: `{"project_id": project_id, "ingestion_id": ingestion_id}` (if ingestion_id provided)
   - Call: `qdrant_client.search(collection_name="document_chunks", query_vector=query_vector, query_filter=filter, limit=top_k, with_payload=True)`
   - **Timeout**: 15 seconds
   - **Error Handling**: If Qdrant fails, raise `RetrievalError("Qdrant service unavailable")`

3. **Format Results**:
   - For each hit:
     ```python
     {
         "chunk_id": str(hit.id),
         "text_content": hit.payload.get("text_content", ""),
         "payload": hit.payload,
         "score": hit.score,
         "file_hash": hit.payload.get("file_hash"),
         "ingestion_id": hit.payload.get("ingestion_id"),
         "page_number": hit.payload.get("page_number"),
         "bbox": hit.payload.get("bbox"),
         "chunk_index": hit.payload.get("chunk_index"),
     }
     ```

**Configuration**: `top_k = RETRIEVAL_TOP_K_EMBED` (default: 64, see Section 6.1)

**Output**: `candidate_chunks: List[Dict]` (top-K chunks, sorted by embedding score descending)

**Error Handling**: If embedder or Qdrant fails, section run fails with `SectionSynthesisError("Retrieval failed: {error_message}")`

---

#### Step 3: Rerank (Top-K → Top-M)

**Function**: `_rerank_candidates(query_text: str, candidate_chunks: List[Dict], top_m: int, reranker_mandatory: bool) -> Tuple[List[Dict], bool, Optional[str]]`

**Process**:
1. **Check Feature Flag**:
   - Read: `RERANKER_MANDATORY = os.getenv("RERANKER_MANDATORY", "false").lower() == "true"`
   - Read: `RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() == "true"`

2. **If Reranker Disabled** (`RERANKER_ENABLED = False`):
   - Return: `(candidate_chunks[:top_m], True, None)` (use top-M by embedding score)
   - Mark: `rerank_skipped = True`, `rerank_error = None`

3. **If Reranker Enabled**:
   - **Prepare Documents**:
     - For each chunk in `candidate_chunks`:
       ```python
       {
           "text": chunk["text_content"],
           "chunk_id": chunk["chunk_id"],
           "metadata": chunk["payload"],
       }
       ```
   - **Call Reranker**:
     - Endpoint: `POST {RERANKER_URL}/rerank`
     - Payload:
       ```json
       {
           "query": query_text,
           "documents": documents_list,
           "top_k": top_m
       }
       ```
     - **Timeout**: 30 seconds
     - **Error Handling**:
       - If `RERANKER_MANDATORY = True` and reranker fails:
         - Raise `SectionSynthesisError("Reranker is mandatory but unavailable: {error_message}")`
       - If `RERANKER_MANDATORY = False` and reranker fails:
         - Log warning: `"Reranker failed, falling back to embed-only"`
         - Return: `(candidate_chunks[:top_m], True, error_message)` (use top-M by embedding score)
         - Mark: `rerank_skipped = True`, `rerank_error = error_message`

4. **Process Reranker Response**:
   - Extract: `results = response["results"]` (sorted by score descending)
   - Merge with original chunks:
     ```python
     for reranked_item in results:
         chunk_id = reranked_item.get("chunk_id")
         original_chunk = find_chunk_by_id(candidate_chunks, chunk_id)
         merged = {
             **original_chunk,
             "rerank_score": reranked_item["score"],
             "rerank_rank": reranked_item["rank"],
             "score": reranked_item["score"],  # Update primary score to rerank score
         }
     ```
   - Return: `(reranked_chunks, False, None)` (rerank succeeded)
   - Mark: `rerank_skipped = False`, `rerank_error = None`

**Configuration**: `top_m = RETRIEVAL_TOP_K_RERANK` (default: 16, see Section 6.1)

**Output**: `(reranked_chunks: List[Dict], rerank_skipped: bool, rerank_error: Optional[str])`

---

#### Step 4: Build Packet A (Primary Sources)

**Function**: `_build_packet_a(reranked_chunks: List[Dict]) -> List[Dict]`

**Process**:
1. For each chunk in `reranked_chunks`:
   - Extract: `chunk_id`, `text_content`, `file_hash`, `page_number`, `bbox`, `payload`
   - Build citation handle:
     ```python
     citation_handle = {
         "chunk_id": chunk_id,
         "page": page_number,
         "source": file_hash[:16],  # Short hash for readability
         "bbox": bbox,  # If available
     }
     ```
   - Build snippet:
     ```python
     snippet = {
         "text": text_content[:500],  # Truncate to 500 chars
         "citation": citation_handle,
         "full_chunk": chunk,  # Include full chunk for context
     }
     ```
   - Append to `packet_a: List[Dict]`

2. **Sort**: By `rerank_rank` (if available) or `score` (descending)

**Output**: `packet_a: List[Dict]` (top-M chunks with citations)

**Format**:
```python
[
    {
        "text": str,              # Chunk text (truncated to 500 chars)
        "citation": {
            "chunk_id": str,
            "page": int,
            "source": str,        # Short file hash
            "bbox": Optional[Dict],
        },
        "full_chunk": Dict,       # Full chunk data for context
    },
    ...
]
```

---

#### Step 5: Build Packet B (Analytical Notes)

**Function**: `_build_packet_b(project_id: str, section: BlueprintSection, state_filter: str = "Draft") -> List[Dict]`

**Process**:
1. **Query Analytical Notes**:
   - ArangoDB query:
     ```aql
     FOR note IN analytical_notes
     FILTER note.project_id == @project_id
     FILTER note.state == @state_filter
     FILTER (@linked_rq IN note.linked_rq OR note.linked_rq == @linked_rq OR note.linked_rq == null)
     FILTER (@tags ANY IN note.tags OR LENGTH(note.tags) == 0)
     SORT note.created_at DESC
     LIMIT @limit
     RETURN note
     ```
   - Parameters:
     - `project_id`: project_id
     - `state_filter`: `"Draft"` (default) or `"Manuscript"`
     - `linked_rq`: any RQ from `section.linked_rqs` (if non-empty)
     - `tags`: any tag from section tags (if available)
     - `limit`: `ANALYTICAL_NOTES_LIMIT` (default: 10, see Section 6.1)

2. **Filter by Relevance** (optional, future enhancement):
   - Use semantic similarity to filter notes relevant to section heading
   - For now: use tag/RQ matching only

3. **Format Notes**:
   - For each note:
     ```python
     {
         "note_id": note.note_id,
         "text": note.text,
         "tags": note.tags,
         "linked_rq": note.linked_rq,
         "state": note.state,
         "source_ref": note.source_ref,  # For context only, not citeable
     }
     ```

**Configuration**: `limit = ANALYTICAL_NOTES_LIMIT` (default: 10)

**Output**: `packet_b: List[Dict]` (relevant Analytical Notes)

**Note**: Packet B is **NOT citeable**. It influences style, analogies, and pedagogy only. Hard rule: All factual claims must come from Packet A.

---

#### Step 6: Synthesizer Call (Nemotron 49B)

**Function**: `_synthesize_section(section: BlueprintSection, packet_a: List[Dict], packet_b: List[Dict], project_config: ProjectConfig) -> str`

**Process**:
1. **Build Prompt**:
   - Fetch system prompt from Prompt Registry: `get_active_prompt_with_meta("vyasa-blueprint-synthesizer", DEFAULT_BLUEPRINT_SYNTHESIZER_PROMPT)`
   - Wrap with ProjectConfig context: `wrap_prompt_with_context(state, system_template)`

2. **Construct User Message** (Sandwich Pattern):
   ```
   Section: {section.heading}
   Journal Slot: {section.journal_slot}
   Depth Intent: {section.depth_intent}
   
   EVIDENCE PACKET A (Primary Sources - MUST be cited):
   {Format packet_a with citations:
   [1] {text} (chunk_id: {chunk_id}, page {page}, source: {source})
   [2] {text} ...
   }
   
   ANALYTICAL NOTES PACKET B (Perspectives - Influence style only, NOT citeable):
   {Format packet_b:
   Note 1: {text} (tags: {tags}, linked RQ: {linked_rq})
   Note 2: {text} ...
   }
   
   CRITICAL RULES:
   1. All factual claims and citations MUST come from Packet A (Primary Sources).
   2. Packet B (Analytical Notes) may influence style, analogies, and pedagogy ONLY.
   3. Use sandwich pattern:
      - HOOK: Attention-grabbing opening (if depth_intent = HOOK)
      - PROOF: Detailed evidence with citations from Packet A (if depth_intent = PROOF)
      - SO_WHAT: Interpretation and implications (if depth_intent = SO_WHAT)
   4. Include inline citations: [[chunk_id]] for each claim from Packet A.
   5. Do NOT cite Packet B directly. Use it to guide framing and style.
   
   Generate the section text in Markdown format.
   ```

3. **Call LLM**:
   - Service: Brain (Nemotron 49B) via `call_expert_with_fallback()`
   - Model: `TEXT_MODEL_ID` (default: `"nvidia/Llama-3_3-Nemotron-Super-49B-v1_5"`)
   - Timeout: 60 seconds
   - Max tokens: `CONTEXT_LIMIT_BRAIN` (default: 32768)
   - Temperature: 0.7 (for creative synthesis)
   - Fallback: Worker (if Brain unavailable)

4. **Parse Response**:
   - Extract section text from LLM response
   - Validate: Text is non-empty, contains at least one citation marker `[[chunk_id]]`
   - **Error Handling**: If no citations found, log warning (non-fatal in exploratory mode, fatal in conservative mode)

**Output**: `section_text: str` (Markdown-formatted section content)

**Error Handling**: If LLM fails, section run fails with `SectionSynthesisError("Synthesis failed: {error_message}")`

---

#### Step 7: Critic Call (Nemotron 49B)

**Function**: `_criticize_section(section_text: str, packet_a: List[Dict], packet_b: List[Dict], rigor_level: str) -> Tuple[List[str], List[Dict]]`

**Process**:
1. **Build Prompt**:
   - Fetch system prompt from Prompt Registry: `get_active_prompt_with_meta("vyasa-blueprint-critic", DEFAULT_BLUEPRINT_CRITIC_PROMPT)`
   - Wrap with ProjectConfig context

2. **Construct User Message**:
   ```
   Section Draft:
   {section_text}
   
   Evidence Packet A (Primary Sources - Ground Truth):
   {Format packet_a with full citations}
   
   Analytical Notes Packet B (Perspectives - NOT citeable):
   {Format packet_b}
   
   CRITICAL VALIDATION RULES:
   1. Check that ALL citations [[chunk_id]] in section_text reference chunks in Packet A.
   2. Flag any factual claims that cannot be traced to Packet A.
   3. Flag any analogies/framing in section_text that go beyond what's supported by Packet A.
   4. For each Analytical Note in Packet B:
      - Check if note's framing/style is used appropriately (influences style, not facts).
      - If note's framing is used AND supported by Packet A evidence:
        → Propose promotion: Draft Note → Manuscript Note (with reason + linked evidence).
      - If note's framing goes beyond Packet A:
        → Flag as "overreach" (do not promote).
   
   Return JSON:
   {
       "flags": ["flag1", "flag2", ...],
       "promotions": [
           {
               "note_id": "uuid",
               "reason": "Framing supported by evidence chunks [chunk_id1, chunk_id2]",
               "linked_evidence": ["chunk_id1", "chunk_id2"]
           },
           ...
       ]
   }
   ```

3. **Call LLM**:
   - Service: Brain (Nemotron 49B) via `call_expert_with_fallback()`
   - Model: `TEXT_MODEL_ID`
   - Timeout: 60 seconds
   - Temperature: 0.3 (for deterministic validation)
   - **Structured Output**: Require strict JSON response (use schema constraint if available)

4. **Parse Response**:
   - Extract: `flags: List[str]`, `promotions: List[Dict]`
   - Validate JSON structure
   - **Error Handling**: If JSON parsing fails, log warning and return empty lists (non-fatal)

**Output**: `(flags: List[str], promotions: List[Dict])`

**Promotion Format**:
```python
{
    "note_id": str,                  # UUID of AnalyticalNote to promote
    "reason": str,                   # Reason for promotion (required)
    "linked_evidence": List[str],    # Chunk IDs from Packet A that support the promotion (required)
}
```

---

#### Step 8: Persist

**Function**: `_persist_section_results(section_id: str, retrieval_bundle: RetrievalBundle, section_draft: ManuscriptBlock, promotions: List[Dict], flags: List[str]) -> None`

**Process**:
1. **Persist RetrievalBundle**:
   - ArangoDB collection: `"retrieval_bundles"`
   - Document key: `retrieval_bundle.bundle_id`
   - Insert/update: `db.collection("retrieval_bundles").insert(retrieval_bundle.model_dump())`
   - **Error Handling**: Log warning if persistence fails (non-fatal, section run continues)

2. **Persist SectionDraft Block**:
   - ArangoDB collection: `"manuscript_blocks"`
   - Document key: `f"{project_id}_{section_draft.block_id}_v{section_draft.version}"`
   - Insert: `ManuscriptService.save_block(section_draft, project_id, validate_citations=True)`
   - **Error Handling**: If persistence fails, section run fails with `SectionSynthesisError("Block persistence failed: {error_message}")`

3. **Apply Promotions** (Analytical Notes):
   - For each promotion in `promotions`:
     - Query: `db.collection("analytical_notes").find({"_key": promotion["note_id"]})`
     - Update:
       ```python
       {
           "state": "Manuscript",
           "promotion_reason": promotion["reason"],
           "critic_flags": flags,  # Include all flags (may be empty)
           "updated_at": datetime.now(timezone.utc).isoformat(),
       }
       ```
     - **Error Handling**: Log warning if note not found (non-fatal, skip promotion)

4. **Write Flags to Analytical Notes** (if any):
   - For notes referenced in `packet_b`:
     - If flags exist, append to `critic_flags` (if not already present)
     - Update: `db.collection("analytical_notes").update({"_key": note_id}, {"critic_flags": updated_flags})`

**Output**: None (side effects: DB writes)

**Error Handling**:
- RetrievalBundle persistence failure: Log warning, continue
- SectionDraft persistence failure: Fail section run
- Promotion failure: Log warning, continue (promotions are best-effort)

---

### 2.3 Section Loop Orchestration

**Function**: `blueprint_synthesis_node(state: ResearchState) -> ResearchState`

**Process**:
1. **Load Blueprint** (if not in state):
   - Query: `db.collection("manuscript_blueprints").find({"project_id": project_id, "version": latest})`
   - If not found, raise `BlueprintNotFoundError("No blueprint found for project {project_id}")`
   - Store in state: `state["blueprint"] = blueprint`

2. **Initialize Accumulators**:
   - `manuscript_blocks: List[ManuscriptBlock] = []`
   - `retrieval_bundles: List[RetrievalBundle] = []`
   - `analytical_note_promotions: List[Dict] = []`

3. **Iterate Sections** (preserve order):
   - For each `section` in `blueprint.sections`:
     - Try:
       - Execute Steps 1-8 (per section)
       - Append `section_draft` to `manuscript_blocks`
       - Append `retrieval_bundle` to `retrieval_bundles`
       - Append `promotions` to `analytical_note_promotions`
     - Except `SectionSynthesisError`:
       - Log error: `"Section {section.section_id} failed: {error_message}"`
       - **If `RIGOR_LEVEL = conservative`**: Fail entire loop (return error state)
       - **If `RIGOR_LEVEL = exploratory`**: Continue to next section (skip failed section)

4. **Update State**:
   - `state["manuscript_blocks"] = manuscript_blocks`
   - `state["retrieval_bundles"] = retrieval_bundles`
   - `state["analytical_note_promotions"] = analytical_note_promotions`

5. **Return State**

**Output**: Updated `ResearchState` with synthesis results

---

## 3. Failure Modes

### 3.1 Reranker Failures

#### Scenario 1: Reranker Mandatory, Service Down

**Condition**: `RERANKER_MANDATORY = true` AND reranker service unavailable (HTTP 503, timeout, or connection error)

**Behavior**:
- **Action**: Fail section run immediately
- **Error**: `SectionSynthesisError("Reranker is mandatory but unavailable: {error_message}")`
- **State**: Section synthesis stops, no block generated for this section
- **Rigor Level**:
  - `conservative`: Fail entire blueprint synthesis loop (stop all sections)
  - `exploratory`: Skip failed section, continue with remaining sections

**Logging**: ERROR level with full error context

---

#### Scenario 2: Reranker Optional, Service Down

**Condition**: `RERANKER_MANDATORY = false` AND reranker service unavailable

**Behavior**:
- **Action**: Fall back to embed-only retrieval
- **RetrievalBundle**: Mark `rerank_skipped = True`, `rerank_error = error_message`
- **Chunks**: Use top-M by embedding score (no reranking)
- **Logging**: WARNING level with error context
- **Provenance**: `RetrievalBundle.rerank_skipped = True` ensures audit trail

**State**: Section synthesis continues normally, block generated with embed-only provenance

---

#### Scenario 3: Reranker Response Invalid

**Condition**: Reranker service responds but JSON is malformed or missing required fields

**Behavior**:
- **Action**: Same as Scenario 2 (fall back to embed-only)
- **Error Handling**: Log WARNING, parse error from response if available
- **RetrievalBundle**: Mark `rerank_skipped = True`, `rerank_error = "Invalid response format"`

---

### 3.2 Embedder Failures

#### Scenario 4: Embedder Service Down

**Condition**: Embedder service unavailable (HTTP 503, timeout, or connection error)

**Behavior**:
- **Action**: Fail section run immediately (embedder is always mandatory)
- **Error**: `SectionSynthesisError("Embedder service unavailable: {error_message}")`
- **State**: Section synthesis stops, no block generated
- **Rigor Level**: Same as Scenario 1

**Logging**: ERROR level with full error context

---

### 3.3 Qdrant Failures

#### Scenario 5: Qdrant Service Down

**Condition**: Qdrant service unavailable (HTTP 503, timeout, or connection error)

**Behavior**:
- **Action**: Fail section run immediately (Qdrant is always mandatory)
- **Error**: `SectionSynthesisError("Qdrant service unavailable: {error_message}")`
- **State**: Section synthesis stops, no block generated
- **Rigor Level**: Same as Scenario 1

**Logging**: ERROR level with full error context

---

### 3.4 Vision-Related Failures

#### Scenario 6: Vision Service Off, Scanned PDF Detected

**Condition**: `VISION_ENABLED = false` AND PDF triage indicates `likely_scanned = true`

**Behavior**:
- **Action**: Log WARNING, continue synthesis (non-fatal)
- **Warning**: `"Vision service is disabled but PDF appears scanned. Text extraction may be weak. Consider reprocessing with vision enabled."`
- **State**: Section synthesis continues, but retrieval quality may be degraded
- **Recommendation**: Suggest user reprocess PDF with `VISION_ENABLED = true`

**Logging**: WARNING level with triage metadata (pages_previewed, preview_text_chars)

**Note**: This is a quality warning, not a failure. Synthesis proceeds with available text.

---

### 3.5 LLM Failures

#### Scenario 7: Synthesizer LLM Unavailable

**Condition**: Brain/Worker service unavailable (HTTP 503, timeout, or connection error)

**Behavior**:
- **Action**: Fail section run immediately (LLM is mandatory)
- **Error**: `SectionSynthesisError("Synthesis LLM unavailable: {error_message}")`
- **State**: Section synthesis stops, no block generated
- **Rigor Level**: Same as Scenario 1

**Logging**: ERROR level with full error context

---

#### Scenario 8: Critic LLM Unavailable

**Condition**: Brain/Worker service unavailable during Critic call

**Behavior**:
- **Action**: Log WARNING, continue synthesis (Critic is optional for block generation)
- **Warning**: `"Critic LLM unavailable, skipping cross-examination. Promotions will not be applied."`
- **State**: Section synthesis continues, block generated without Critic validation
- **Promotions**: Empty list (no promotions applied)
- **Flags**: Empty list (no flags generated)

**Logging**: WARNING level with error context

**Note**: Block is still generated and persisted. Promotions can be applied later via manual review or reprocess.

---

### 3.6 Persistence Failures

#### Scenario 9: RetrievalBundle Persistence Failure

**Condition**: ArangoDB unavailable or insert fails for `retrieval_bundles` collection

**Behavior**:
- **Action**: Log WARNING, continue synthesis (non-fatal)
- **Warning**: `"Failed to persist RetrievalBundle {bundle_id}: {error_message}"`
- **State**: Section synthesis continues, block generated, but bundle not persisted
- **Audit**: Bundle data remains in `state["retrieval_bundles"]` for manual recovery

**Logging**: WARNING level with bundle_id and error context

---

#### Scenario 10: SectionDraft Block Persistence Failure

**Condition**: ArangoDB unavailable or insert fails for `manuscript_blocks` collection

**Behavior**:
- **Action**: Fail section run (block persistence is mandatory)
- **Error**: `SectionSynthesisError("Block persistence failed: {error_message}")`
- **State**: Section synthesis stops, block not persisted (but exists in state)
- **Rigor Level**: Same as Scenario 1

**Logging**: ERROR level with block_id and error context

**Recovery**: Block data remains in `state["manuscript_blocks"]` for manual recovery or retry

---

#### Scenario 11: Analytical Note Promotion Failure

**Condition**: ArangoDB unavailable or update fails for `analytical_notes` collection

**Behavior**:
- **Action**: Log WARNING, continue synthesis (non-fatal)
- **Warning**: `"Failed to promote AnalyticalNote {note_id}: {error_message}"`
- **State**: Section synthesis continues, promotions not applied (but recorded in state)
- **Audit**: Promotions remain in `state["analytical_note_promotions"]` for manual application

**Logging**: WARNING level with note_id and error context

---

### 3.7 Blueprint Validation Failures

#### Scenario 12: Blueprint Not Found

**Condition**: No blueprint exists for `project_id` in ArangoDB

**Behavior**:
- **Action**: Fail blueprint synthesis node immediately
- **Error**: `BlueprintNotFoundError("No blueprint found for project {project_id}")`
- **State**: Blueprint synthesis node returns error state, no sections processed

**Logging**: ERROR level with project_id

**Recovery**: User must create blueprint via UI or API before synthesis can proceed

---

#### Scenario 13: Blueprint Has Empty Sections

**Condition**: Blueprint exists but `sections` list is empty

**Behavior**:
- **Action**: Log INFO, return state with empty `manuscript_blocks`
- **Warning**: `"Blueprint {blueprint_id} has no sections. No synthesis performed."`
- **State**: Blueprint synthesis node completes successfully with empty results

**Logging**: INFO level with blueprint_id

**Note**: This is not an error. Empty blueprints are valid (user may add sections later).

---

### 3.8 Error Recovery and Retry Strategy

**Retry Policy**: No automatic retries for section synthesis. Failures are logged and state is preserved for manual recovery or retry.

**Manual Recovery**:
- RetrievalBundle data: Available in `state["retrieval_bundles"]`
- SectionDraft data: Available in `state["manuscript_blocks"]`
- Promotion data: Available in `state["analytical_note_promotions"]`

**Retry Mechanism**: User can retry failed sections by:
1. Fixing underlying issue (service availability, blueprint validation)
2. Re-running blueprint synthesis node with same state
3. Sections that succeeded will be skipped (idempotent) or regenerated (if force flag set)

---

## 4. State Diagrams

### 4.1 Analytical Note State Machine

```
┌─────────────────────────────────────────────────────────────┐
│                    Analytical Note States                     │
└─────────────────────────────────────────────────────────────┘

                    ┌──────────┐
                    │  DRAFT   │ (Initial State)
                    └────┬─────┘
                         │
                         │ User creates note
                         │ (via UI or API)
                         │
                         ▼
        ┌────────────────────────────────────┐
        │  DRAFT State                       │
        │  - state: "Draft"                  │
        │  - critic_flags: []                │
        │  - promotion_reason: None          │
        └────────────────────────────────────┘
                         │
                         │ Used in section synthesis
                         │ (included in Packet B)
                         │
                         ▼
        ┌────────────────────────────────────┐
        │  Critic Cross-Examination          │
        │  (Step 7 of section loop)          │
        └────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          │ Supported    │ Overreach    │ No decision
          │ by Packet A  │ beyond       │ (Critic unavailable)
          │              │ Packet A     │
          ▼              ▼              ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ MANUSCRIPT│   │  DRAFT   │   │  DRAFT   │
    │ (Promoted)│   │ (Flagged)│   │ (Unchanged)│
    └──────────┘   └──────────┘   └──────────┘
         │              │              │
         │              │              │
         └──────────────┴──────────────┘
                         │
                         │ Final State
                         ▼
        ┌────────────────────────────────────┐
        │  MANUSCRIPT State                  │
        │  - state: "Manuscript"             │
        │  - promotion_reason: str           │
        │  - critic_flags: List[str]         │
        │  - linked_evidence: List[str]      │
        └────────────────────────────────────┘

State Transitions:
1. DRAFT → MANUSCRIPT:
   - Trigger: Critic proposes promotion (Step 7)
   - Condition: Note's framing supported by Packet A evidence
   - Action: Update state, set promotion_reason, link evidence
   
2. DRAFT → DRAFT (Flagged):
   - Trigger: Critic flags overreach (Step 7)
   - Condition: Note's framing goes beyond Packet A
   - Action: Append flag to critic_flags, keep state=DRAFT
   
3. DRAFT → DRAFT (Unchanged):
   - Trigger: Critic unavailable or no decision
   - Condition: No promotion or flag generated
   - Action: Keep state=DRAFT, no changes

Invariants:
- state = MANUSCRIPT → promotion_reason must be non-empty
- state = MANUSCRIPT → linked_evidence (from promotion) must be non-empty
- state = DRAFT → promotion_reason = None
- critic_flags may be non-empty in either state (flagged but promoted, or flagged and not promoted)
```

---

### 4.2 Section Synthesis State Machine

```
┌─────────────────────────────────────────────────────────────┐
│              Section Synthesis State Machine                 │
└─────────────────────────────────────────────────────────────┘

                    ┌──────────┐
                    │  QUEUED  │ (Section in blueprint)
                    └────┬─────┘
                         │
                         │ blueprint_synthesis_node starts
                         │
                         ▼
        ┌────────────────────────────────────┐
        │  Step 1: Build Section Query       │
        │  - Construct query_text            │
        └────────────┬───────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │  Step 2: Retrieve Candidates       │
        │  - Embed query                     │
        │  - Qdrant search (top-K)           │
        └────────────┬───────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
          │ Success             │ Failure (Embedder/Qdrant down)
          │                     │
          ▼                     ▼
    ┌──────────┐         ┌──────────┐
    │  RERANK  │         │  FAILED  │ (Section run fails)
    └────┬─────┘         └──────────┘
         │
         │ Step 3: Rerank
         │
    ┌────┴────┐
    │         │
    │ Success │ Failure
    │         │
    ▼         ▼
┌────────┐ ┌─────────────────────┐
│ RERANKED│ │ RERANK_SKIPPED      │ (if optional)
│         │ │ (fallback to embed) │
└────┬────┘ └──────────┬──────────┘
     │                 │
     └────────┬────────┘
              │
              ▼
        ┌────────────────────────────────────┐
        │  Step 4: Build Packet A            │
        │  - Format top-M chunks             │
        └────────────┬───────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │  Step 5: Build Packet B            │
        │  - Query Analytical Notes          │
        └────────────┬───────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │  Step 6: Synthesizer Call          │
        │  - Nemotron 49B synthesis          │
        └────────────┬───────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
          │ Success             │ Failure (LLM down)
          │                     │
          ▼                     ▼
    ┌──────────┐         ┌──────────┐
    │  DRAFTED │         │  FAILED  │ (Section run fails)
    └────┬─────┘         └──────────┘
         │
         │ Step 7: Critic Call
         │
    ┌────┴────┐
    │         │
    │ Success │ Failure (LLM down, non-fatal)
    │         │
    ▼         ▼
┌────────┐ ┌──────────┐
│CRITIQUED│ │  DRAFTED │ (no promotions)
│         │ │          │
└────┬────┘ └──────────┘
     │
     │ Step 8: Persist
     │
     ▼
┌─────────────────────────────┐
│  Step 8a: Persist Bundle    │
│  (may fail, non-fatal)      │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  Step 8b: Persist Block     │
│  (mandatory, may fail)      │
└────────────┬────────────────┘
             │
     ┌───────┴───────┐
     │               │
     │ Success       │ Failure
     │               │
     ▼               ▼
┌────────┐      ┌──────────┐
│COMPLETED│     │  FAILED  │ (Section run fails)
└─────────┘     └──────────┘
     │
     │ Step 8c: Apply Promotions
     │ (best-effort, non-fatal)
     │
     ▼
┌─────────────────────────────┐
│  FINAL STATE: COMPLETED     │
│  - Block persisted          │
│  - Bundle persisted (if successful)│
│  - Promotions applied (if successful)│
└─────────────────────────────┘

State Definitions:
- QUEUED: Section in blueprint, not yet processed
- RERANK: Reranking in progress (Step 3)
- RERANKED: Reranking successful
- RERANK_SKIPPED: Reranking skipped (fallback to embed-only)
- DRAFTED: Section text synthesized (Step 6)
- CRITIQUED: Critic validation complete (Step 7)
- COMPLETED: Section fully processed and persisted (Step 8)
- FAILED: Section run failed (unrecoverable error)

Error Handling:
- FAILED state: Section run stops, no block generated
- Non-fatal errors: Continue to next step (warnings logged)
- Rigor level affects failure propagation:
  - conservative: Fail entire loop on any section failure
  - exploratory: Skip failed sections, continue with remaining
```

---

## 5. Sequence Diagrams

### 5.1 Section Synthesis Loop Sequence

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Section Synthesis Loop Sequence                       │
└─────────────────────────────────────────────────────────────────────────┘

Actor: blueprint_synthesis_node
Participants: Embedder, Qdrant, Reranker, Brain (Synthesizer), Brain (Critic), ArangoDB

blueprint_synthesis_node
    │
    │ 1. Load Blueprint
    ├───────────────────────────────────────────────────────────► ArangoDB
    │                                                              Query blueprint
    │                                                              ◄─────────────────
    │
    │ 2. For each section in blueprint.sections:
    │
    │   2.1 Build Section Query
    │   ┌──────────────────────────────────────────────────────┐
    │   │ section_query = f(heading, journal_slot, linked_rqs, │
    │   │                    depth_intent)                     │
    │   └──────────────────────────────────────────────────────┘
    │
    │   2.2 Retrieve Candidates
    │   ├──────────────────────────────────────────────────────► Embedder
    │   │ POST /embed                                          │
    │   │ {texts: [section_query]}                            │
    │   │                                                      │
    │   │                                                      │ ◄───────────────────
    │   │                                                      │ {embeddings: [[...]]}
    │   │                                                      │
    │   ├──────────────────────────────────────────────────────► Qdrant
    │   │ search(collection="document_chunks",                │
    │   │        query_vector=query_vector,                   │
    │   │        limit=top_k_embed)                           │
    │   │                                                      │
    │   │                                                      │ ◄───────────────────
    │   │                                                      │ candidate_chunks (top-K)
    │   │
    │   2.3 Rerank
    │   ├──────────────────────────────────────────────────────► Reranker
    │   │ POST /rerank                                        │
    │   │ {query: section_query,                              │
    │   │  documents: candidate_chunks,                       │
    │   │  top_k: top_k_rerank}                               │
    │   │                                                      │
    │   │                                                      │ ◄───────────────────
    │   │                                                      │ {results: [{...}]}
    │   │                                                      │ (reranked top-M)
    │   │
    │   2.4 Build Packet A
    │   ┌──────────────────────────────────────────────────────┐
    │   │ packet_a = format_chunks_with_citations(            │
    │   │             reranked_chunks)                        │
    │   └──────────────────────────────────────────────────────┘
    │
    │   2.5 Build Packet B
    │   ├──────────────────────────────────────────────────────► ArangoDB
    │   │ Query analytical_notes                              │
    │   │ FILTER project_id, state, linked_rq, tags           │
    │   │                                                      │
    │   │                                                      │ ◄───────────────────
    │   │                                                      │ packet_b (Analytical Notes)
    │   │
    │   2.6 Synthesizer Call
    │   ├──────────────────────────────────────────────────────► Brain (Synthesizer)
    │   │ POST /v1/chat/completions                           │
    │   │ {messages: [                                        │
    │   │   {role: "system", content: system_prompt},         │
    │   │   {role: "user", content: packet_a + packet_b +     │
    │   │                      sandwich_pattern_instruction}   │
    │   │ ]}                                                  │
    │   │                                                      │
    │   │                                                      │ ◄───────────────────
    │   │                                                      │ {content: section_text}
    │   │
    │   2.7 Critic Call
    │   ├──────────────────────────────────────────────────────► Brain (Critic)
    │   │ POST /v1/chat/completions                           │
    │   │ {messages: [                                        │
    │   │   {role: "system", content: critic_prompt},         │
    │   │   {role: "user", content: section_text +            │
    │   │                      packet_a + packet_b +           │
    │   │                      validation_rules}               │
    │   │ ]}                                                  │
    │   │                                                      │
    │   │                                                      │ ◄───────────────────
    │   │                                                      │ {flags: [...],       │
    │   │                                                      │  promotions: [...]}  │
    │   │
    │   2.8 Persist
    │   ├──────────────────────────────────────────────────────► ArangoDB
    │   │ Insert RetrievalBundle                              │
    │   │ (non-fatal if fails)                                │
    │   │                                                      │
    │   ├──────────────────────────────────────────────────────► ArangoDB
    │   │ Insert ManuscriptBlock                              │
    │   │ (fatal if fails)                                    │
    │   │                                                      │
    │   ├──────────────────────────────────────────────────────► ArangoDB
    │   │ Update AnalyticalNote (promotions)                  │
    │   │ (non-fatal if fails)                                │
    │   │                                                      │
    │   2.9 Append to accumulators
    │   ┌──────────────────────────────────────────────────────┐
    │   │ manuscript_blocks.append(section_draft)             │
    │   │ retrieval_bundles.append(retrieval_bundle)          │
    │   │ analytical_note_promotions.extend(promotions)       │
    │   └──────────────────────────────────────────────────────┘
    │
    │ 3. Update State
    │ ┌──────────────────────────────────────────────────────┐
    │ │ state["manuscript_blocks"] = manuscript_blocks       │
    │ │ state["retrieval_bundles"] = retrieval_bundles       │
    │ │ state["analytical_note_promotions"] = promotions     │
    │ └──────────────────────────────────────────────────────┘
    │
    │ 4. Return State
    │
```

**Notes**:
- Steps 2.1-2.8 execute sequentially per section
- If any mandatory step fails, section run stops (error handling as per Section 3)
- Non-fatal errors (reranker optional, bundle persistence) allow continuation
- All DB operations are transactional per section (no partial commits)

---

### 5.2 Analytical Note Promotion Sequence

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  Analytical Note Promotion Sequence                      │
└─────────────────────────────────────────────────────────────────────────┘

Participants: Critic (Brain), ArangoDB, AnalyticalNote

Critic (Step 7)
    │
    │ 1. Cross-Examine Section Draft
    │ ┌──────────────────────────────────────────────────────┐
    │ │ Check citations in section_text vs Packet A          │
    │ │ Check analogies/framing vs Packet A support          │
    │ │ For each note in Packet B:                           │
    │ │   - If framing used AND supported by Packet A:       │
    │ │     → Propose promotion                              │
    │ │   - If framing goes beyond Packet A:                 │
    │ │     → Flag as overreach                              │
    │ └──────────────────────────────────────────────────────┘
    │
    │ 2. Generate Promotions
    │ ┌──────────────────────────────────────────────────────┐
    │ │ promotions = [                                       │
    │ │   {                                                  │
    │ │     "note_id": "uuid-1",                             │
    │ │     "reason": "Framing supported by evidence...",    │
    │ │     "linked_evidence": ["chunk_id1", "chunk_id2"]   │
    │ │   },                                                 │
    │ │   ...                                                │
    │ │ ]                                                    │
    │ └──────────────────────────────────────────────────────┘
    │
    │ 3. Return Promotions
    │
blueprint_synthesis_node (Step 8)
    │
    │ 4. For each promotion in promotions:
    │
    │   4.1 Query Note
    │   ├──────────────────────────────────────────────────────► ArangoDB
    │   │ Query analytical_notes                              │
    │   │ FILTER _key == promotion.note_id                    │
    │   │                                                      │
    │   │                                                      │ ◄───────────────────
    │   │                                                      │ note (if found)
    │   │
    │   4.2 Update Note State
    │   ├──────────────────────────────────────────────────────► ArangoDB
    │   │ Update analytical_notes                             │
    │   │ SET state = "Manuscript",                           │
    │   │     promotion_reason = promotion.reason,            │
    │   │     critic_flags = flags,                           │
    │   │     updated_at = now()                              │
    │   │ WHERE _key == promotion.note_id                     │
    │   │                                                      │
    │   │                                                      │ ◄───────────────────
    │   │                                                      │ (success or error)
    │   │
    │   4.3 Handle Errors (non-fatal)
    │   ┌──────────────────────────────────────────────────────┐
    │   │ If note not found or update fails:                  │
    │   │   - Log WARNING                                     │
    │   │   - Continue to next promotion                      │
    │   └──────────────────────────────────────────────────────┘
    │
    │ 5. Promotion Complete
    │ ┌──────────────────────────────────────────────────────┐
    │ │ Note state: DRAFT → MANUSCRIPT                       │
    │ │ Note.promotion_reason: set                           │
    │ │ Note.critic_flags: updated (if any)                  │
    │ └──────────────────────────────────────────────────────┘
```

**Notes**:
- Promotions are applied best-effort (non-fatal failures)
- Failed promotions are logged but don't block section synthesis
- Promotions can be manually applied later via API if automatic promotion fails

---

## 6. Configuration Defaults

### 6.1 Retrieval Configuration

**Location**: `src/shared/config.py` (to be extended)

**Environment Variables**:
```python
# Embed recall (top-K)
RETRIEVAL_TOP_K_EMBED = int(os.getenv("RETRIEVAL_TOP_K_EMBED", "64"))  # Default: 64

# Rerank output (top-M)
RETRIEVAL_TOP_K_RERANK = int(os.getenv("RETRIEVAL_TOP_K_RERANK", "16"))  # Default: 16

# Reranker service configuration
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() == "true"  # Default: true
RERANKER_MANDATORY = os.getenv("RERANKER_MANDATORY", "false").lower() == "true"  # Default: false

# Analytical Notes limit
ANALYTICAL_NOTES_LIMIT = int(os.getenv("ANALYTICAL_NOTES_LIMIT", "10"))  # Default: 10
```

**Defaults Summary**:
- `RETRIEVAL_TOP_K_EMBED = 64`: Retrieve top-64 chunks from Qdrant (before reranking)
- `RETRIEVAL_TOP_K_RERANK = 16`: Return top-16 chunks after reranking (Evidence Packet A)
- `RERANKER_ENABLED = true`: Reranker is enabled by default
- `RERANKER_MANDATORY = false`: Reranker is optional by default (fallback to embed-only if fails)
- `ANALYTICAL_NOTES_LIMIT = 10`: Maximum Analytical Notes to include in Packet B

**Rationale**:
- Top-K=64 provides good recall while limiting reranker input size (cost/performance trade-off)
- Top-M=16 fits within 64k context window for Nemotron 49B (allows room for prompts, Packet B, system context)
- Reranker optional by default provides graceful degradation if service unavailable
- Analytical Notes limit prevents prompt bloat while preserving relevant perspectives

---

### 6.2 Timeout Configuration

**Location**: `src/shared/config.py`

**Environment Variables**:
```python
# Embedder timeout
EMBEDDER_TIMEOUT_SECONDS = int(os.getenv("EMBEDDER_TIMEOUT_SECONDS", "10"))  # Default: 10

# Qdrant timeout
QDRANT_TIMEOUT_SECONDS = int(os.getenv("QDRANT_TIMEOUT_SECONDS", "15"))  # Default: 15

# Reranker timeout
RERANKER_TIMEOUT_SECONDS = int(os.getenv("RERANKER_TIMEOUT_SECONDS", "30"))  # Default: 30

# LLM timeout (Synthesizer and Critic)
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))  # Default: 60
```

**Defaults Summary**:
- Embedder: 10 seconds (lightweight embedding generation)
- Qdrant: 15 seconds (vector search)
- Reranker: 30 seconds (reranking top-64 chunks)
- LLM: 60 seconds (synthesis and critique)

---

### 6.3 Rigor Level Configuration

**Location**: `ProjectConfig.rigor_level` (from project config)

**Values**:
- `"exploratory"`: Non-fatal failures allow continuation, warnings logged
- `"conservative"`: Fatal failures stop entire loop, errors logged

**Behavior**:
- **Exploratory**: Skip failed sections, continue with remaining sections
- **Conservative**: Stop entire blueprint synthesis loop on any section failure

---

### 6.4 Model Configuration

**Location**: `src/shared/config.py`

**Defaults**:
```python
# Embedder model
EMBEDDER_MODEL_ID = "nvidia/nv-embedqa-e5-v5"  # 1024 dimensions

# Reranker model
RERANKER_MODEL_ID = "nvidia/llama-3.2-nv-rerankqa-1b-v2"

# Synthesis/Critique model
TEXT_MODEL_ID = "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5"  # 64k context
```

---

### 6.5 Feature Flags

**Location**: Environment variables (with defaults in `src/shared/config.py`)

**Flags**:
```python
# Reranker
RERANKER_ENABLED = True          # Enable reranker service
RERANKER_MANDATORY = False       # Require reranker (fail if unavailable)

# Vision
VISION_ENABLED = False           # Enable vision service (default: false)
VISION_TRIAGE_PAGES = 2          # Pages to preview for triage
VISION_MIN_TEXT_CHARS = 800      # Minimum text chars to consider PDF text-based

# Blueprint synthesis
BLUEPRINT_SYNTHESIS_ENABLED = True  # Enable blueprint-driven synthesis
```

---

## 7. Data Flow Contracts

### 7.1 Section Query Construction Contract

**Input**: `BlueprintSection`, `ProjectConfig`

**Output**: `query_text: str`

**Contract**:
- `query_text` must be non-empty
- `query_text` must include section heading
- `query_text` must include journal slot
- `query_text` must include linked RQ texts (if `linked_rqs` non-empty)
- `query_text` must include depth intent description

**Validation**: Query construction must never fail (no external dependencies)

---

### 7.2 Retrieval Contract

**Input**: `query_text: str`, `project_id: str`, `ingestion_id: Optional[str]`, `top_k: int`

**Output**: `candidate_chunks: List[Dict]`

**Contract**:
- `len(candidate_chunks) <= top_k`
- Each chunk must have: `chunk_id`, `text_content`, `payload`, `score`
- Chunks must be sorted by `score` (descending)
- All chunks must have `project_id` matching input (security invariant)
- If `ingestion_id` provided, all chunks must have matching `ingestion_id`

**Error Handling**:
- Embedder failure: Raise `RetrievalError` (mandatory service)
- Qdrant failure: Raise `RetrievalError` (mandatory service)
- Empty results: Return empty list (not an error, may indicate no matching chunks)

---

### 7.3 Reranking Contract

**Input**: `query_text: str`, `candidate_chunks: List[Dict]`, `top_m: int`, `reranker_mandatory: bool`

**Output**: `(reranked_chunks: List[Dict], rerank_skipped: bool, rerank_error: Optional[str])`

**Contract**:
- `len(reranked_chunks) <= top_m`
- If `rerank_skipped = False`: Chunks sorted by `rerank_score` (descending), `rerank_error = None`
- If `rerank_skipped = True`: Chunks sorted by `score` (descending), `rerank_error` may be present
- Each reranked chunk must have: `rerank_score`, `rerank_rank` (if not skipped)
- `rerank_skipped = True` AND `reranker_mandatory = True`: Must raise `SectionSynthesisError`

**Error Handling**:
- Reranker mandatory and unavailable: Raise `SectionSynthesisError`
- Reranker optional and unavailable: Return fallback (embed-only) with `rerank_skipped = True`
- Invalid reranker response: Same as optional failure (fallback to embed-only)

---

### 7.4 Packet Construction Contracts

#### Packet A (Primary Sources)

**Input**: `reranked_chunks: List[Dict]`

**Output**: `packet_a: List[Dict]`

**Contract**:
- Each item must have: `text` (truncated to 500 chars), `citation` (with `chunk_id`, `page`, `source`), `full_chunk`
- Items must be sorted by `rerank_rank` (if available) or `score` (descending)
- `len(packet_a) = len(reranked_chunks)` (no filtering, only formatting)

**Invariant**: All citations in Packet A must be traceable to `reranked_chunks`

#### Packet B (Analytical Notes)

**Input**: `project_id: str`, `section: BlueprintSection`, `state_filter: str`

**Output**: `packet_b: List[Dict]`

**Contract**:
- Each item must have: `note_id`, `text`, `tags`, `linked_rq`, `state`, `source_ref`
- Items must be filtered by: `project_id`, `state` (default: "Draft"), `linked_rq` (if section has linked RQs), `tags` (if section has tags)
- `len(packet_b) <= ANALYTICAL_NOTES_LIMIT` (default: 10)
- Items must be sorted by `created_at` (descending, most recent first)

**Invariant**: Packet B items are **NOT citeable**. They influence style only.

---

### 7.5 Synthesis Contract

**Input**: `section: BlueprintSection`, `packet_a: List[Dict]`, `packet_b: List[Dict]`, `project_config: ProjectConfig`

**Output**: `section_text: str`

**Contract**:
- `section_text` must be non-empty
- `section_text` must be Markdown-formatted
- `section_text` must include at least one citation marker `[[chunk_id]]` referencing Packet A
- `section_text` must follow sandwich pattern (Hook → Proof → So-what) based on `depth_intent`
- `section_text` must NOT directly cite Packet B (analogies/framing only, no citations)

**Validation**:
- In conservative mode: Reject if no citations found (fatal)
- In exploratory mode: Warn if no citations found (non-fatal)

**Error Handling**:
- LLM unavailable: Raise `SectionSynthesisError` (mandatory service)
- LLM response invalid: Log warning, retry once, then raise `SectionSynthesisError`

---

### 7.6 Critique Contract

**Input**: `section_text: str`, `packet_a: List[Dict]`, `packet_b: List[Dict]`, `rigor_level: str`

**Output**: `(flags: List[str], promotions: List[Dict])`

**Contract**:
- `flags` must be list of strings (each flag is a violation description)
- `promotions` must be list of dicts with: `note_id`, `reason`, `linked_evidence`
- Each promotion's `linked_evidence` must reference chunk IDs from Packet A
- Promotions must only reference notes from Packet B

**Validation**:
- Citations in `section_text` must be validated against Packet A (flag if not found)
- Analogies/framing in `section_text` must be validated against Packet A support (flag if overreach)
- Promotions must only be proposed if note's framing is supported by Packet A evidence

**Error Handling**:
- LLM unavailable: Return empty lists (non-fatal, synthesis continues)
- Invalid JSON response: Log warning, return empty lists (non-fatal)

---

### 7.7 Persistence Contracts

#### RetrievalBundle Persistence

**Input**: `retrieval_bundle: RetrievalBundle`

**Output**: `success: bool`, `error: Optional[str]`

**Contract**:
- Persistence is **non-fatal** (section synthesis continues if fails)
- Bundle data remains in `state["retrieval_bundles"]` for manual recovery
- Bundle ID must be unique (UUID collision extremely unlikely)

#### SectionDraft Block Persistence

**Input**: `section_draft: ManuscriptBlock`, `project_id: str`

**Output**: `success: bool`, `error: Optional[str]`

**Contract**:
- Persistence is **mandatory** (section synthesis fails if persistence fails)
- Block must have: `block_id`, `section_title`, `content`, `claim_ids`, `citation_keys`, `version`
- Block version must increment on updates (versioning)
- Citations must be validated (Librarian Key-Guard)

#### Analytical Note Promotion

**Input**: `promotions: List[Dict]`

**Output**: `success_count: int`, `failed_count: int`

**Contract**:
- Promotions are **best-effort** (non-fatal, section synthesis continues)
- Each promotion updates: `state = "Manuscript"`, `promotion_reason`, `critic_flags`, `updated_at`
- Failed promotions remain in `state["analytical_note_promotions"]` for manual application

---

## 8. Summary

This specification defines the exact orchestration behavior for:

1. **New Pipeline Objects**: AnalyticalNote (Draft → Manuscript promotion), ManuscriptBlueprint (section-driven synthesis), RetrievalBundle (reproducible evidence selection)

2. **Section Synthesis Loop**: 8-step process per blueprint section (query → retrieve → rerank → packet A/B → synthesize → critique → persist)

3. **Failure Modes**: 13 failure scenarios with exact error handling behavior (mandatory vs optional services, rigor level propagation, graceful degradation)

4. **State Machines**: Analytical Note promotion flow, Section synthesis state transitions

5. **Sequence Diagrams**: Section synthesis loop sequence, Analytical Note promotion sequence

6. **Configuration Defaults**: Retrieval limits (K=64, M=16), timeouts, feature flags, model IDs

7. **Data Flow Contracts**: Input/output contracts for each step with validation rules and error handling

**Key Invariants**:
- Packet A (Primary Sources) is **always citeable**, Packet B (Analytical Notes) is **never citeable**
- Reranker is **optional by default** (graceful degradation to embed-only)
- Section synthesis is **sequential per section** (order preserved)
- Promotions are **best-effort** (non-fatal failures allow continuation)
- RetrievalBundle persistence is **non-fatal** (audit trail preserved in state)

**Implementation Notes**:
- All schemas are defined in `src/orchestrator/schemas/`
- All node functions are in `src/orchestrator/nodes/`
- Configuration defaults are in `src/shared/config.py`
- Error handling follows rigor level (conservative vs exploratory)

---

**End of Specification**
