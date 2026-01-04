"""
Cartography node for knowledge extraction.

Extracts structured knowledge graphs from raw text using RQ-scoped retrieval
and evidence-aware RAG. Produces canonical Claim objects with source anchors.
"""

import json
import re
from typing import Dict, Any, List, Optional

from ...shared.config import (
    _env,
    get_brain_url,
    get_memory_url,
    get_arango_password,
    ARANGODB_DB,
    ARANGODB_USER,
)
from ...shared.model_registry import get_model_config
from ...shared.context_budget import estimate_tokens
from ...shared.logger import get_logger
from ...shared.utils import get_utc_now
from ...shared.role_manager import RoleRegistry
from ..context_packer import build_extraction_layers, stub_retrieve_evidence
from ..state import PhaseEnum, ResearchState
from ..normalize import normalize_extracted_json
from ..telemetry import TelemetryEmitter, trace_node
from ..config import ExpertType
from arango import ArangoClient

from .base import wrap_prompt_with_context

logger = get_logger("orchestrator", __name__)
telemetry_emitter = TelemetryEmitter()
role_registry = RoleRegistry()

# Lazy import to avoid circular dependencies
_synthesis_service: Optional[Any] = None


def _get_synthesis_service() -> Optional[Any]:
    """Get or initialize SynthesisService for canonical knowledge queries.
    
    Returns:
        SynthesisService instance or None if DB unavailable
    """
    global _synthesis_service
    if _synthesis_service is None:
        try:
            from ..synthesis_service import SynthesisService
            from ...shared.config import (
                get_memory_url,
                get_arango_password,
                ARANGODB_DB,
                ARANGODB_USER,
            )

            arango_url = get_memory_url()
            arango_db = ARANGODB_DB
            arango_user = ARANGODB_USER
            arango_password = get_arango_password()

            client = ArangoClient(hosts=arango_url)
            db = client.db(arango_db, username=arango_user, password=arango_password)
            _synthesis_service = SynthesisService(db)
            logger.debug("SynthesisService initialized in cartography module")
        except Exception as e:
            logger.warning(f"Failed to initialize SynthesisService in cartography: {e}")
            _synthesis_service = None
    return _synthesis_service


def _query_established_knowledge(
    raw_text: str,
    state: Optional[ResearchState] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, int], List[str]]:
    """Query knowledge base for entities mentioned in the text with prioritized retrieval.
    
    When force_refresh_context is True, prioritizes candidate facts from reference_ids,
    then canonical knowledge, then document chunks.
    
    Args:
        raw_text: Text to extract entity names from
        state: Optional[ResearchState] containing reference_ids and force_refresh_context
    
    Returns:
        Tuple of (knowledge_entries, context_sources_counts, selected_reference_ids)
        - knowledge_entries: List of knowledge entries (candidate or canonical)
        - context_sources_counts: Dict with counts from each tier
        - selected_reference_ids: List of reference IDs actually used
    """
    # Extract entity names (simple heuristic)
    words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', raw_text)
    entity_names = list(set(words))[:20]  # Limit to 20 unique names
    
    if not entity_names:
        return [], {}, []
    
    context_sources = {
        "candidate_facts": 0,
        "canonical_knowledge": 0,
        "document_chunks": 0,
    }
    selected_reference_ids = []
    
    force_refresh = state.get("force_refresh_context", False) if state else False
    reference_ids = state.get("reference_ids") if state else None
    project_id = state.get("project_id") if state else None
    
    all_knowledge = []
    
    # Tier 1: Candidate facts (when force_refresh_context is True)
    if force_refresh:
        candidate_facts = _query_candidate_knowledge(entity_names, reference_ids, project_id)
        if candidate_facts:
            all_knowledge.extend(candidate_facts)
            context_sources["candidate_facts"] = len(candidate_facts)
            # Extract reference_ids from candidate facts
            for fact in candidate_facts:
                ref_id = fact.get("reference_id")
                if ref_id and ref_id not in selected_reference_ids:
                    selected_reference_ids.append(ref_id)
    
    # Tier 2: Canonical knowledge
    service = _get_synthesis_service()
    if service:
        try:
            canonical = service.query_established_knowledge(entity_names)
            if canonical:
                # Filter out canonical entries that conflict with candidate facts
                if force_refresh and all_knowledge:
                    canonical = _filter_conflicting_canonical(canonical, all_knowledge, state)
                all_knowledge.extend(canonical)
                context_sources["canonical_knowledge"] = len(canonical)
        except Exception as e:
            logger.warning(f"Failed to query canonical knowledge: {e}", exc_info=True)
    
    # Tier 3: Document chunks (placeholder - would use vector search in production)
    # For now, document chunks are handled separately in the workflow
    
    # Limit total entries to avoid prompt bloat
    return all_knowledge[:20], context_sources, selected_reference_ids


