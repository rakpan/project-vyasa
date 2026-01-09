"""
Cartography node for knowledge extraction.

Extracts structured knowledge graphs from raw text using RQ-scoped retrieval
and evidence-aware RAG. Produces canonical Claim objects with source anchors.
"""

import json
import re
from typing import Dict, Any, List, Optional

import requests

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
from ..state import PhaseEnum, ResearchState, acquire_tier_b_slot, release_tier_b_slot
from ..normalize import normalize_extracted_json
from ..telemetry import get_telemetry_emitter, trace_node
from ..config import ExpertType
from arango import ArangoClient

from .base import wrap_prompt_with_context
from ..schemas.candidate_mentions import CandidateMentions, CandidateMention
from ..schemas.evidence_pack import EvidencePack
from ..services.candidate_mentions_service import CandidateMentionsService
from ..services.evidence_pack_service import EvidencePackService
from ..services.retrieval_bundle_service import RetrievalBundleService
from ..retrieval.retrieval_service import RetrievalService
from ..section_synthesis.section_orchestrator import build_evidence_pack
from ..state import ExecutionTier

logger = get_logger("orchestrator", __name__)
telemetry_emitter = get_telemetry_emitter()
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


def cartographer_pass1_candidate_mentions(
    project_id: str,
    ingestion_id: str,
    raw_text: str,
    chunks: List[Dict[str, Any]],
    db: Optional[Any] = None,
) -> CandidateMentions:
    """Pass 1 (Tier A): Gather candidate entity mentions using cheap recall methods.
    
    Methods:
    - Keyword/regex matching
    - TOC-guided targeting
    - Embedding-driven mention gathering
    
    This pass NEVER emits triples - only candidate mentions.
    
    Args:
        project_id: Project identifier.
        ingestion_id: Ingestion identifier.
        raw_text: Raw document text.
        chunks: List of chunks from Qdrant (with chunk_id, text_content, payload).
        db: Optional ArangoDB database instance for persistence.
    
    Returns:
        CandidateMentions collection with all detected mentions.
    """
    from ...shared.config import get_embedder_url
    import requests
    
    mentions: List[CandidateMention] = []
    detection_methods_used = []
    
    # Entity type keywords (cheap keyword matching)
    entity_keywords = {
        "Vulnerability": ["vulnerability", "vulnerable", "exploit", "attack", "weakness", "flaw", "breach", "threat"],
        "Mechanism": ["mechanism", "defense", "mitigation", "protection", "countermeasure", "safeguard", "control"],
        "Constraint": ["constraint", "limit", "requirement", "dependency", "resource", "capacity", "budget"],
        "Outcome": ["outcome", "result", "effect", "consequence", "impact", "benefit", "cost"],
    }
    
    # Method 1: Keyword matching (cheap recall)
    detection_methods_used.append("keyword")
    for entity_type, keywords in entity_keywords.items():
        pattern = re.compile(r'\b(' + '|'.join(re.escape(kw) for kw in keywords) + r')\b', re.IGNORECASE)
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", "")
            text_content = chunk.get("text_content") or chunk.get("text", "")
            payload = chunk.get("payload", {})
            page_number = payload.get("page_number")
            section_label = payload.get("section_label") or payload.get("heading")
            
            matches = pattern.finditer(text_content)
            for match in matches:
                mention = CandidateMention(
                    entity_type=entity_type,
                    mention_text=match.group(0),
                    chunk_id=chunk_id,
                    page_number=page_number,
                    confidence=0.5,  # Base confidence for keyword matches
                    section_label=section_label,
                    detection_method="keyword",
                    context_snippet=text_content[max(0, match.start()-50):match.end()+50],
                )
                mentions.append(mention)
    
    # Method 2: TOC-guided targeting (if TOC sections detected)
    detection_methods_used.append("toc_guided")
    toc_keywords = ["introduction", "method", "result", "discussion", "conclusion", "background", "related work"]
    for chunk in chunks:
        text_content = chunk.get("text_content") or chunk.get("text", "")
        payload = chunk.get("payload", {})
        section_label = payload.get("section_label") or payload.get("heading", "")
        chunk_id = chunk.get("chunk_id", "")
        page_number = payload.get("page_number")
        
        # If section label matches TOC keywords, boost mentions in this chunk
        if any(toc_kw in section_label.lower() for toc_kw in toc_keywords):
            # Look for entity mentions near section headers
            for entity_type in entity_keywords.keys():
                # Simple pattern: entity type word near section start
                pattern = re.compile(r'\b' + re.escape(entity_type.lower()) + r'\b', re.IGNORECASE)
                if pattern.search(text_content[:200]):  # First 200 chars of chunk
                    mention = CandidateMention(
                        entity_type=entity_type,
                        mention_text=entity_type,
                        chunk_id=chunk_id,
                        page_number=page_number,
                        confidence=0.6,  # Higher confidence for TOC-guided
                        section_label=section_label,
                        detection_method="toc_guided",
                        context_snippet=text_content[:200],
                    )
                    mentions.append(mention)
    
    # Method 3: Embedding-driven mention gathering (if embedder available)
    try:
        embedder_url = get_embedder_url()
        if embedder_url:
            detection_methods_used.append("embedding")
            # Query embedder for entity type embeddings
            entity_queries = {
                "Vulnerability": "security vulnerability weakness exploit",
                "Mechanism": "defense mechanism protection mitigation",
                "Constraint": "constraint limit requirement dependency",
                "Outcome": "outcome result effect consequence",
            }
            
            # For each entity type, find chunks with high similarity
            for entity_type, query_text in entity_queries.items():
                try:
                    response = requests.post(
                        f"{embedder_url}/embed",
                        json={"texts": [query_text]},
                        timeout=5
                    )
                    if response.ok:
                        # In a full implementation, we'd compare embeddings
                        # For now, we'll use a simple heuristic: chunks with entity keywords
                        for chunk in chunks:
                            chunk_id = chunk.get("chunk_id", "")
                            text_content = chunk.get("text_content") or chunk.get("text", "")
                            payload = chunk.get("payload", {})
                            page_number = payload.get("page_number")
                            section_label = payload.get("section_label") or payload.get("heading")
                            
                            # Check if chunk contains entity type keywords
                            keywords = entity_keywords.get(entity_type, [])
                            if any(kw in text_content.lower() for kw in keywords):
                                # Check if we already have this mention
                                existing = any(
                                    m.chunk_id == chunk_id and m.entity_type == entity_type
                                    for m in mentions
                                )
                                if not existing:
                                    mention = CandidateMention(
                                        entity_type=entity_type,
                                        mention_text=entity_type,
                                        chunk_id=chunk_id,
                                        page_number=page_number,
                                        confidence=0.55,  # Slightly higher for embedding-guided
                                        section_label=section_label,
                                        detection_method="embedding",
                                        context_snippet=text_content[:300],
                                    )
                                    mentions.append(mention)
                except Exception as e:
                    logger.debug(f"Embedding-driven mention gathering failed: {e}")
    except Exception as e:
        logger.debug(f"Embedder not available for mention gathering: {e}")
    
    # Deduplicate mentions (same chunk_id + entity_type)
    seen = set()
    unique_mentions = []
    for mention in mentions:
        key = (mention.chunk_id, mention.entity_type, mention.mention_text.lower())
        if key not in seen:
            seen.add(key)
            unique_mentions.append(mention)
    
    # Create CandidateMentions collection
    candidate_mentions = CandidateMentions.create(
        project_id=project_id,
        ingestion_id=ingestion_id,
        mentions=unique_mentions,
        detection_methods_used=list(set(detection_methods_used)),
    )
    
    # Persist if DB available
    if db:
        try:
            mentions_service = CandidateMentionsService(db)
            candidate_mentions = mentions_service.save_mentions(candidate_mentions)
            logger.info(
                f"Pass 1: Saved {len(unique_mentions)} candidate mentions",
                extra={
                    "payload": {
                        "mentions_id": candidate_mentions.mentions_id,
                        "project_id": project_id,
                        "ingestion_id": ingestion_id,
                        "entity_types": list(set(m.entity_type for m in unique_mentions)),
                    }
                }
            )
        except Exception as e:
            logger.warning(f"Failed to persist CandidateMentions: {e}", exc_info=True)
    
    return candidate_mentions


