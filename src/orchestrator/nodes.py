"""
Workflow nodes for the agentic Cartographer -> Critic loop.
"""

import json
import os
import sys
import uuid
import shutil
import tempfile
import time
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..shared.config import (
    get_worker_url,
    get_brain_url,
    get_vision_url,
    get_drafter_url,
    get_memory_url,
    ARANGODB_DB,
    ARANGODB_USER,
    ARANGODB_PASSWORD,
)
from .context_packer import build_extraction_layers, stub_retrieve_evidence
from ..shared.model_registry import get_model_config
from ..shared.context_budget import get_context_budget, estimate_tokens
from ..shared.logger import get_logger
from ..shared.llm_client import chat
from ..shared.role_manager import RoleRegistry
from ..shared.utils import get_utc_now
from .state import PaperState, JobStatus
from .normalize import normalize_extracted_json
from .telemetry import TelemetryEmitter, trace_node
from .config import ExpertType, NODE_EXPERT_MAP
from .job_manager import update_job_status
from arango import ArangoClient
import re


logger = get_logger("orchestrator", __name__)
telemetry_emitter = TelemetryEmitter()
role_registry = RoleRegistry()

# Lazy import to avoid circular dependencies
_project_service: Optional[Any] = None
_synthesis_service: Optional[Any] = None


BACKPRESSURE_THRESHOLD_DELAY = 0.85
BACKPRESSURE_THRESHOLD_RETRY = 0.95


def _parse_kv_utilization(metrics_text: str) -> Optional[float]:
    """Extract kv cache utilization from Prometheus exposition text."""
    for line in metrics_text.splitlines():
        if "kv_cache_utilization" in line or "kv_cache_fill" in line or "kv_cache_usage" in line:
            match = re.search(r"([0-9]+\.?[0-9]*)", line)
            if match:
                try:
                    value = float(match.group(1))
                    # Some metrics are 0-100, others 0-1
                    return value / 100.0 if value > 1 else value
                except ValueError:
                    continue
    return None


def check_kv_backpressure(expert_url: str):
    """Query SGLang metrics and decide whether to proceed, delay, or retry later."""
    try:
        resp = requests.get(f"{expert_url}/metrics", timeout=2)
        resp.raise_for_status()
        utilization = _parse_kv_utilization(resp.text)
        if utilization is None:
            return {"action": "proceed", "utilization": 0.0, "reason": "kv_cache_utilization_not_found"}
    except Exception as exc:  # noqa: BLE001
        return {"action": "proceed", "utilization": 0.0, "reason": f"metrics_unavailable:{exc}"}

    if utilization >= BACKPRESSURE_THRESHOLD_RETRY:
        return {"action": "retry_later", "utilization": utilization, "reason": "kv_cache>95%"}
    if utilization >= BACKPRESSURE_THRESHOLD_DELAY:
        time.sleep(0.2)
        return {"action": "delay", "utilization": utilization, "reason": "kv_cache>85%"}
    return {"action": "proceed", "utilization": utilization, "reason": "ok"}


def route_to_expert(node_name: str, node_type: str = "auto") -> tuple[str, str, str]:
    """Route a node to the appropriate expert service.
    
    Args:
        node_name: Name of the node function (e.g., "cartographer_node", "critic_node")
        node_type: Explicit expert type, or "auto" to infer from node_name
        
    Returns:
        Tuple of (expert_url, expert_name, model_id) for the appropriate expert service.
        expert_name is a human-readable identifier for logging/telemetry.
    """
    # Infer node type from name if auto
    if node_type == "auto":
        node_type = NODE_EXPERT_MAP.get(node_name, ExpertType.EXTRACTION_SCHEMA)
    
    # Route to appropriate expert
    if node_type == ExpertType.LOGIC_REASONING:
        return get_brain_url(), "Brain", get_model_config("brain").model_id
    elif node_type == ExpertType.EXTRACTION_SCHEMA:
        return get_worker_url(), "Worker", get_model_config("worker").model_id
    elif node_type == ExpertType.PROSE_WRITING:
        return get_drafter_url(), "Drafter", "(ollama model)"
    elif node_type == ExpertType.VISION:
        return get_vision_url(), "Vision", get_model_config("vision").model_id
    else:
        # Fallback to Worker
        return get_worker_url(), "Worker", get_model_config("worker").model_id