def _query_candidate_knowledge(
    entity_names: List[str],
    reference_ids: Optional[List[str]],
    project_id: Optional[str],
) -> List[Dict[str, Any]]:
    """Query candidate_knowledge collection for facts from specific references.
    
    Args:
        entity_names: List of entity names to search for
        reference_ids: Optional list of reference IDs to filter by
        project_id: Optional project ID to filter by
    
    Returns:
        List of candidate fact documents
    """
    try:
        from arango import ArangoClient
        from ...shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, get_arango_password
        
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
        
        if not db.has_collection("candidate_knowledge"):
            return []
        
        coll = db.collection("candidate_knowledge")
        
        # Build query: match by subject/object containing entity names, filter by reference_id
        query_parts = []
        bind_vars = {}
        
        # If reference_ids provided, use them; otherwise get latest PROMOTED references for project
        if not reference_ids and project_id:
            # Query for latest PROMOTED references for the project
            ref_query = """
            FOR ref IN external_references
            FILTER ref.project_id == @project_id AND ref.status == "PROMOTED"
            SORT ref.extracted_at DESC
            LIMIT 10
            RETURN ref.reference_id
            """
            ref_cursor = db.aql.execute(ref_query, bind_vars={"project_id": project_id})
            reference_ids = [r for r in ref_cursor]
        
        if reference_ids:
            query_parts.append("FILTER fact.reference_id IN @reference_ids")
            bind_vars["reference_ids"] = reference_ids
        
        # Filter by entity names (subject or object matches)
        if entity_names:
            query_parts.append("FILTER fact.subject IN @entity_names OR fact.object IN @entity_names")
            bind_vars["entity_names"] = entity_names
        
        # Only get candidate facts (not already promoted)
        query_parts.append('FILTER fact.promotion_state == "candidate"')
        
        query = f"""
        FOR fact IN candidate_knowledge
        {" AND ".join(query_parts)}
        SORT fact.confidence DESC
        LIMIT 50
        RETURN fact
        """
        
        cursor = db.aql.execute(query, bind_vars=bind_vars)
        return list(cursor)
    except Exception as e:
        logger.warning(f"Failed to query candidate knowledge: {e}", exc_info=True)
        return []