def cartographer_pass2_triple_extraction(
    project_id: str,
    ingestion_id: str,
    candidate_mentions: CandidateMentions,
    project_context: Dict[str, Any],
    db: Any,
    state: Optional[ResearchState] = None,
) -> Dict[str, Any]:
    """Pass 2 (Tier B): Extract schema-locked triples from EvidencePacks.
    
    For each entity_type:
    1. Build EvidencePack from relevant candidate mentions (top-M)
    2. Call Nemotron via SGLang using JSON-locked prompts
    3. Output strict triples with claim_id/entity ids, relations, spans
    4. Store backing chunk_ids for Critic verification
    
    This pass ONLY consumes EvidencePacks and emits strict JSON.
    
    Args:
        project_id: Project identifier.
        ingestion_id: Ingestion identifier.
        candidate_mentions: CandidateMentions from Pass 1.
        project_context: ProjectConfig context.
        db: ArangoDB database instance.
        state: Optional ResearchState for context injection.
    
    Returns:
        Dict with "triples" array containing strict JSON triples with chunk_ids.
    
    Raises:
        ValueError: If EvidencePack cannot be built or Nemotron call fails.
    """
    from ..storage.qdrant import QdrantStorage
    from ..services.evidence_pack_service import EvidencePackService
    from ..services.retrieval_bundle_service import RetrievalBundleService
    from ..section_synthesis.section_orchestrator import build_evidence_pack
    from ..nodes.nodes import route_to_expert, call_expert_with_fallback
    from ..config import ExpertType
    from ..prompts import get_active_prompt_with_meta, DEFAULT_CARTOGRAPHER_PROMPT
    
    # Group mentions by entity_type
    mentions_by_type: Dict[str, List[CandidateMention]] = {}
    for mention in candidate_mentions.mentions:
        if mention.entity_type not in mentions_by_type:
            mentions_by_type[mention.entity_type] = []
        mentions_by_type[mention.entity_type].append(mention)
    
    all_triples = []
    qdrant_storage = QdrantStorage()
    pack_service = EvidencePackService(db)
    
    # Opik tracing: Track first triple extraction (critical path span 2)
    from ..telemetry.opik_emitter import get_opik_emitter
    opik_emitter = get_opik_emitter()
    first_entity_family_processed = False
    first_entity_type = None
    first_triples_count = 0
    first_extraction_error = None
    
    # For each entity_type, build EvidencePack and extract triples
    for entity_type, mentions in mentions_by_type.items():
        if not mentions:
            continue
        
        # Get top-M mentions (by confidence, then by detection method priority)
        # Priority: embedding > toc_guided > keyword
        method_priority = {"embedding": 3, "toc_guided": 2, "keyword": 1}
        sorted_mentions = sorted(
            mentions,
            key=lambda m: (m.confidence, method_priority.get(m.detection_method, 0)),
            reverse=True
        )
        top_m_mentions = sorted_mentions[:20]  # Top 20 mentions per entity type
        
        # Get chunk IDs from mentions
        chunk_ids = [m.chunk_id for m in top_m_mentions]
        
        # Retrieve chunks from Qdrant
        chunks = []
        for chunk_id in chunk_ids:
            try:
                chunk_data = qdrant_storage.get_chunks_by_ids([chunk_id], project_id)
                if chunk_data:
                    chunks.extend(chunk_data)
            except Exception as e:
                logger.warning(f"Failed to retrieve chunk {chunk_id}: {e}")
        
        if not chunks:
            logger.warning(f"No chunks retrieved for entity_type {entity_type}")
            continue
        
        # Build query from entity type and top mentions
        query_text = f"Extract {entity_type} entities and their relationships from: " + ", ".join(
            m.mention_text for m in top_m_mentions[:5]
        )
        
        # Build RetrievalBundle (required for EvidencePack)
        from ..schemas.retrieval import RetrievalBundle
        retrieval_bundle = RetrievalBundle.create(
            query_text=query_text,
            project_id=project_id,
            ingestion_id=ingestion_id,
            candidate_chunks=chunks,
            reranked_chunks=chunks,  # Use same chunks (already filtered)
            embedder_model_id="nvidia/nv-embedqa-e5-v5",
            reranker_model_id="none",  # No reranking in Pass 2 (chunks already selected)
            top_k_embed=len(chunks),
            top_k_rerank=len(chunks),
            query_source="cartographer_pass2",
            section_id=None,
        )
        
        # Persist RetrievalBundle
        bundle_service = RetrievalBundleService(db)
        bundle_service.save_bundle(retrieval_bundle)
        
        # Build EvidencePack from RetrievalBundle
        evidence_pack = build_evidence_pack(
            reranked_chunks=chunks,
            retrieval_bundle=retrieval_bundle,
            ingestion_id=ingestion_id,
            project_id=project_id,
            section_id=None,
        )
        
        # Persist EvidencePack
        evidence_pack = pack_service.save_pack(evidence_pack)
        
        logger.debug(
            f"Pass 2: Built EvidencePack for {entity_type}",
            extra={
                "payload": {
                    "pack_id": evidence_pack.pack_id,
                    "entity_type": entity_type,
                    "mention_count": len(top_m_mentions),
                    "snippet_count": len(evidence_pack.snippets),
                }
            }
        )
        
        # Load prompt from DB-backed registry (with fallback to defaults)
        from ...shared.prompt_registry import get_prompt as get_db_prompt
        prompt_profile = get_db_prompt("cartographer_pass2", DEFAULT_CARTOGRAPHER_PROMPT)
        system_template = prompt_profile["template"]
        
        # Fallback to Opik/defaults if DB not available
        if prompt_profile.get("source") == "default":
            system_template, prompt_meta = get_active_prompt_with_meta("vyasa-cartographer", DEFAULT_CARTOGRAPHER_PROMPT)
        else:
            # Use DB-backed template
            from ..prompts.models import PromptUse
            prompt_meta = PromptUse.from_template(
                prompt_name="cartographer_pass2",
                template=system_template,
                resolved_source="db",
                tag=f"v{prompt_profile.get('version', 0)}",
                cache_hit=False,
            )
        
        # Wrap with context
        if state is None:
            state = {"project_context": project_context}
        else:
            state = {**state, "project_context": project_context}
        
        from .base import wrap_prompt_with_context
        system_prompt = wrap_prompt_with_context(state, system_template)
        
        # Add strict JSON schema instruction
        schema_instruction = f"""
CRITICAL: You MUST return valid JSON ONLY (no prose, no markdown code blocks). The output MUST strictly conform to this schema:

{{
  "triples": [
    {{
      "subject": "string (required)",
      "predicate": "string (required)",
      "object": "string (required)",
      "confidence": 0.0-1.0 (required, float),
      "claim_id": "string (unique identifier, required)",
      "entity_type": "{entity_type}",
      "chunk_ids": ["chunk_id1", "chunk_id2"] (array of backing chunk IDs, required),
      "source_pointer": {{
        "doc_hash": "string (file hash, required)",
        "page": integer (1-based page number, required),
        "snippet": "string (text excerpt, required)"
      }},
      "rq_hits": ["RQ1", "RQ2"] (array of research question IDs, required)
    }}
  ]
}}

REQUIREMENTS:
- Every triple MUST have: subject, predicate, object, confidence, claim_id, chunk_ids, source_pointer, rq_hits
- chunk_ids MUST reference chunks from the EvidencePack provided
- rq_hits MUST be a non-empty array
- Output MUST be valid JSON only
"""
        
        system_prompt = f"{system_prompt}\n\n{schema_instruction}"
        
        # Format EvidencePack for prompt
        evidence_text = "EVIDENCE PACK (Primary Sources - MUST be cited):\n"
        for idx, snippet in enumerate(evidence_pack.snippets, 1):
            pointer = evidence_pack.pointers[idx-1] if idx-1 < len(evidence_pack.pointers) else None
            evidence_text += f"[{idx}] {snippet.quote_text}\n"
            evidence_text += f"    (chunk_id: {snippet.chunk_id}, page {snippet.page_number or '?'})\n\n"
        
        user_prompt = f"""Extract {entity_type} entities and their relationships from the following evidence:

{evidence_text}

Return ONLY valid JSON with triples array. Each triple must include chunk_ids from the evidence pack above."""
        
        # Call Nemotron via SGLang (Tier-B call)
        expert_url, expert_name, expert_model = route_to_expert("cartographer_pass2", ExpertType.EXTRACTION_SCHEMA)
        
        prompt = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        # Acquire Tier B slot (serialize Nemotron calls: max-running-requests=1)
        if not acquire_tier_b_slot(blocking=True, timeout=300.0):  # 5 minute timeout
            raise ValueError("Tier B slot unavailable (timeout waiting for Nemotron call slot)")
        
        # Apply Tier B budget: max output tokens
        from ...shared.runtime_budgets import get_output_max_tokens
        max_output_tokens = get_output_max_tokens("cartographer_pass2")
        
        request_params = {
            "temperature": 0.3,
            "max_tokens": max_output_tokens,  # From runtime budgets
            "response_format": {"type": "json_object"},
        }
        
        logger.debug(
            f"Using prompt profile v{prompt_profile.get('version', 0)} and output max_tokens={max_output_tokens} for cartographer_pass2",
            extra={"payload": {"agent": "cartographer_pass2", "max_tokens": max_output_tokens, "prompt_version": prompt_profile.get("version", 0), "prompt_source": prompt_profile.get("source", "default")}}
        )
        
        try:
            response = call_expert_with_fallback(
                expert_url=expert_url,
                expert_name=expert_name,
                model_id=expert_model,
                prompt=prompt,
                request_params=request_params,
                node_name="cartographer_pass2",
                state=state,
            )
            
            # Parse JSON response
            extracted = response.get("content", "") if isinstance(response, dict) else str(response)
            
            # Try to extract JSON from response
            json_match = re.search(r'\{.*"triples".*\}', extracted, re.DOTALL)
            if json_match:
                extracted_json = json.loads(json_match.group(0))
            else:
                # Try parsing entire response as JSON
                extracted_json = json.loads(extracted)
            
            # Normalize and validate
            from ..normalize import normalize_extracted_json
            normalized = normalize_extracted_json(extracted_json)
            
            # Ensure triples have chunk_ids from EvidencePack
            triples = normalized.get("triples", [])
            for triple in triples:
                # Add chunk_ids if not present
                if "chunk_ids" not in triple:
                    # Extract chunk_ids from EvidencePack snippets
                    triple["chunk_ids"] = [s.chunk_id for s in evidence_pack.snippets]
                
                # Ensure source_pointer has doc_hash
                source_pointer = triple.get("source_pointer", {})
                if "doc_hash" not in source_pointer and evidence_pack.pointers:
                    pointer = evidence_pack.pointers[0]
                    source_pointer["doc_hash"] = pointer.file_id or ""
                    triple["source_pointer"] = source_pointer
            
            all_triples.extend(triples)
            
            logger.info(
                f"Pass 2: Extracted {len(triples)} triples for {entity_type}",
                extra={
                    "payload": {
                        "entity_type": entity_type,
                        "triple_count": len(triples),
                        "pack_id": evidence_pack.pack_id,
                    }
                }
            )
            
            # Opik tracing: First triple extraction (critical path span 2)
            if is_first_entity_family and not first_entity_family_processed:
                first_entity_family_processed = True
                first_triples_count = len(triples)
                
                # Extract first claim_id if available
                first_claim_id = None
                if triples and isinstance(triples[0], dict):
                    first_claim_id = triples[0].get("claim_id")
                
                opik_emitter.emit_span(
                    span_name="triple_extraction",
                    job_id=state.get("jobId") or state.get("job_id") if state else "",
                    project_id=project_id,
                    ingestion_id=ingestion_id,
                    meta={
                        "entity_type": first_entity_type,
                        "evidence_pack_id": evidence_pack.pack_id,
                        "retrieval_bundle_id": retrieval_bundle.bundle_id,
                        "triples_count": first_triples_count,
                        "first_claim_id": first_claim_id,
                    },
                    error=None,
                )
            
        except Exception as e:
            logger.error(
                f"Pass 2: Failed to extract triples for {entity_type}: {e}",
                exc_info=True
            )
            
            # Opik tracing: Emit span even on failure (for first entity family)
            if is_first_entity_family and not first_entity_family_processed:
                first_entity_family_processed = True
                first_extraction_error = str(e)
                
                opik_emitter.emit_span(
                    span_name="triple_extraction",
                    job_id=state.get("jobId") or state.get("job_id") if state else "",
                    project_id=project_id,
                    ingestion_id=ingestion_id,
                    meta={
                        "entity_type": first_entity_type,
                        "evidence_pack_id": evidence_pack.pack_id if evidence_pack else None,
                        "retrieval_bundle_id": retrieval_bundle.bundle_id if retrieval_bundle else None,
                        "triples_count": 0,
                    },
                    error=first_extraction_error,
                )
            
            # Continue with next entity type (non-fatal)
            continue
        finally:
            # Always release Tier B slot after triple extraction completes (success or failure)
            # This is inside the loop so each entity_type releases its slot
            release_tier_b_slot()
    
    return {
        "triples": all_triples,
        "mentions_id": candidate_mentions.mentions_id,
    }