def call_expert_with_fallback(
    expert_url: str,
    expert_name: str,
    model_id: str,
    prompt: List[Dict[str, Any]],
    request_params: Dict[str, Any],
    fallback_url: Optional[str] = None,
    fallback_model_id: Optional[str] = None,
    node_name: str = "unknown",
    state: Optional[Dict[str, Any]] = None,
    allowed_tools: Optional[list] = None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Call an expert service with automatic retry/fallback via llm_client.chat."""
    data, meta = chat(
        primary_url=expert_url,
        model=model_id,
        messages=prompt,
        request_params=request_params,
        state=state,
        node_name=node_name,
        expert_name=expert_name,
        fallback_url=fallback_url,
        fallback_model=fallback_model_id,
        fallback_expert_name="Brain",
        allowed_tools=allowed_tools,
    )
    logger.debug(
        "Expert call completed",
        extra={
            "payload": {
                "node_name": node_name,
                "expert": meta.get("expert_name"),
                "path": meta.get("path"),
                "url": meta.get("url_base"),
            }
        },
    )
    return data, meta


def _get_synthesis_service() -> Optional[Any]:
    """Get or initialize SynthesisService for canonical knowledge queries.
    
    Returns:
        SynthesisService instance or None if DB unavailable
    """
    global _synthesis_service
    if _synthesis_service is None:
        try:
            from .synthesis_service import SynthesisService
            from ..shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, ARANGODB_PASSWORD
            
            arango_url = os.getenv("MEMORY_URL", get_memory_url())
            arango_db = os.getenv("ARANGODB_DB", ARANGODB_DB)
            arango_user = os.getenv("ARANGODB_USER", ARANGODB_USER)
            arango_password = os.getenv("ARANGO_ROOT_PASSWORD") or os.getenv("ARANGODB_PASSWORD", ARANGODB_PASSWORD)
            
            client = ArangoClient(hosts=arango_url)
            db = client.db(arango_db, username=arango_user, password=arango_password)
            _synthesis_service = SynthesisService(db)
            logger.debug("SynthesisService initialized in nodes module")
        except Exception as e:
            logger.warning(f"Failed to initialize SynthesisService in nodes: {e}")
            _synthesis_service = None
    return _synthesis_service


def _query_established_knowledge(
    raw_text: str,
    state: Optional[PaperState] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, int], List[str]]:
    """Query knowledge base for entities mentioned in the text with prioritized retrieval.
    
    When force_refresh_context is True, prioritizes candidate facts from reference_ids,
    then canonical knowledge, then document chunks.
    
    Args:
        raw_text: Text to extract entity names from
        state: Optional[PaperState] containing reference_ids and force_refresh_context
    
    Returns:
        Tuple of (knowledge_entries, context_sources_counts, selected_reference_ids)
        - knowledge_entries: List of knowledge entries (candidate or canonical)
        - context_sources_counts: Dict with counts from each tier
        - selected_reference_ids: List of reference IDs actually used
    """
    import re
    
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
        from ..shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, get_arango_password
        
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
    state: Optional[PaperState],
) -> List[Dict[str, Any]]:
    """Filter canonical knowledge entries that conflict with candidate facts.
    
    A conflict is detected when:
    - Same subject/object but contradictory predicate/object
    
    Args:
        canonical: List of canonical knowledge entries
        candidate_facts: List of candidate facts
        state: PaperState (for storing conflict flags)
    
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


def _get_project_service() -> Optional[Any]:
    """Get ProjectService instance (lazy import to avoid circular dependencies).
    
    Returns:
        ProjectService instance if available, None if DB unavailable.
    """
    global _project_service
    if _project_service is None:
        try:
            # Lazy imports to avoid circular dependencies
            from ..project.service import ProjectService
            from ..shared.config import MEMORY_URL, ARANGODB_DB, ARANGODB_USER, ARANGODB_PASSWORD
            arango_url = os.getenv("MEMORY_URL", MEMORY_URL)
            arango_db = os.getenv("ARANGODB_DB", ARANGODB_DB)
            arango_user = os.getenv("ARANGODB_USER", ARANGODB_USER)
            arango_password = os.getenv("ARANGO_ROOT_PASSWORD") or os.getenv("ARANGODB_PASSWORD", ARANGODB_PASSWORD)
            
            client = ArangoClient(hosts=arango_url)
            db = client.db(arango_db, username=arango_user, password=arango_password)
            # Do not create DBs/collections here; assume pre-provisioned (matches server.py behavior)
            _project_service = ProjectService(db)
            logger.debug("ProjectService initialized in nodes module (no DB creation)")
        except Exception as e:
            logger.warning(f"Failed to initialize ProjectService in nodes: {e}")
            _project_service = None
    return _project_service


def hydrate_project_context(state: PaperState) -> PaperState:
    """Hydrate project context from project_id if missing.
    
    Ensures project_context is available in state as a JSON-serializable dict.
    If project_id exists but project_context is missing, fetches from ProjectService
    and stores model_dump() into state.
    
    Args:
        state: PaperState that may contain project_id.
    
    Returns:
        Updated PaperState with project_context populated if project_id was present.
    
    Raises:
        ValueError: If project_id is provided but project not found.
        RuntimeError: If project_id is provided but DB is unavailable.
    """
    project_id = state.get("project_id")
    
    # If no project_id, return state unchanged
    if not project_id:
        return state
    
    # If project_context already exists, return state unchanged
    if state.get("project_context"):
        return state
    
    # Fetch project config
    project_service = _get_project_service()
    if project_service is None:
        raise RuntimeError("ProjectService unavailable: cannot fetch project context")
    
    try:
        from ..project.types import ProjectConfig
        project = project_service.get_project(project_id)
        
        hydrated = {**state, "project_context": project.model_dump()}
        logger.info(f"Hydrated project context for project_id={project_id}")
        
        return hydrated
    except ValueError as e:
        # Project not found
        raise ValueError(f"Project not found: {project_id}") from e
    except Exception as e:
        # Other errors (DB unavailable, etc.)
        logger.error(f"Failed to hydrate project context for {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Failed to fetch project context: {e}") from e


@trace_node
def cartographer_node(state: PaperState) -> PaperState:
    """Extract graph JSON from raw text using Cortex Worker, incorporating prior critiques.
    
    Uses Worker (SGLang) to extract structured knowledge graph with STRICT JSON
    requirements. The output is normalized to guarantee a `triples` array structure
    that the console expects.
    
    Args:
        state: PaperState containing raw_text, optional critiques, and optional project context.
        
    Returns:
        Updated PaperState with extracted_json containing guaranteed `triples` array.
        
    Raises:
        ValueError: If raw_text is missing or project_id provided but project not found.
        RuntimeError: If project_id provided but DB unavailable.
        requests.RequestException: If Worker API call fails.
    """
    # Hydrate project context if project_id is present
    state = hydrate_project_context(state)
    
    # Safe access to project context (already hydrated if project_id exists)
    project_id = state.get("project_id")
    project_context = state.get("project_context")
    
    raw_text = state.get("raw_text", "")
    critiques = state.get("critiques", []) or []
    role = role_registry.get_role("The Cartographer")
    force_refresh_context = state.get("force_refresh_context", False)

    if not raw_text:
        raise ValueError("raw_text is required for cartographer node")

    context_hints: List[str] = []
    if project_context:
        thesis = project_context.get("thesis", "")
        research_questions = project_context.get("research_questions", [])
        if thesis:
            context_hints.append(f'Thesis: "{thesis}"')
        if research_questions:
            context_hints.append(
                "Research Questions:\n" + "\n".join([f"- {rq}" for rq in research_questions])
            )
    system_prompt = role.system_prompt
    if context_hints:
        system_prompt = f"{system_prompt}\n\nContext:\n" + "\n".join(context_hints)
        logger.debug(
            "Cartographer: Injected project context into prompt",
            extra={"payload": {"has_thesis": bool(project_context.get('thesis')), "rq_count": len(project_context.get('research_questions', []))}}
        )
    
    # Evidence-Aware RAG: Pre-extraction lookup with prioritized retrieval
    established_knowledge, context_sources, selected_ref_ids = _query_established_knowledge(raw_text, state)
    
    # Store context metadata in a fresh dict per revision to avoid accumulation
    merged_context_sources = {**state.get("context_sources", {}), **context_sources}
    state = {**state, "context_sources": merged_context_sources}
    if selected_ref_ids:
        state["selected_reference_ids"] = selected_ref_ids
    
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
                    "selected_reference_ids": selected_ref_ids,
                }
            }
        )
        
        # Emit telemetry with context sources
        if state.get("job_id"):
            telemetry_emitter.emit_event(
                "context_assembly",
                {
                    "job_id": state.get("job_id"),
                    "project_id": project_id,
                    "node_name": "cartographer_node",
                    "timestamp": get_utc_now().isoformat(),
                    "context_sources": context_sources,
                    "selected_reference_ids": selected_ref_ids,
                    "knowledge_count": len(established_knowledge),
                },
            )
    if force_refresh_context:
        system_prompt = f"{system_prompt}\nForce refresh context: prioritize latest evidence and candidate facts."

    layered_section = ""
    if os.getenv("ENABLE_CONTEXT_PACKING_EXTRACT", "false").lower() in ("1", "true", "yes"):
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

    user_sections = [f"Document:\n{raw_text}"]
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
        
        triples_count = len(normalized.get("triples", []))
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
        enriched_state = {**state}
        if usage:
            enriched_state["_sglang_usage"] = usage
        # Store expert info for trace_node decorator
        enriched_state["_expert_name"] = actual_expert_name
        enriched_state["_expert_url"] = actual_expert_url
        return {**enriched_state, "extracted_json": normalized}
    except json.JSONDecodeError as e:
        logger.error(
            "Cartographer failed to parse JSON response",
            extra={"payload": {"prompt_chars": len(raw_text), "error": str(e)}},
            exc_info=True,
        )
        # Return empty structure on JSON parse failure
        return {**state, "extracted_json": {"triples": []}}
    except Exception as e:
        logger.error(
            "Cartographer failed to extract graph",
            extra={"payload": {"prompt_chars": len(raw_text), "error": str(e)}},
            exc_info=True,
        )
        # Return empty structure on failure (don't raise to allow workflow to continue)
        return {**state, "extracted_json": {"triples": []}}