def _filter_conflicting_canonical(
    canonical: List[Dict[str, Any]],
    candidate_facts: List[Dict[str, Any]],
    state: Optional[ResearchState],
) -> List[Dict[str, Any]]:
    """Filter canonical knowledge entries that conflict with candidate facts.
    
    A conflict is detected when:
    - Same subject/object but contradictory predicate/object
    
    Args:
        canonical: List of canonical knowledge entries
        candidate_facts: List of candidate facts
        state: ResearchState (for storing conflict flags)
    
    Returns:
        Filtered list of canonical entries (conflicts removed)
    """
    conflicts = []
    
    # Build a map of candidate facts by subject for quick lookup
    candidate_map = {}
    for fact in candidate_facts:
        subject = fact.get("subject", "").lower()
        if subject not in candidate_map:
            candidate_map[subject] = []
        candidate_map[subject].append(fact)
    
    filtered_canonical = []
    for entry in canonical:
        entity_name = entry.get("entity_name", "").lower()
        canonical_subject = entry.get("subject", "").lower()
        canonical_object = entry.get("object", "").lower()
        canonical_predicate = entry.get("predicate", "")
        
        has_conflict = False
        
        # Check for conflicts with candidate facts
        for check_key in [entity_name, canonical_subject]:
            if check_key in candidate_map:
                for candidate in candidate_map[check_key]:
                    cand_subject = candidate.get("subject", "").lower()
                    cand_object = candidate.get("object", "").lower()
                    cand_predicate = candidate.get("predicate", "")
                    
                    # Conflict detection: same subject but different/contradictory predicate/object
                    if (canonical_subject == cand_subject and 
                        (canonical_predicate != cand_predicate or canonical_object != cand_object)):
                        conflicts.append({
                            "canonical": entry.get("entity_id", ""),
                            "candidate": candidate.get("fact_id", ""),
                            "reason": f"Contradictory predicates: canonical='{canonical_predicate}' vs candidate='{cand_predicate}'"
                        })
                        has_conflict = True
                        break
        
        if not has_conflict:
            filtered_canonical.append(entry)
    
    # Store conflicts in state if available
    if state and conflicts:
        if "conflict_flags" not in state:
            state["conflict_flags"] = []
        state["conflict_flags"].extend(conflicts)
        logger.warning(
            f"Detected {len(conflicts)} conflicts between candidate and canonical knowledge",
            extra={"payload": {"conflicts": conflicts}}
        )
    
    return filtered_canonical