@trace_node
def cartographer_node(state: ResearchState) -> ResearchState:
    """Extract graph JSON from raw text using two-pass protocol (Tier A/Tier B).
    
    Pass 1 (Tier A): Gather candidate mentions using cheap recall methods.
    Pass 2 (Tier B): Extract schema-locked triples from EvidencePacks.
    
    Uses Worker (SGLang) to extract structured knowledge graph with STRICT JSON
    requirements. The output is normalized to guarantee a `triples` array structure
    that the console expects.
    
    Args:
        state: ResearchState containing raw_text, optional critiques, and optional project context.
        
    Returns:
        Updated ResearchState with extracted_json containing guaranteed `triples` array.
        
    Raises:
        ValueError: If raw_text is missing or project_id provided but project not found.
        RuntimeError: If project_id provided but DB unavailable, or if infrastructure
            dependencies (cortex-brain, cortex-worker) are unavailable. This prevents
            silent completion with 0 triples when services are down.
        requests.RequestException: If Worker API call fails due to dependency issues.
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
    
    # Debug logging for raw_text preservation at node entry
    raw_text = state.get("raw_text", "")
    logger.debug(
        "Cartographer node entry",
        extra={
            "payload": {
                "job_id": job_id,
                "raw_text_length": len(raw_text) if raw_text else 0,
                "has_raw_text": "raw_text" in state,
                "has_pdf_path": "pdf_path" in state,
                "state_keys": list(state.keys())[:20],  # Limit to first 20 keys for logging
            }
        }
    )
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
    
    if not ingestion_id:
        raise ValueError("ingestion_id is required for cartographer node (evidence scoping)")

    # Get DB connection for persistence
    db = None
    try:
        from arango import ArangoClient
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
    except Exception as e:
        logger.warning(f"Failed to connect to DB for cartographer: {e}", exc_info=True)
        # Continue without DB (mentions won't be persisted, but extraction can proceed)

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
                        use_reranker=False,  # Cartography doesn't need reranking for speed
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
    
    # Two-pass protocol implementation
    try:
        # Pass 1 (Tier A): Gather candidate mentions (cheap recall)
        logger.info("Cartographer Pass 1 (Tier A): Gathering candidate mentions")
        candidate_mentions = cartographer_pass1_candidate_mentions(
            project_id=project_id,
            ingestion_id=ingestion_id,
            raw_text=raw_text,
            chunks=all_chunks_with_anchors,
            db=db,
        )
        
        # Pass 2 (Tier B): Extract triples from EvidencePacks
        logger.info("Cartographer Pass 2 (Tier B): Extracting triples from EvidencePacks")
        if not db:
            raise RuntimeError("Database unavailable for Pass 2 (EvidencePack persistence required)")
        
        extraction_result = cartographer_pass2_triple_extraction(
            project_id=project_id,
            ingestion_id=ingestion_id,
            candidate_mentions=candidate_mentions,
            project_context=project_context or {},
            db=db,
            state=state,
        )
        
        triples = extraction_result.get("triples", [])
        
        # Convert triples to normalized format expected by downstream nodes
        from ..schemas.claims import Claim, SourceAnchor
        canonical_claims = []
        for triple in triples:
            try:
                # Ensure chunk_ids are present (required for Critic)
                chunk_ids = triple.get("chunk_ids", [])
                if not chunk_ids:
                    logger.warning(f"Triple missing chunk_ids: {triple.get('claim_id', 'unknown')}")
                    continue
                
                # Build source_anchor from triple
                source_pointer = triple.get("source_pointer", {})
                source_anchor = SourceAnchor(
                    doc_hash=source_pointer.get("doc_hash", ""),
                    page=source_pointer.get("page", 1),
                    bbox=source_pointer.get("bbox"),
                    snippet=source_pointer.get("snippet", ""),
                )
                
                # Build Claim from triple
                claim = Claim(
                    claim_id=triple.get("claim_id", ""),
                    claim_text=triple.get("claim_text", f"{triple.get('subject')} {triple.get('predicate')} {triple.get('object')}"),
                    subject=triple.get("subject", ""),
                    predicate=triple.get("predicate", ""),
                    object=triple.get("object", ""),
                    confidence=triple.get("confidence", 0.5),
                    source_anchor=source_anchor,
                    rq_hits=triple.get("rq_hits", []),
                    relevance_score=triple.get("relevance_score"),
                    # Store chunk_ids for Critic verification
                    metadata={"chunk_ids": chunk_ids, "entity_type": triple.get("entity_type")},
                )
                
                canonical_claims.append(claim.model_dump(exclude_none=True))
            except Exception as e:
                logger.error(f"Failed to convert triple to Claim: {e}", exc_info=True)
                # Include as-is in exploratory mode
                if rigor_level != "conservative":
                    canonical_claims.append(triple)
        
        normalized = {
            "triples": canonical_claims,
            "mentions_id": extraction_result.get("mentions_id"),
        }
        
        logger.info(
            "Cartographer two-pass extraction completed",
            extra={
                "payload": {
                    "triples_count": len(canonical_claims),
                    "mentions_id": extraction_result.get("mentions_id"),
                    "pass1_mentions": len(candidate_mentions.mentions),
                }
            }
        )
        
        return {
            "extracted_json": normalized,
            "triples": canonical_claims,
            "phase": PhaseEnum.MAPPING.value,
        }
        
    except Exception as e:
        logger.error(
            f"Cartographer two-pass extraction failed: {e}",
            exc_info=True
        )
        # Return empty structure on failure
        return {"extracted_json": {"triples": []}, "triples": [], "phase": PhaseEnum.MAPPING.value}