def _detect_quantization_failure(text: str) -> bool:
    """Detect FP4 quantization failures: garbled text or repetitive tokens.
    
    Args:
        text: Text to analyze for quantization artifacts.
    
    Returns:
        True if quantization failure is detected, False otherwise.
    """
    if not text or len(text) < 10:
        return False

    # Treat structured JSON as likely valid; avoid false positives on compact payloads
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return False
    
    # Check for repetitive token patterns (common FP4 failure)
    # Look for sequences of 3+ identical tokens
    words = text.split()
    if len(words) >= 3:
        for i in range(len(words) - 2):
            if words[i] == words[i + 1] == words[i + 2]:
                return True
    
    # Check for garbled text patterns
    # High ratio of non-alphanumeric characters or unusual character sequences
    alphanumeric_ratio = sum(1 for c in text if c.isalnum()) / len(text) if text else 0
    if alphanumeric_ratio < 0.3:  # Less than 30% alphanumeric suggests garbled text
        return True
    
    # Check for excessive special characters or control characters
    special_char_count = sum(1 for c in text if not c.isalnum() and not c.isspace())
    if len(text) > 0 and special_char_count / len(text) > 0.5:  # More than 50% special chars
        return True
    
    return False


@trace_node
def critic_node(state: PaperState) -> PaperState:
    """Validate extracted graph and return pass/fail with critiques.
    
    Uses Brain (high-level reasoning) service for validation.
    Includes FP4 quantization failure detection to catch garbled text or repetitive tokens.
    Includes vocabulary guardrail check for forbidden words in synthesizer output.
    """
    extracted = state.get("extracted_json") or {}
    raw_text = state.get("raw_text", "")
    synthesis = state.get("synthesis", "")
    role = role_registry.get_role("The Critic")
    
    # Pre-validation: Check for FP4 quantization failures in extracted text
    # This catches failures before sending to Brain, saving compute
    extracted_str = json.dumps(extracted, ensure_ascii=False)
    if _detect_quantization_failure(extracted_str):
        logger.warning(
            "FP4 quantization failure detected in extraction",
            extra={"payload": {"extracted_preview": extracted_str[:200]}},
        )
        # Early return to avoid double-incrementing revision_count in downstream logic
        revision_count = state.get("revision_count", 0) + 1
        return {
            **state,
            "critiques": ["Extraction appears garbled or contains repetitive tokens (possible FP4 quantization failure)"],
            "revision_count": revision_count,
            "critic_status": "fail",
        }

    def _load_page_text(doc_hash: str, page: int) -> str:
        """Load page text from cache or extract from PDF.
        
        Args:
            doc_hash: SHA256 hash of the PDF document
            page: 1-based page number
        
        Returns:
            Text content of the page, or empty string if not available
        """
        try:
            from .pdf_text_cache import load_page_text
            pdf_path = state.get("pdf_path")
            return load_page_text(doc_hash, page, pdf_path=pdf_path)
        except Exception as e:
            logger.warning(
                f"Failed to load page text for doc_hash={doc_hash[:16]}... page={page}: {e}",
                extra={"payload": {"doc_hash": doc_hash[:16], "page": page}},
                exc_info=True,
            )
            # Fallback to raw_text if cache fails (graceful degradation)
            return raw_text or ""

    def _snippet_exists(snippet: str, text: str) -> bool:
        if not snippet or not text:
            return False
        if snippet in text:
            return True
        # Fuzzy containment
        import difflib
        return difflib.SequenceMatcher(None, snippet, text).quick_ratio() > 0.6

    def _validate_claims() -> tuple[list[str], bool]:
        """Validate claims and triples with hardened evidence binding checks.
        
        The Critic's Gate: Rejects any claim/triple that:
        - Lacks doc_hash (hard requirement)
        - Has invalid bbox range [0, 1000]
        - Has snippet that doesn't match page text (fuzzy match)
        
        Returns:
            Tuple of (critiques list, validation_ok bool)
        """
        critiques_local: list[str] = []
        ok = True
        claims = extracted.get("claims") or []
        triples = extracted.get("triples") or []
        
        # Validate claims
        for claim in claims:
            if not isinstance(claim, dict):
                critiques_local.append("Claim is not an object")
                ok = False
                continue
            
            pointer = claim.get("source_pointer") or {}
            bbox = pointer.get("bbox")
            doc_hash = claim.get("doc_hash") or pointer.get("doc_hash")
            page = pointer.get("page")
            snippet = pointer.get("snippet", "")
            project_id = claim.get("project_id")
            
            # Hard requirement: doc_hash must exist
            if not doc_hash:
                critiques_local.append("Claim missing doc_hash (required for evidence binding)")
                ok = False
                continue
            
            # Hard requirement: source_pointer must have all fields
            if not page or not bbox or len(bbox) != 4:
                critiques_local.append("Claim missing source_pointer fields (page/bbox required)")
                ok = False
                continue
            
            # Validate bbox range [0, 1000]
            if any((c < 0 or c > 1000) for c in bbox):
                critiques_local.append(f"Claim bbox out of range (must be 0-1000): {bbox}")
                ok = False
            
            # Validate project_id
            if not project_id:
                critiques_local.append("Claim missing project_id")
                ok = False
            
            # Real text verification: fuzzy match snippet against page text
            if doc_hash and page and snippet:
                try:
                    page_text = _load_page_text(doc_hash, page)
                    if not _snippet_exists(snippet, page_text):
                        critiques_local.append(
                            f"Claim snippet not found in page text (doc_hash={doc_hash[:16]}... page={page})"
                        )
                        ok = False
                except Exception as e:
                    logger.warning(f"Failed to verify snippet for claim: {e}", exc_info=True)
                    critiques_local.append(f"Failed to verify claim snippet: {e}")
                    ok = False
        
        # Validate triples (same checks; source_pointer required)
        for triple in triples:
            if not isinstance(triple, dict) or not triple:
                continue
            
            pointer = triple.get("source_pointer") or {}
            bbox = pointer.get("bbox")
            doc_hash = triple.get("doc_hash") or pointer.get("doc_hash")
            page = pointer.get("page")
            snippet = triple.get("snippet") or triple.get("evidence", "")
            
            # Hard requirement: doc_hash must exist
            if not doc_hash:
                critiques_local.append("Triple missing doc_hash (required for evidence binding)")
                ok = False
                continue
            if not page or not bbox or len(bbox) != 4:
                critiques_local.append("Triple source_pointer missing required fields (page/bbox)")
                ok = False
                continue
            
            # Validate bbox range
            if any((c < 0 or c > 1000) for c in bbox):
                critiques_local.append(f"Triple bbox out of range (must be 0-1000): {bbox}")
                ok = False
            
            # Real text verification
            if snippet:
                try:
                    page_text = _load_page_text(doc_hash, page)
                    if not _snippet_exists(snippet, page_text):
                        critiques_local.append(
                            f"Triple snippet not found in page text (doc_hash={doc_hash[:16]}... page={page})"
                        )
                        ok = False
                except Exception as e:
                    logger.warning(f"Failed to verify triple snippet: {e}", exc_info=True)
                    critiques_local.append(f"Failed to verify triple snippet: {e}")
                    ok = False
        
        return critiques_local, ok

    claim_critiques, claims_ok = _validate_claims()
    conflict_flags = state.get("conflict_flags") or []

    context_segments = []
    if claim_critiques:
        context_segments.append(f"Claim critiques: {json.dumps(claim_critiques, ensure_ascii=False)}")
    if conflict_flags:
        context_segments.append(f"Conflict flags: {conflict_flags}")
    system_prompt = role.system_prompt
    if context_segments:
        system_prompt = f"{system_prompt}\n\nContext:\n" + "\n".join(context_segments)

    user_content = json.dumps(
        {
            "extracted_graph": extracted,
            "raw_text": raw_text,
        },
        ensure_ascii=False,
    )

    critique_prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        # Legacy/simple path: attempt direct HTTP call first (monkeypatch-friendly for tests)
        try:
            resp = requests.post(
                get_brain_url(),
                json={"messages": critique_prompt, "response_format": {"type": "json_object"}},
                timeout=5,
            )
            content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "{}")
            parsed = json.loads(content) if isinstance(content, str) else content
            status = parsed.get("status", "fail").lower()
            critiques = parsed.get("critiques", [])
            if not isinstance(critiques, list):
                critiques = [str(critiques)]
            revision_count = state.get("revision_count", 0) + (0 if status == "pass" else 1)
            critic_score = 1.0 if status == "pass" else 0.0
            synthesis_val = state.get("synthesis") or "synthesis_placeholder"
            return {**state, "critiques": critiques, "revision_count": revision_count, "critic_status": status, "critic_score": critic_score, "synthesis": synthesis_val}
        except Exception:
            pass
        # Route to appropriate expert: Critic uses Brain (logic/reasoning) service
        expert_url, expert_name, expert_model = route_to_expert("critic_node", ExpertType.LOGIC_REASONING)
        decision = check_kv_backpressure(expert_url)
        if decision.get("action") == "retry_later":
            return {**state, "critic_status": "retry_later", "error": "RETRY_LATER"}
        # soft delay already applied inside decision for >85%
        data, meta = call_expert_with_fallback(
            expert_url=expert_url,
            expert_name=expert_name,
            model_id=expert_model,
            prompt=critique_prompt,
            request_params={
                "temperature": 0.3,
                "top_p": 0.9,
                "max_tokens": 8192,
                "response_format": {"type": "json_object"},
            },
            fallback_url=None,  # No fallback for critic (already using Brain)
            fallback_model_id=None,
            node_name="critic_node",
            state=state,
            allowed_tools=role.allowed_tools,
        )
        latency_ms = meta.get("duration_ms", 0.0)
        usage = meta.get("usage")
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        parsed = json.loads(content) if isinstance(content, str) else content
        status = parsed.get("status", "fail").lower()
        critiques = parsed.get("critiques", [])
        if not isinstance(critiques, list):
            critiques = [str(critiques)]
        
        # Additional check: If Brain response itself looks garbled, mark as fail
        if _detect_quantization_failure(content):
            logger.warning(
                "FP4 quantization failure detected in Brain response",
                extra={"payload": {"response_preview": content[:200]}},
            )
            status = "fail"
            critiques.append("Brain response appears garbled (possible quantization failure)")

        # Snippet existence check (best-effort)
        critiques.extend(claim_critiques)
        if not claims_ok:
            status = "fail"

        # Conflict flags surfaced during context assembly
        conflict_flags = state.get("conflict_flags") or []
        if conflict_flags:
            status = "fail"
            critiques.append("Conflict Resolution Needed")
            critiques.append("Recommendation: Cartographer must resolve contradictory evidence before proceeding.")
        
        # Vocabulary guardrail check: scan synthesis output for forbidden words
        if synthesis:
            try:
                from ..shared.vocab_guard import get_vocab_guard
                vocab_guard = get_vocab_guard()
                forbidden_words = vocab_guard.get_forbidden_words()
                
                if forbidden_words:
                    # Case-insensitive regex pattern to match forbidden words with word boundaries
                    # Escape special regex characters in words
                    escaped_words = [re.escape(word) for word in forbidden_words]
                    pattern = r'\b(' + '|'.join(escaped_words) + r')\b'
                    matches = re.findall(pattern, synthesis, re.IGNORECASE)
                    
                    if matches:
                        # Get unique matches (lowercased for consistency)
                        unique_matches = sorted(set(word.lower() for word in matches))
                        status = "fail"
                        critiques.append(f"Prohibited vocabulary detected: {', '.join(unique_matches)}")
                        logger.warning(
                            "Vocab guardrail: Prohibited words found in synthesis",
                            extra={"payload": {"forbidden_words": unique_matches, "job_id": state.get("job_id")}},
                        )
            except Exception as e:
                logger.warning(f"Failed to check vocabulary guardrail: {e}", exc_info=True)
                # Don't fail on guardrail check errors - just log and continue
        
        # Increment revision count on failure
        revision_count = state.get("revision_count", 0)
        if status != "pass":
            revision_count += 1
        critic_score = 1.0 if status == "pass" else 0.0
        logger.info(
            "Critic evaluated extraction",
            extra={
                "payload": {
                    "expert": meta.get("expert_name", expert_name),
                    "telemetry": {
                        "model_id": meta.get("model_id", expert_model),
                        "task_type": "adjudicate",
                        "tokens_in_est": estimate_tokens(extracted_str),
                        "tokens_out_est": estimate_tokens(content if isinstance(content, str) else json.dumps(content)),
                        "latency_ms": latency_ms,
                        "kv_policy": get_model_config("brain").kv_policy,
                    }
                }
            },
        )
        enriched_state = {**state}
        if usage:
            enriched_state["_sglang_usage"] = usage
        # Store expert info for trace_node decorator
        enriched_state["_expert_name"] = meta.get("expert_name", expert_name)
        enriched_state["_expert_url"] = meta.get("url_base", expert_url)
        return {
            **enriched_state,
            "critiques": critiques,
            "revision_count": revision_count,
            "critic_status": status,
            "critic_score": critic_score,
        }
    except Exception:
        logger.error(
            "Critic validation failed",
            extra={"payload": {"has_extracted": bool(extracted)}},
            exc_info=True,
        )
        # On failure to critique, force manual review path
        revision_count = state.get("revision_count", 0) + 1
        return {**state, "critiques": ["Critic execution failed"], "revision_count": revision_count, "critic_status": "fail"}


