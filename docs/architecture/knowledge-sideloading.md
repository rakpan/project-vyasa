# Knowledge Sideloading: Out-of-Band (OOB) Research Ingestion

This document defines the contract and guardrails for ingesting external research content into Project Vyasa without polluting the canonical knowledge graph.

## Overview

Out-of-Band (OOB) research ingestion allows users to inject content from external sources (e.g., Perplexity, web scraping, manual paste) into Vyasa's knowledge pipeline. **Critical invariant**: OOB content is **NOT** canonical by default and must go through explicit review and promotion before entering the canonical knowledge graph.

## Storage Architecture

### Collections

OOB content is stored in three distinct collections:

1. **`external_references`** (ArangoDB)
   - Stores raw content + provenance metadata
   - Schema: `ExternalReference` (see `src/shared/schema.py`)
   - Fields: `reference_id`, `project_id`, `content_raw`, `source_name`, `source_url`, `extracted_at`, `tags`, `status`

2. **`candidate_knowledge`** (ArangoDB)
   - Stores extracted facts from external references
   - Schema: `CandidateFact` (see `src/shared/schema.py`)
   - Fields: `fact_id`, `reference_id`, `project_id`, `subject`, `predicate`, `object`, `confidence`, `priority_boost`, `source_type`, `promotion_state`, `created_at`
   - **Default `promotion_state`: `"candidate"`** (NOT canonical)

3. **`canonical_knowledge`** (ArangoDB)
   - Stores vetted, merged knowledge from finalized projects
   - Schema: `CanonicalKnowledge` (see `src/shared/schema.py`)
   - **OOB content does NOT enter here without explicit promotion**

## Lifecycle

### Stage 1: Ingestion
- External content is ingested as `ExternalReference` with `status="INGESTED"`
- Raw content stored in `content_raw` field
- Provenance tracked: `source_name`, `source_url` (if available), `extracted_at`

### Stage 2: Extraction
- `status` transitions to `"EXTRACTING"` → `"EXTRACTED"`
- Cartographer/Worker extracts structured facts (triples) from raw content
- Extracted facts stored in `candidate_knowledge` collection
- Each `CandidateFact` has:
  - `promotion_state="candidate"` (default)
  - `reference_id` linking back to source `ExternalReference`
  - `confidence` score from extraction model

### Stage 3: Review
- `status` transitions to `"NEEDS_REVIEW"` if confidence < threshold or source_url missing
- Human reviewer can:
  - **Promote**: Move candidate facts to canonical (via UI or API)
  - **Reject**: Mark `status="REJECTED"`, remove from candidate pool

### Stage 4: Promotion
- **Manual Promotion**: User selects candidate facts in UI → `promotion_state="canonical"` → merged into `canonical_knowledge`
- **Automatic Promotion** (if enabled):
  - Requires: `confidence >= OOB_PROMOTION_CONFIDENCE_THRESHOLD` (default: 0.85)
  - AND: `source_url` exists (if `OOB_REQUIRE_SOURCE_URL_FOR_AUTO_PROMOTION=true`, default: true)
  - On promotion: `promotion_state="canonical"` → merged into `canonical_knowledge`

## Promotion Rules

### Rule 1: Candidates are NOT Canonical by Default
- **Invariant**: `CandidateFact.promotion_state` defaults to `"candidate"`
- **Enforcement**: All queries that read canonical knowledge MUST filter by `promotion_state="canonical"` or query `canonical_knowledge` collection directly
- **Rationale**: Prevents accidental pollution of canonical graph with unverified OOB content

### Rule 2: Promotion Requirements

**Manual Promotion** (always allowed):
- User action in UI or API call
- No automatic checks required
- Human reviewer has final authority