@trace_node
def cartographer_node(state: ResearchState) -> ResearchState:
    """Extract graph JSON from raw text using Cortex Worker, incorporating prior critiques.
    
    Uses Worker (SGLang) to extract structured knowledge graph with STRICT JSON
    requirements. The output is normalized to guarantee a `triples` array structure
    that the console expects.
    
    Args:
        state: ResearchState containing raw_text, optional critiques, and optional project context.
        
    Returns:
        Updated ResearchState with extracted_json containing guaranteed `triples` array.
        
    Raises:
        ValueError: If raw_text is missing or project_id provided but project not found.
        RuntimeError: If project_id provided but DB unavailable.
        requests.RequestException: If Worker API call fails.
    """
    # Import from nodes.py for now (will be moved to base.py/utils.py later)
    # Note: These are still in nodes.py but will be moved to base/utils in future refactor phases
    from .nodes import validate_state_schema, hydrate_project_context, route_to_expert, call_expert_with_fallback
    
    state = validate_state_schema(state)
    # Hydrate project context if project_id is present
    state = hydrate_project_context(state)
    
    # Safe access to project context (already hydrated if project_id exists)
    project_id = state.get("project_id")
    project_context = state.get("project_context")
    job_id = state.get("jobId") or state.get("job_id")
    
    raw_text = state.get("raw_text", "")
    critiques = state.get("critiques", []) or []
    
    # Fetch prompt from Prompt Registry (with fallback to factory default)
    from ..prompts import get_active_prompt_with_meta, DEFAULT_CARTOGRAPHER_PROMPT
    system_template, prompt_meta = get_active_prompt_with_meta("vyasa-cartographer", DEFAULT_CARTOGRAPHER_PROMPT)
    
    # Record prompt usage in state
    prompt_manifest = state.get("prompt_manifest", {})
    prompt_manifest["cartographer"] = prompt_meta.model_dump(mode="python")
    state["prompt_manifest"] = prompt_manifest
    
    force_refresh_context = state.get("force_refresh_context", False)
    ingestion_id = state.get("ingestion_id")
    rigor_level = state.get("rigor_level") or (project_context or {}).get("rigor_level", "exploratory")

    if not raw_text:
        raise ValueError("raw_text is required for cartographer node")

    # RQ-scoped retrieval: Retrieve chunks from Qdrant for each Research Question
    rq_scoped_chunks: Dict[str, List[Dict[str, Any]]] = {}
    all_chunks_with_anchors: List[Dict[str, Any]] = []
    
    if project_id and project_context:
        research_questions = project_context.get("research_questions", [])
        if research_questions and ingestion_id:
            try:
                from ..storage.qdrant import QdrantStorage
                qdrant_storage = QdrantStorage()
                
                # Retrieve top-k chunks per RQ (default: 5, configurable)
                chunks_per_rq = int(_env("CARTOGRAPHER_CHUNKS_PER_RQ", "5"))
                
                for rq_idx, rq_text in enumerate(research_questions):
                    rq_id = f"RQ{rq_idx + 1}"
                    chunks = qdrant_storage.retrieve_chunks_by_query(
                        query_text=rq_text,
                        project_id=project_id,
                        ingestion_id=ingestion_id,
                        limit=chunks_per_rq,
                    )
                    rq_scoped_chunks[rq_id] = chunks
                    all_chunks_with_anchors.extend(chunks)
                    
                    logger.debug(
                        f"Retrieved {len(chunks)} chunks for {rq_id}",
                        extra={"payload": {"rq_id": rq_id, "chunk_count": len(chunks)}}
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to retrieve chunks from Qdrant for RQ-scoped extraction: {e}",
                    exc_info=True
                )
                # Continue without Qdrant chunks (graceful degradation)
    
    # Use wrap_prompt_with_context for consistent context injection
    # Apply context injection AFTER fetching prompt from Opik
    # This ensures all LLM calls are governed by ProjectConfig (thesis, RQs, anti-scope, rigor)
    system_prompt = wrap_prompt_with_context(state, system_template)
    
    # Evidence-Aware RAG: Pre-extraction lookup with prioritized retrieval
    established_knowledge, context_sources, selected_ref_ids = _query_established_knowledge(raw_text, state)
    
    # Store context metadata in a fresh dict per revision to avoid accumulation
    merged_context_sources = {**state.get("context_sources", {}), **context_sources}
    selected_reference_ids = selected_ref_ids
    
    if established_knowledge:
        knowledge_section = "Established Knowledge:\n"
        for entry in established_knowledge[:10]:
            knowledge_section += f"- {entry.get('entity_name')} ({entry.get('entity_type')}): {entry.get('description', 'N/A')[:100]}\n"
        knowledge_section += "Use this to focus on novel or updated relationships."
        system_prompt = f"{system_prompt}\n\n{knowledge_section}"
        logger.debug(
            "Cartographer: Injected established knowledge into prompt",
            extra={
                "payload": {
                    "knowledge_count": len(established_knowledge),
                    "context_sources": context_sources,
                    "selected_reference_ids": selected_reference_ids,
                }
            }
        )
        
        # Emit telemetry with context sources
        if job_id:
            telemetry_emitter.emit_event(
                "context_assembly",
                {
                    "job_id": job_id,
                    "project_id": project_id,
                    "node_name": "cartographer_node",
                    "timestamp": get_utc_now().isoformat(),
                    "context_sources": context_sources,
                    "selected_reference_ids": selected_reference_ids,
                    "knowledge_count": len(established_knowledge),
                },
            )
    if force_refresh_context:
        system_prompt = f"{system_prompt}\nForce refresh context: prioritize latest evidence and candidate facts."

    layered_section = ""
    if _env("ENABLE_CONTEXT_PACKING_EXTRACT", "false").lower() in ("1", "true", "yes"):
        corpus_memory = state.get("corpus_memory") or []
        evidence_chunks = state.get("evidence_chunks") or stub_retrieve_evidence(raw_text)
        working_state = {
            "schema": "triples array required",
            "constraints": [
                "triples must include subject, predicate, object, confidence",
                "include evidence snippets with provenance if available",
            ],
            "conflicts": state.get("critiques") or [],
        }
        layered_section = build_extraction_layers(corpus_memory, evidence_chunks, working_state)

    # Enhanced schema instruction for structured claims (strict JSON mapping to Claim schema)
    schema_instruction = """
CRITICAL: You MUST return valid JSON ONLY (no prose, no markdown code blocks). The output MUST strictly conform to this schema:

{
  "triples": [
    {
      "subject": "string (required)",
      "predicate": "string (required)",
      "object": "string (required)",
      "confidence": 0.0-1.0 (required, float),
      "claim_text": "string (human-readable claim, required)",
      "relevance_score": 0.0-1.0 (relevance to thesis/RQs, optional but recommended),
      "rq_hits": ["RQ1", "RQ2"] (array of research question IDs this claim addresses, required),
      "source_pointer": {
        "doc_hash": "string (file hash/SHA256, required)",
        "page": integer (1-based page number, required),
        "bbox": [x1, y1, x2, y2] (optional, bounding box coordinates),
        "snippet": "string (text excerpt, optional but recommended)"
      }
    }
  ]
}

REQUIREMENTS:
- Every triple MUST have: subject, predicate, object, confidence, claim_text, rq_hits
- rq_hits MUST be a non-empty array (at least one RQ ID)
- source_pointer.doc_hash and source_pointer.page MUST be present
- In conservative mode, bbox or snippet MUST be present in source_pointer
"""
    
    # Add schema instruction (always include for strict enforcement)
    system_prompt = f"{system_prompt}\n\n{schema_instruction}"
    
    # Add RQ-scoped chunks context if available
    if rq_scoped_chunks:
        chunks_section = "\n\nRetrieved Evidence Chunks (RQ-scoped):\n"
        for rq_id, chunks in rq_scoped_chunks.items():
            if chunks:
                chunks_section += f"\n{rq_id} Evidence:\n"
                for chunk in chunks[:3]:  # Show first 3 chunks per RQ
                    text = chunk.get("text_content", "")[:200]  # Truncate for prompt
                    page = chunk.get("page_number", "?")
                    chunks_section += f"- Page {page}: {text}...\n"
        system_prompt = f"{system_prompt}\n{chunks_section}"
    
    # Build user content with RQ-scoped chunks if available
    user_sections = []
    
    # If we have RQ-scoped chunks, use them instead of raw_text
    if rq_scoped_chunks and all_chunks_with_anchors:
        user_sections.append("Evidence Chunks (retrieved from knowledge base):\n")
        for rq_id, chunks in rq_scoped_chunks.items():
            if chunks:
                user_sections.append(f"\n{rq_id} Evidence:")
                for chunk in chunks:
                    text = chunk.get("text_content", "")
                    page = chunk.get("page_number", "?")
                    file_hash = chunk.get("file_hash", "")
                    user_sections.append(f"[Page {page}, File: {file_hash[:16]}...]\n{text}\n")
    else:
        # Fallback to raw_text if no chunks available
        user_sections.append(f"Document:\n{raw_text}")
    
    if layered_section:
        user_sections.append(f"Layered context:\n{layered_section}")
    if critiques:
        user_sections.append(f"Previous critiques: {' | '.join(critiques)}")
    user_content = "\n\n".join(user_sections)

    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        # Get role for allowed_tools
        role = role_registry.get_role("cartographer")
        
        # Route to appropriate expert: Cartographer uses Worker (extraction) with Brain fallback
        expert_url, expert_name, expert_model = route_to_expert("cartographer_node", ExpertType.EXTRACTION_SCHEMA)
        fallback_url = get_brain_url() if expert_name == "Worker" else None
        fallback_model = get_model_config("brain").model_id if fallback_url else None

        data, meta = call_expert_with_fallback(
            expert_url=expert_url,
            expert_name=expert_name,
            model_id=expert_model,
            prompt=prompt,
            request_params={
                "temperature": 0.6,
                "top_p": 0.95,
                "max_tokens": 4096,
                "response_format": {"type": "json_object"},
            },
            fallback_url=fallback_url,
            fallback_model_id=fallback_model,
            node_name="cartographer_node",
            state=state,
            allowed_tools=role.allowed_tools,
        )
        latency_ms = meta.get("duration_ms", 0.0)
        usage = meta.get("usage")
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        
        # Parse JSON (handle markdown code blocks if present)
        if isinstance(content, str):
            # Remove markdown code blocks if present
            if content.strip().startswith("```"):
                lines = content.strip().split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
            extracted = json.loads(content)
        else:
            extracted = content
        
        # Normalize to guarantee triples structure (early normalization)
        normalized = normalize_extracted_json(extracted)
        
        # Validate normalized structure: ensure triples exists and is a list
        if not isinstance(normalized, dict):
            logger.warning(
                "Cartographer: normalized output is not a dict, using empty structure",
                extra={"payload": {"normalized_type": type(normalized).__name__}},
            )
            normalized = {"triples": []}
        
        if "triples" not in normalized:
            logger.warning(
                "Cartographer: normalized output missing 'triples' key, adding empty array",
                extra={"payload": {"normalized_keys": list(normalized.keys())}},
            )
            normalized["triples"] = []
        
        if not isinstance(normalized.get("triples"), list):
            logger.warning(
                "Cartographer: normalized 'triples' is not a list, converting to empty array",
                extra={"payload": {"triples_type": type(normalized.get("triples")).__name__}},
            )
            normalized["triples"] = []
        
        # Convert triples to canonical Claim objects with source_anchor from Qdrant payload
        triples = normalized.get("triples", [])
        if isinstance(triples, list):
            from ..schemas.claims import Claim, SourceAnchor
            
            canonical_claims = []
            chunk_map = {chunk.get("chunk_id"): chunk for chunk in all_chunks_with_anchors}
            
            for triple in triples:
                if not isinstance(triple, dict):
                    continue
                
                # Try to find matching chunk by text similarity or use source_pointer
                source_pointer = triple.get("source_pointer", {})
                doc_hash = source_pointer.get("doc_hash") or triple.get("file_hash")
                page_number = source_pointer.get("page") or triple.get("page_number", 1)
                
                # Find matching chunk from Qdrant results
                matching_chunk = None
                if doc_hash and page_number:
                    for chunk in all_chunks_with_anchors:
                        if (chunk.get("file_hash") == doc_hash and 
                            chunk.get("page_number") == page_number):
                            matching_chunk = chunk
                            break
                
                # Build source_anchor from chunk payload or source_pointer
                source_anchor = None
                if matching_chunk:
                    payload = matching_chunk.get("payload", {})
                    anchor_data = {
                        "doc_id": payload.get("file_hash") or doc_hash or "",
                        "page_number": payload.get("page_number") or page_number,
                    }
                    if payload.get("bbox"):
                        anchor_data["bbox"] = payload["bbox"]
                    if source_pointer.get("snippet") or matching_chunk.get("text_content"):
                        anchor_data["snippet"] = source_pointer.get("snippet") or matching_chunk.get("text_content", "")[:200]
                    try:
                        source_anchor = SourceAnchor(**anchor_data)
                    except Exception as e:
                        logger.warning(f"Failed to create SourceAnchor from chunk payload: {e}", exc_info=True)
                elif source_pointer:
                    # Fallback: create from source_pointer
                    anchor_data = {
                        "doc_id": doc_hash or "",
                        "page_number": page_number,
                    }
                    if source_pointer.get("bbox"):
                        bbox = source_pointer["bbox"]
                        if isinstance(bbox, list) and len(bbox) == 4:
                            x1, y1, x2, y2 = bbox
                            anchor_data["bbox"] = {"x": float(x1), "y": float(y1), "w": float(x2 - x1), "h": float(y2 - y1)}
                    if source_pointer.get("snippet"):
                        anchor_data["snippet"] = source_pointer["snippet"]
                    try:
                        source_anchor = SourceAnchor(**anchor_data) if anchor_data.get("doc_id") else None
                    except Exception as e:
                        logger.warning(f"Failed to create SourceAnchor from source_pointer: {e}", exc_info=True)
                
                # Convert to Claim using from_triple_dict
                try:
                    # Ensure ingestion_id is present
                    triple["ingestion_id"] = ingestion_id or triple.get("ingestion_id", "")
                    triple["file_hash"] = doc_hash or triple.get("file_hash", "")
                    
                    # Create Claim from triple dict
                    claim = Claim.from_triple_dict(triple, ingestion_id=ingestion_id or "", rigor_level=rigor_level)
                    
                    # Override source_anchor if we have a better one from Qdrant
                    if source_anchor:
                        claim.source_anchor = source_anchor
                    
                    # Validate in conservative mode (fail explicitly, no silent rejection)
                    if rigor_level == "conservative":
                        if not claim.source_anchor:
                            error_msg = f"Claim {claim.claim_id} missing source_anchor in conservative mode"
                            logger.error(
                                error_msg,
                                extra={"payload": {"claim_id": claim.claim_id, "triple": triple}}
                            )
                            raise ValueError(error_msg)
                        if not claim.rq_hits:
                            error_msg = f"Claim {claim.claim_id} missing rq_hits in conservative mode"
                            logger.error(
                                error_msg,
                                extra={"payload": {"claim_id": claim.claim_id, "triple": triple}}
                            )
                            raise ValueError(error_msg)
                    elif rigor_level == "exploratory":
                        # In exploratory, warn but allow
                        if not claim.source_anchor:
                            logger.warning(
                                f"Claim {claim.claim_id} missing source_anchor (exploratory mode, allowing)",
                                extra={"payload": {"claim_id": claim.claim_id}}
                            )
                        if not claim.rq_hits:
                            logger.warning(
                                f"Claim {claim.claim_id} missing rq_hits (exploratory mode, allowing)",
                                extra={"payload": {"claim_id": claim.claim_id}}
                            )
                    
                    # Convert back to dict for state (maintain backward compatibility)
                    canonical_claims.append(claim.model_dump(exclude_none=True))
                except Exception as e:
                    logger.error(
                        f"Failed to convert triple to Claim: {e}",
                        exc_info=True,
                        extra={"payload": {"triple_keys": list(triple.keys())}}
                    )
                    # In conservative mode, fail explicitly on schema validation errors
                    if rigor_level == "conservative":
                        error_msg = f"Failed to convert triple to Claim in conservative mode: {e}"
                        logger.error(
                            error_msg,
                            extra={"payload": {"triple_keys": list(triple.keys()), "error": str(e)}}
                        )
                        raise ValueError(error_msg) from e
                    # In exploratory, include as-is
                    canonical_claims.append(triple)
            
            normalized["triples"] = canonical_claims
            triples = canonical_claims
        
        triples_count = len(triples)
        # Determine actual model used (may be Brain if fallback was used)
        actual_model = meta.get("model_id") or expert_model
        actual_expert_name = meta.get("expert_name", expert_name)
        actual_expert_url = meta.get("url_base", expert_url)
        logger.info(
            "Cartographer extracted graph",
            extra={
                "payload": {
                    "triples_count": triples_count,
                    "has_entities": "entities" in normalized,
                    "expert": actual_expert_name,
                    "telemetry": {
                        "model_id": actual_model,
                        "task_type": "extract",
                        "tokens_in_est": estimate_tokens(raw_text),
                        "tokens_out_est": estimate_tokens(content if isinstance(content, str) else json.dumps(content)),
                        "latency_ms": latency_ms,
                        "kv_policy": get_model_config("worker").kv_policy if actual_expert_name == "Worker" else get_model_config("brain").kv_policy,
                    },
                }
            },
        )
        enriched_state: ResearchState = {}
        if usage:
            enriched_state["_sglang_usage"] = usage  # type: ignore[index]
        enriched_state["_expert_name"] = actual_expert_name  # type: ignore[index]
        enriched_state["_expert_url"] = actual_expert_url  # type: ignore[index]
        return {
            **enriched_state,
            "extracted_json": normalized,
            "triples": normalized.get("triples", []),
            "context_sources": merged_context_sources,
            "selected_reference_ids": selected_reference_ids,
            "phase": PhaseEnum.MAPPING.value,
        }
    except json.JSONDecodeError as e:
        logger.error(
            "Cartographer failed to parse JSON response",
            extra={"payload": {"prompt_chars": len(raw_text), "error": str(e)}},
            exc_info=True,
        )
        # Return empty structure on JSON parse failure
        return {"extracted_json": {"triples": []}, "triples": [], "phase": PhaseEnum.MAPPING.value}
    except Exception as e:
        logger.error(
            "Cartographer failed to extract graph",
            extra={"payload": {"prompt_chars": len(raw_text), "error": str(e)}},
            exc_info=True,
        )
        # Return empty structure on failure (don't raise to allow workflow to continue)
        return {"extracted_json": {"triples": []}, "triples": [], "phase": PhaseEnum.MAPPING.value}