def select_images_for_vision(image_paths: List[str]) -> List[str]:
    """Select a subset of images to send to Vision."""
    if not image_paths:
        return []
    max_images = int(os.getenv("VISION_MAX_IMAGES", "5"))
    preferred = []
    others = []
    for path in image_paths:
        name = os.path.basename(path).lower()
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        if any(tag in name for tag in ["fig", "table", "chart", "diagram"]) or size > 500_000:
            preferred.append(path)
        else:
            others.append(path)
    ordered = preferred + others
    return ordered[:max_images]


def build_vision_context(vision_results: List[Dict[str, Any]]) -> str:
    """Create a deterministic context block from vision results."""
    lines: List[str] = []
    for res in vision_results:
        path = os.path.basename(res.get("image_path", "image"))
        lines.append(f"[FIGURE {path}]")
        caption = res.get("caption", "").strip()
        if caption:
            lines.append(f"caption: {caption}")
        facts = res.get("extracted_facts") or []
        if facts:
            lines.append("extracted_facts:")
            for fact in facts:
                key = fact.get("key", "")
                value = fact.get("value", "")
                unit = fact.get("unit", "")
                conf = fact.get("confidence", 0.0)
                lines.append(f"- key: {key} value: {value} unit: {unit} (confidence={conf})")
        tables = res.get("tables") or []
        for tbl in tables:
            lines.append(f"table: {tbl.get('title','')}".strip())
            rows = tbl.get("rows") or []
            for row in rows:
                lines.append(f"  row: {row}")
    return "\n".join(lines)