**Automatic Promotion** (configurable):
- Requires `confidence >= OOB_PROMOTION_CONFIDENCE_THRESHOLD` (default: 0.85)
- If `OOB_REQUIRE_SOURCE_URL_FOR_AUTO_PROMOTION=true` (default: true):
  - Requires `source_url` to be present in parent `ExternalReference`
  - Prevents promotion of unverified sources (e.g., manual paste without URL)

### Rule 3: Deduplication

**Fact Hash Computation**:
- Compute stable `fact_hash = hash(normalize(subject|predicate|object))`
- Normalization: lowercase, trim whitespace, canonicalize predicate values
- Use consistent hash algorithm (e.g., SHA256 of normalized string)

**Deduplication Strategy**:
- If `fact_hash` already exists in `canonical_knowledge`:
  - **DO NOT** create duplicate canonical fact
  - **DO** add `reference_id` to existing fact's `source_pointers` or `provenance_log`
  - Store as additional evidence reference, not duplicate fact

- If `fact_hash` exists in `candidate_knowledge` (same or different reference):
  - **DO NOT** create duplicate candidate fact
  - **DO** merge confidence scores (e.g., max or weighted average)
  - **DO** link both `reference_id`s to the same candidate fact

## Guardrails

### Guardrail 1: Collection Isolation
- **Enforcement**: API endpoints MUST NOT query `candidate_knowledge` when user requests "canonical knowledge"
- **Implementation**: Always filter by `promotion_state="canonical"` or query `canonical_knowledge` collection

### Guardrail 2: Status Transitions
- **Valid transitions**:
  - `INGESTED` → `EXTRACTING` → `EXTRACTED` → `NEEDS_REVIEW` → `PROMOTED` or `REJECTED`
  - `EXTRACTED` → `PROMOTED` (if auto-promotion criteria met)
- **Invalid**: Cannot transition from `REJECTED` to `PROMOTED` without re-ingestion

### Guardrail 3: Source Verification
- If `OOB_REQUIRE_SOURCE_URL_FOR_AUTO_PROMOTION=true`:
  - Auto-promotion blocked if `ExternalReference.source_url` is `None` or empty
  - Manual promotion still allowed (human reviewer can verify)

### Guardrail 4: Project Scoping
- All `ExternalReference` and `CandidateFact` entries MUST have `project_id`
- Promotion to canonical knowledge inherits project context but becomes globally accessible
- Queries can filter by `project_id` to show project-scoped candidate facts

## Configuration

See `src/shared/config.py`:

- `OOB_PROMOTION_CONFIDENCE_THRESHOLD` (default: `0.85`): Minimum confidence for auto-promotion
- `OOB_REQUIRE_SOURCE_URL_FOR_AUTO_PROMOTION` (default: `true`): Require source URL for auto-promotion

## Example Flow

1. User pastes content from Perplexity → `ExternalReference` created with `status="INGESTED"`, `source_name="Perplexity"`, `source_url="https://..."`

2. Extraction job runs → `status="EXTRACTING"` → extracts facts → `status="EXTRACTED"`

3. Facts stored in `candidate_knowledge`:
   ```json
   {
     "fact_id": "fact-123",
     "reference_id": "ref-abc",
     "promotion_state": "candidate",
     "confidence": 0.92,
     "subject": "SQL Injection",
     "predicate": "ENABLES",
     "object": "Database Compromise"
   }
   ```

4. Auto-promotion check:
   - `confidence >= 0.85` ✓
   - `source_url` exists ✓
   - → Auto-promote to `canonical_knowledge`

5. Deduplication: If fact already exists in canonical, add `reference_id` to provenance instead of creating duplicate

## Implementation Notes

- **No APIs/UI in this contract**: This document defines the data model and rules only
- **Future work**: API endpoints for ingestion, review UI, promotion workflows
- **Indexing**: Ensure indexes on `candidate_knowledge.promotion_state`, `candidate_knowledge.reference_id`, `external_references.status`
- **Queries**: Always use collection-level filtering to prevent accidental mixing of candidate and canonical knowledge