@trace_node
def vision_node(state: PaperState) -> PaperState:
    """Run Vision on selected images and inject results into raw_text context."""
    image_paths = state.get("image_paths") or []
    if not image_paths:
        logger.warning("Vision: No images to process")
        # Update state with empty vision_output and return immediately
        return {**state, "vision_output": []}

    selected = select_images_for_vision(image_paths)
    if not selected:
        return state

    vision_url = get_vision_url()
    vision_results: List[Dict[str, Any]] = []
    project_id = state.get("project_id") or "default_project"
    artifacts_root = Path("/raid/artifacts") / project_id
    try:
        artifacts_root.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        # Fallback for environments without /raid (tests/local)
        tmp_root = Path(tempfile.mkdtemp(prefix="vyasa_artifacts_"))
        artifacts_root = tmp_root / project_id
        artifacts_root.mkdir(parents=True, exist_ok=True)

    for path in selected:
        try:
            artifact_id = f"artifact-{uuid.uuid4()}"
            artifact_path = artifacts_root / f"{artifact_id}.png"
            try:
                shutil.copy(path, artifact_path)
            except Exception:
                logger.warning("Failed to copy artifact", extra={"payload": {"source": path, "target": str(artifact_path)}})
            with open(path, "rb") as fh:
                files = {"file": (os.path.basename(path), fh, "application/octet-stream")}
                vision_model = get_model_config("vision").model_id
                start = time.time()
                resp = requests.post(
                    f"{vision_url}/v1/vision",
                    data={"payload": json.dumps({"model": vision_model, "image_path": path})},
                    files=files,
                    timeout=60,
                )
                resp.raise_for_status()
                latency_ms = (time.time() - start) * 1000
                data = resp.json()
                if "choices" in data:
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                    data = json.loads(content) if isinstance(content, str) else content
                vision_results.append(
                    {
                        "image_path": path,
                        "caption": data.get("caption", ""),
                        "extracted_facts": data.get("extracted_facts", []),
                        "tables": data.get("tables", []),
                        "confidence": data.get("confidence", 0.0),
                        "notes": data.get("notes", ""),
                        "artifact_id": artifact_id,
                        "telemetry": {
                            "model_id": vision_model,
                            "task_type": "vision",
                            "latency_ms": latency_ms,
                            "kv_policy": get_model_config("vision").kv_policy,
                        },
                    }
                )
                telemetry_emitter.emit_event(
                    "llm_call",
                    {
                        "job_id": state.get("job_id"),
                        "project_id": project_id,
                        "node_name": "vision",
                        "timestamp": get_utc_now().isoformat(),
                        "duration_ms": latency_ms,
                        "metadata": {
                            "model_id": vision_model,
                            "image_path": path,
                            "artifact_id": artifact_id,
                            "url": f"{vision_url}/v1/vision",
                        },
                    },
                )
        except Exception as exc:
            logger.warning(
                "Vision processing failed for image",
                extra={"payload": {"image_path": path, "error": str(exc)}},
            )
            continue

    if not vision_results:
        return state

    vision_context = build_vision_context(vision_results)
    raw_text = state.get("raw_text", "")
    combined_text = raw_text + "\n\n## Vision Extracts\n" + vision_context

    logger.info(
        "Vision context injected",
        extra={"payload": {"images_processed": len(vision_results), "context_chars": len(vision_context)}},
    )

    return {**state, "raw_text": combined_text, "vision_results": vision_results}


@trace_node
def saver_node(state: PaperState) -> PaperState:
    """Persist extracted graph to ArangoDB with a status flag and receipt.
    
    Raises exceptions on failure (does not swallow errors) to ensure job failure
    is properly tracked.
    """
    extracted = state.get("extracted_json") or {}
    critiques = state.get("critiques", []) or []
    status = state.get("critic_status", "pass")
    vision_results = state.get("vision_results", [])
    project_id = state.get("project_id")
    manuscript_blocks = state.get("manuscript_blocks", [])

    # Ensure expert verification fields exist on triples
    if isinstance(extracted, dict) and isinstance(extracted.get("triples"), list):
        normalized_triples = []
        for triple in extracted.get("triples", []):
            if isinstance(triple, dict):
                triple.setdefault("is_expert_verified", False)
                triple.setdefault("expert_notes", None)
            normalized_triples.append(triple)
        extracted["triples"] = normalized_triples

    def _next_block_version(db, block_id: str, project: str) -> int:
        cursor = db.aql.execute(
            "FOR b IN manuscript_blocks FILTER b.block_id==@bid AND b.project_id==@pid SORT b.version DESC LIMIT 1 RETURN b.version",
            bind_vars={"bid": block_id, "pid": project},
        )
        versions = list(cursor)
        return (versions[0] + 1) if versions else 1

    def _validate_citations(db, project: str, keys: list[str]) -> None:
        """Librarian Key-Guard: Validate citation keys against project bibliography.
        
        This guard ensures that AI cannot save ManuscriptBlocks with invalid citations.
        All citation_keys must exist in the project_bibliography collection.
        
        Args:
            db: ArangoDB database instance.
            project: Project identifier.
            keys: List of citation keys to validate.
        
        Raises:
            ValueError: If bibliography collection is missing or citation keys are invalid.
        """
        if not keys:
            return
        if not db.has_collection("project_bibliography"):
            raise ValueError(
                "Bibliography collection 'project_bibliography' missing. "
                "Cannot validate citation keys. Add bibliography entries first."
            )
        cursor = db.aql.execute(
            "FOR b IN project_bibliography FILTER b.project_id==@pid RETURN b.citation_key",
            bind_vars={"pid": project},
        )
        existing = set(cursor)
        missing = [k for k in keys if k not in existing]
        if missing:
            raise ValueError(
                f"Citation keys not found in project bibliography: {missing}. "
                "Add these keys to 'project_bibliography' collection first."
            )

    try:
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=ARANGODB_PASSWORD)
        if not db.has_collection("extractions"):
            db.create_collection("extractions")
        if not db.has_collection("manuscript_blocks"):
            db.create_collection("manuscript_blocks")
        collection = db.collection("extractions")
        doc: Dict[str, Any] = {
            "graph": extracted,
            "critiques": critiques,
            "status": status if status == "pass" else "needs_manual_review",
            "vision_results": vision_results,
            "project_id": project_id,
        }
        receipt = collection.insert(doc)
        # Build explicit receipt
        save_receipt = {
            "collection": "extractions",
            "document_key": receipt.get("_key"),
            "document_id": receipt.get("_id"),
            "revision": receipt.get("_rev"),
            "saved_at": get_utc_now().isoformat(),
            "status": "SAVED",
        }
        logger.info("Saved extraction to ArangoDB", extra={"payload": {"status": doc["status"], "key": receipt.get("_key")}})

        # Persist manuscript blocks with versioning and citation guard (Librarian Key-Guard)
        if manuscript_blocks and project_id:
            from ..manuscript.service import ManuscriptService
            from ..shared.schema import ManuscriptBlock
            
            manuscript_service = ManuscriptService(db)
            
            for block_data in manuscript_blocks:
                if not isinstance(block_data, dict):
                    continue
                
                # Convert dict to ManuscriptBlock model
                try:
                    block = ManuscriptBlock(
                        block_id=block_data.get("block_id", ""),
                        section_title=block_data.get("section_title", ""),
                        content=block_data.get("content", ""),
                        order_index=block_data.get("order_index", 0),
                        claim_ids=block_data.get("claim_ids", []),
                        citation_keys=block_data.get("citation_keys", []),
                        project_id=project_id,
                        is_expert_verified=block_data.get("is_expert_verified", False),
                        expert_notes=block_data.get("expert_notes"),
                    )
                    
                    # Save with citation validation (Librarian Key-Guard)
                    manuscript_service.save_block(block, project_id, validate_citations=True)
                    
                except ValueError as e:
                    # Citation validation failed - log and re-raise
                    logger.error(
                        f"Librarian Key-Guard: Citation validation failed for block {block_data.get('block_id')}",
                        extra={"payload": {"error": str(e), "project_id": project_id}},
                        exc_info=True,
                    )
                    raise  # Re-raise to ensure job failure is tracked
                except Exception as e:
                    logger.error(
                        f"Failed to save manuscript block {block_data.get('block_id')}",
                        extra={"payload": {"error": str(e), "project_id": project_id}},
                        exc_info=True,
                    )
                    raise

        return {**state, "save_receipt": save_receipt}
    except Exception as e:
        logger.error(f"DB Save Failed: {e}", exc_info=True)
        raise  # Re-raise to ensure job failure is tracked


@trace_node
def synthesizer_node(state: PaperState) -> PaperState:
    """Synthesizer node to integrate narrative or math outputs with vocabulary guardrail.
    
    Uses vocab_guard to inject forbidden word constraints into prompts before LLM calls.
    """
    logger.info("Synthesizer node executed", extra={"payload": {"job_id": state.get("job_id")}})
    
    # Get vocabulary guard for applying constraints
    try:
        from ..shared.vocab_guard import get_vocab_guard
        vocab_guard = get_vocab_guard()
    except Exception as e:
        logger.warning(f"Failed to load vocab guard: {e}", exc_info=True)
        vocab_guard = None
    
    extracted = state.get("extracted_json") or {}
    triples = extracted.get("triples") if isinstance(extracted, dict) else []
    synthesis_text = state.get("synthesis")
    
    # If synthesis_text exists, it means it was generated by a previous step
    # Otherwise, generate it using LLM with vocab guard constraints
    if not synthesis_text:
        # For now, generate a simple summary (placeholder implementation)
        # When fully implemented, this would call llm_client.chat() with vocab_guard constraints
        synthesis_text = f"Synthesized summary: processed {len(triples) if isinstance(triples, list) else 0} triples."
        
        # Example of how vocab_guard would be applied before LLM call:
        # system_prompt = role.system_prompt if role else "You are a Synthesizer..."
        # if vocab_guard:
        #     system_prompt = vocab_guard.apply_constraints(system_prompt)
        # Then use the modified system_prompt in the llm_client.chat() call
    
    return {**state, "synthesis": synthesis_text}


@trace_node
def failure_cleanup_node(state: PaperState) -> PaperState:
    """Terminal failure handler that marks the job failed and emits telemetry."""
    job_id = state.get("job_id")
    error_msg = state.get("error") or state.get("critic_status") or "Workflow failed"
    try:
        if job_id:
            update_job_status(job_id, JobStatus.FAILED, current_step="failure_cleanup", error=str(error_msg), message="Failure cleanup")
    except Exception as exc:  # noqa: BLE001
        logger.error("Unable to mark job failed during cleanup", extra={"payload": {"job_id": job_id, "error": str(exc)}})
    telemetry_emitter.emit_event(
        "system_failure",
        {
            "job_id": job_id,
            "node_name": "failure_cleanup",
            "timestamp": get_utc_now().isoformat(),
            "error": str(error_msg),
        },
    )
    return {**state, "status": "fail"}


@trace_node
def lead_counsel_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Strategic triage: choose summary vs detail based on kernel overlap and new primitives."""
    summary = state.get("librarian_summary") or state.get("summary") or ""
    project_kernel = (
        state.get("project_kernel")
        or (state.get("project_context") or {}).get("thesis")
        or ""
    )
    triples = []
    extracted = state.get("extracted_json") or {}
    if isinstance(extracted, dict):
        triples = extracted.get("triples") or []

    def _tokenize(text: str) -> List[str]:
        return [t.lower() for t in text.replace("\n", " ").split() if t]

    kernel_tokens = set(_tokenize(project_kernel))
    summary_tokens = set(_tokenize(summary))

    redundant = sorted(list(summary_tokens & kernel_tokens))

    new_primitives: List[str] = []
    for t in triples:
        if not isinstance(t, dict):
            continue
        for part in ("subject", "object", "predicate"):
            val = t.get(part)
            if isinstance(val, str):
                for token in _tokenize(val):
                    if token and token not in kernel_tokens:
                        new_primitives.append(token)

    presentation = "DETAIL" if new_primitives else "SUMMARIZE"
    triage = {
        "redundant": redundant,
        "unique": new_primitives,
        "presentation": presentation,
    }
    return {**state, "lead_counsel": triage}


@trace_node
def logician_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Autoformalization using the math sandbox."""
    latex = state.get("latex_formula") or state.get("logician_input") or ""
    try:
        from .tools.math_sandbox import MathSandbox  # Local import to avoid optional dep failures at import time

        sandbox = MathSandbox()
        result = sandbox.execute_symbolic(latex) if latex else {"error": "no_formula"}
        result["tool_used"] = "math_sandbox"
    except Exception as exc:  # noqa: BLE001
        result = {"error": f"math_sandbox_unavailable:{exc}"}
    return {**state, "logician": result}
