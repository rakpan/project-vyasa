"""
Knowledge Sideloader API: Out-of-Band (OOB) Research Ingestion

Handles ingestion of external research content (Perplexity, web scraping, etc.)
into Vyasa's knowledge pipeline with proper guardrails to prevent pollution
of canonical knowledge.
"""

import json
import threading
import time
import uuid
import hashlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify

from arango import ArangoClient
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ...shared.schema import ExternalReference, CandidateFact
from ...shared.config import (
    get_memory_url,
    ARANGODB_DB,
    ARANGODB_USER,
    get_arango_password,
    get_worker_url,
    get_brain_url,
    OOB_PROMOTION_CONFIDENCE_THRESHOLD,
    OOB_REQUIRE_SOURCE_URL_FOR_AUTO_PROMOTION,
)
from ...shared.model_registry import get_model_config
from ...shared.logger import get_logger
from ..nodes import route_to_expert, call_expert_with_fallback, ExpertType
from ..telemetry import TelemetryEmitter, extract_usage_from_response
from ..normalize import normalize_extracted_json

logger = get_logger("orchestrator", __name__)
telemetry_emitter = TelemetryEmitter()

# Flask Blueprint for knowledge routes
knowledge_bp = Blueprint("knowledge", __name__, url_prefix="/api/knowledge")

# Collections
EXTERNAL_REFERENCES_COLLECTION = "external_references"
CANDIDATE_KNOWLEDGE_COLLECTION = "candidate_knowledge"
CANONICAL_KNOWLEDGE_COLLECTION = "canonical_knowledge"


def _get_db() -> Optional[StandardDatabase]:
    """Get ArangoDB database connection.
    
    Returns:
        StandardDatabase instance or None if connection fails.
    """
    try:
        arango_url = get_memory_url()
        arango_db = ARANGODB_DB
        arango_user = ARANGODB_USER
        arango_password = get_arango_password()
        
        client = ArangoClient(hosts=arango_url)
        db = client.db(arango_db, username=arango_user, password=arango_password)
        return db
    except Exception as e:
        logger.error(f"Failed to connect to ArangoDB: {e}", exc_info=True)
        return None


def _ensure_collections(db: StandardDatabase) -> None:
    """Ensure external_references and candidate_knowledge collections exist with indexes.
    
    Args:
        db: ArangoDB database instance
    """
    # Ensure external_references collection
    if not db.has_collection(EXTERNAL_REFERENCES_COLLECTION):
        db.create_collection(EXTERNAL_REFERENCES_COLLECTION)
        logger.info(f"Created collection: {EXTERNAL_REFERENCES_COLLECTION}")
    
    coll_refs = db.collection(EXTERNAL_REFERENCES_COLLECTION)
    try:
        coll_refs.ensure_persistent_index(["reference_id"], unique=True)
        coll_refs.ensure_persistent_index(["project_id"])
        coll_refs.ensure_persistent_index(["status"])
        coll_refs.ensure_persistent_index(["extracted_at"])
    except ArangoError:
        pass  # Indexes may already exist
    
    # Ensure candidate_knowledge collection
    if not db.has_collection(CANDIDATE_KNOWLEDGE_COLLECTION):
        db.create_collection(CANDIDATE_KNOWLEDGE_COLLECTION)
        logger.info(f"Created collection: {CANDIDATE_KNOWLEDGE_COLLECTION}")
    
    coll_candidates = db.collection(CANDIDATE_KNOWLEDGE_COLLECTION)
    try:
        coll_candidates.ensure_persistent_index(["fact_id"], unique=True)
        coll_candidates.ensure_persistent_index(["reference_id"])
        coll_candidates.ensure_persistent_index(["project_id"])
        coll_candidates.ensure_persistent_index(["promotion_state"])
        coll_candidates.ensure_persistent_index(["created_at"])
    except ArangoError:
        pass  # Indexes may already exist


def _create_external_reference(
    db: StandardDatabase,
    project_id: str,
    content_raw: str,
    source_name: str,
    source_url: Optional[str],
    tags: List[str],
) -> str:
    """Create and persist an ExternalReference.
    
    Args:
        db: ArangoDB database instance
        project_id: Project ID
        content_raw: Raw content text
        source_name: Source name (e.g., "Perplexity")
        source_url: Optional source URL
        tags: List of tags (default includes "OOB")
        
    Returns:
        reference_id (UUID string)
    """
    reference_id = str(uuid.uuid4())
    extracted_at = datetime.now(timezone.utc)
    
    # Ensure default tags include "OOB"
    if "OOB" not in tags:
        tags = ["OOB"] + [t for t in tags if t != "OOB"]
    
    ref = ExternalReference(
        reference_id=reference_id,
        project_id=project_id,
        content_raw=content_raw,
        source_name=source_name,
        source_url=source_url,
        extracted_at=extracted_at,
        tags=tags,
        status="INGESTED",
    )
    
    coll = db.collection(EXTERNAL_REFERENCES_COLLECTION)
    doc = ref.model_dump(exclude={"id", "key"})
    doc["_key"] = reference_id
    coll.insert(doc)
    
    logger.info(
        "Created external reference",
        extra={
            "payload": {
                "reference_id": reference_id,
                "project_id": project_id,
                "source_name": source_name,
                "status": "INGESTED",
            }
        },
    )
    
    return reference_id


def _update_external_reference_status(
    db: StandardDatabase,
    status: str,
    reference_id: str,
) -> None:
    """Update the status of an ExternalReference.
    
    Args:
        db: ArangoDB database instance
        reference_id: Reference ID
        status: New status value
    """
    try:
        coll = db.collection(EXTERNAL_REFERENCES_COLLECTION)
        coll.update({"_key": reference_id, "status": status})
        logger.debug(
            f"Updated external reference status",
            extra={"payload": {"reference_id": reference_id, "status": status}},
        )
    except Exception as e:
        logger.error(
            f"Failed to update external reference status: {e}",
            extra={"payload": {"reference_id": reference_id, "status": status}},
            exc_info=True,
        )


def _create_candidate_facts(
    db: StandardDatabase,
    reference_id: str,
    project_id: str,
    triples: List[Dict[str, Any]],
) -> int:
    """Create and persist CandidateFact entries from extracted triples.
    
    Args:
        db: ArangoDB database instance
        reference_id: External reference ID
        project_id: Project ID
        triples: List of triple dictionaries with subject, predicate, object, confidence
        
    Returns:
        Number of facts created
    """
    if not triples:
        return 0
    
    coll = db.collection(CANDIDATE_KNOWLEDGE_COLLECTION)
    created_at = datetime.now(timezone.utc)
    facts_created = 0
    
    for triple in triples:
        fact_id = str(uuid.uuid4())
        subject = triple.get("subject", "").strip()
        predicate = triple.get("predicate", "").strip()
        obj = triple.get("object", "").strip()
        confidence = float(triple.get("confidence", 0.5))
        
        # Skip invalid triples
        if not subject or not predicate or not obj:
            logger.warning(
                "Skipping invalid triple (missing subject/predicate/object)",
                extra={"payload": {"triple": triple}},
            )
            continue
        
        # Clamp confidence to [0.0, 1.0]
        confidence = max(0.0, min(1.0, confidence))
        
        fact = CandidateFact(
            fact_id=fact_id,
            reference_id=reference_id,
            project_id=project_id,
            subject=subject,
            predicate=predicate,
            object=obj,
            confidence=confidence,
            priority_boost=1.0,
            source_type="human_injected",
            promotion_state="candidate",
            created_at=created_at,
        )
        
        doc = fact.model_dump(exclude={"id", "key"})
        doc["_key"] = fact_id
        coll.insert(doc)
        facts_created += 1
    
    logger.info(
        f"Created {facts_created} candidate facts",
        extra={
            "payload": {
                "reference_id": reference_id,
                "project_id": project_id,
                "facts_created": facts_created,
            }
        },
    )
    
    return facts_created


def _extract_facts_from_content(
    content_raw: str,
    project_id: str,
    reference_id: str,
) -> tuple[List[Dict[str, Any]], bool, Optional[str]]:
    """Extract facts (triples) from raw content using Worker expert with Brain fallback.
    
    Args:
        content_raw: Raw content text to extract from
        project_id: Project ID for context
        reference_id: Reference ID for telemetry
        
    Returns:
        Tuple of (triples_list, fallback_used, error_message)
    """
    # Build extraction prompt (similar to cartographer_node)
    system_prompt = """You are the Cartographer. Extract a structured knowledge graph from text as JSON. Output ONLY JSON.

CRITICAL REQUIREMENTS:
- Output MUST be valid JSON only (no prose, no markdown code blocks)
- MUST include a "triples" array, even if empty
- Each triple must have: subject, predicate, object, confidence (0.0-1.0), and optional evidence

Required JSON structure:
{
  "triples": [
    {
      "subject": "entity or concept name",
      "predicate": "relationship type (e.g., 'causes', 'enables', 'mitigates', 'requires')",
      "object": "target entity or concept",
      "confidence": 0.0-1.0,
      "evidence": "text excerpt supporting this relation (optional)"
    }
  ]
}

The "triples" array is REQUIRED. Return empty array [] if no relations found."""

    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content_raw},
    ]
    
    try:
        # Route to Worker expert with Brain fallback
        expert_url, expert_name, expert_model = route_to_expert(
            "knowledge_sideload_extraction", ExpertType.EXTRACTION_SCHEMA
        )
        fallback_url = get_brain_url() if expert_name == "Worker" else None
        fallback_model = get_model_config("brain").model_id if fallback_url else None
        
        state = {"project_id": project_id, "job_id": reference_id}
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
            node_name="knowledge_sideload_extraction",
            state=state,
        )
        
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        
        # Parse JSON (handle markdown code blocks if present)
        if isinstance(content, str):
            if content.strip().startswith("```"):
                lines = content.strip().split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
            extracted = json.loads(content)
        else:
            extracted = content
        
        # Normalize to guarantee triples structure
        normalized = normalize_extracted_json(extracted)
        triples = normalized.get("triples", [])
        
        fallback_used = meta.get("path") == "fallback"
        
        return triples, fallback_used, None
        
    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"Failed to extract facts from content: {e}",
            extra={
                "payload": {
                    "reference_id": reference_id,
                    "project_id": project_id,
                    "error": error_msg,
                }
            },
            exc_info=True,
        )
        return [], False, error_msg


def _run_extraction_background(
    reference_id: str,
    project_id: str,
    content_raw: str,
) -> None:
    """Background task to extract facts from external reference content.
    
    This runs in a separate thread and does NOT block the API request.
    Includes timeout protection (300 seconds) to prevent runaway background work.
    
    Args:
        reference_id: External reference ID
        project_id: Project ID
        content_raw: Raw content to extract from
    """
    start_time = time.time()
    db = _get_db()
    if not db:
        logger.error(
            "Cannot run extraction: DB unavailable",
            extra={"payload": {"reference_id": reference_id}},
        )
        return
    
    _ensure_collections(db)
    
    try:
        # Update status to EXTRACTING
        _update_external_reference_status(db, "EXTRACTING", reference_id)
        
        # Extract facts with timeout protection (300 seconds)
        def run_extraction():
            return _extract_facts_from_content(content_raw, project_id, reference_id)
        
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_extraction)
                triples, fallback_used, error = future.result(timeout=300)  # 300 second timeout
        except FutureTimeoutError:
            # Timeout occurred - update status and emit telemetry
            logger.warning(
                f"Extraction timeout for reference {reference_id}",
                extra={"payload": {"reference_id": reference_id, "project_id": project_id}},
            )
            duration_ms = (time.time() - start_time) * 1000
            
            # Check if status is FAILED or use NEEDS_REVIEW
            try:
                coll_refs = db.collection(EXTERNAL_REFERENCES_COLLECTION)
                ref_doc = coll_refs.get(reference_id)
                current_status = ref_doc.get("status") if ref_doc else "EXTRACTING"
                # Use FAILED if already in a terminal state, otherwise NEEDS_REVIEW
                new_status = "FAILED" if current_status == "FAILED" else "NEEDS_REVIEW"
            except Exception:
                new_status = "NEEDS_REVIEW"
            
            _update_external_reference_status(db, new_status, reference_id)
            
            telemetry_emitter.emit_event(
                "knowledge_sideload_failed",
                {
                    "reference_id": reference_id,
                    "project_id": project_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "duration_ms": duration_ms,
                    "reason": "timeout",
                },
            )
            return
        
        if error:
            # Extraction failed
            _update_external_reference_status(db, "NEEDS_REVIEW", reference_id)
            duration_ms = (time.time() - start_time) * 1000
            telemetry_emitter.emit_event(
                "knowledge_sideload_completed",
                {
                    "reference_id": reference_id,
                    "project_id": project_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "duration_ms": duration_ms,
                    "facts_extracted": 0,
                    "fallback_used": False,
                    "status": "NEEDS_REVIEW",
                },
            )
            return
        
        # Persist candidate facts
        facts_created = _create_candidate_facts(db, reference_id, project_id, triples)
        
        # Update status based on results
        if facts_created == 0:
            status = "NEEDS_REVIEW"
        else:
            status = "EXTRACTED"
        
        _update_external_reference_status(db, status, reference_id)
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Emit completion telemetry
        telemetry_emitter.emit_event(
            "knowledge_sideload_completed",
            {
                "reference_id": reference_id,
                "project_id": project_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": duration_ms,
                "facts_extracted": facts_created,
                "fallback_used": fallback_used,
                "status": status,
            },
        )
        
        logger.info(
            f"Extraction completed for reference {reference_id}",
            extra={
                "payload": {
                    "reference_id": reference_id,
                    "project_id": project_id,
                    "facts_extracted": facts_created,
                    "status": status,
                    "fallback_used": fallback_used,
                    "duration_ms": duration_ms,
                }
            },
        )
        
    except Exception as e:
        logger.error(
            f"Background extraction failed: {e}",
            extra={"payload": {"reference_id": reference_id, "project_id": project_id}},
            exc_info=True,
        )
        try:
            _update_external_reference_status(db, "NEEDS_REVIEW", reference_id)
        except Exception:
            pass  # Best effort
        
        duration_ms = (time.time() - start_time) * 1000
        telemetry_emitter.emit_event(
            "knowledge_sideload_completed",
            {
                "reference_id": reference_id,
                "project_id": project_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": duration_ms,
                "facts_extracted": 0,
                "fallback_used": False,
                "status": "NEEDS_REVIEW",
            },
        )


@knowledge_bp.route("/sideload", methods=["POST"])
def sideload_knowledge():
    """Ingest external research content (OOB) into Vyasa's knowledge pipeline.
    
    Request body (JSON):
        {
            "project_id": str (required),
            "content_raw": str (required),
            "source_name": str (required, e.g., "Perplexity"),
            "source_url": str (optional),
            "tags": List[str] (optional, default includes "OOB")
        }
    
    Response:
        {
            "reference_id": str,
            "status": "INGESTED"
        }
    
    Errors:
        400: Missing required fields
        503: Database unavailable
    """
    db = _get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        payload = request.json or {}
        project_id = payload.get("project_id", "").strip()
        content_raw = payload.get("content_raw", "").strip()
        source_name = payload.get("source_name", "").strip()
        source_url = payload.get("source_url")
        tags = payload.get("tags", ["OOB"])
        
        # Validation
        if not project_id:
            return jsonify({"error": "project_id is required"}), 400
        if not content_raw:
            return jsonify({"error": "content_raw is required"}), 400
        if not source_name:
            return jsonify({"error": "source_name is required"}), 400
        
        # Ensure collections exist
        _ensure_collections(db)
        
        # Create external reference
        reference_id = _create_external_reference(
            db=db,
            project_id=project_id,
            content_raw=content_raw,
            source_name=source_name,
            source_url=source_url,
            tags=tags,
        )
        
        # Emit start telemetry
        telemetry_emitter.emit_event(
            "knowledge_sideload_started",
            {
                "reference_id": reference_id,
                "project_id": project_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_name": source_name,
                "has_source_url": bool(source_url),
            },
        )
        
        # Enqueue background extraction (non-blocking)
        thread = threading.Thread(
            target=_run_extraction_background,
            args=(reference_id, project_id, content_raw),
            daemon=True,
        )
        thread.start()
        
        return jsonify({"reference_id": reference_id, "status": "INGESTED"}), 201
        
    except Exception as e:
        logger.error(f"Failed to sideload knowledge: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@knowledge_bp.route("/references", methods=["GET"])
def list_references():
    """List external references for a project.
    
    Query parameters:
        project_id: str (required)
    
    Response:
        List of ExternalReference summaries (without content_raw for brevity)
    
    Errors:
        400: Missing project_id
        503: Database unavailable
    """
    db = _get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        project_id = request.args.get("project_id", "").strip()
        if not project_id:
            return jsonify({"error": "project_id query parameter is required"}), 400
        
        coll = db.collection(EXTERNAL_REFERENCES_COLLECTION)
        query = f"""
        FOR ref IN {EXTERNAL_REFERENCES_COLLECTION}
        FILTER ref.project_id == @project_id
        SORT ref.extracted_at DESC
        RETURN {{
            reference_id: ref.reference_id,
            project_id: ref.project_id,
            source_name: ref.source_name,
            source_url: ref.source_url,
            extracted_at: ref.extracted_at,
            tags: ref.tags,
            status: ref.status
        }}
        """
        
        cursor = db.aql.execute(query, bind_vars={"project_id": project_id})
        references = list(cursor)
        
        return jsonify(references), 200
        
    except Exception as e:
        logger.error(f"Failed to list references: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@knowledge_bp.route("/references/<reference_id>", methods=["GET"])
def get_reference(reference_id: str):
    """Get an external reference with its candidate facts.
    
    Args:
        reference_id: Reference ID
    
    Response:
        {
            "reference": ExternalReference (full object),
            "candidate_facts": List[CandidateFact]
        }
    
    Errors:
        404: Reference not found
        503: Database unavailable
    """
    db = _get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        # Get external reference
        coll_refs = db.collection(EXTERNAL_REFERENCES_COLLECTION)
        ref_doc = coll_refs.get(reference_id)
        
        if not ref_doc:
            return jsonify({"error": "Reference not found"}), 404
        
        # Get candidate facts
        coll_facts = db.collection(CANDIDATE_KNOWLEDGE_COLLECTION)
        query = f"""
        FOR fact IN {CANDIDATE_KNOWLEDGE_COLLECTION}
        FILTER fact.reference_id == @reference_id
        SORT fact.created_at DESC
        RETURN fact
        """
        
        cursor = db.aql.execute(query, bind_vars={"reference_id": reference_id})
        facts = list(cursor)
        
        # Remove ArangoDB internal fields for response
        ref_doc.pop("_id", None)
        ref_doc.pop("_key", None)
        ref_doc.pop("_rev", None)
        
        for fact in facts:
            fact.pop("_id", None)
            fact.pop("_key", None)
            fact.pop("_rev", None)
        
        return jsonify({"reference": ref_doc, "candidate_facts": facts}), 200
        
    except Exception as e:
        logger.error(f"Failed to get reference: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


def _compute_fact_hash(subject: str, predicate: str, obj: str) -> str:
    """Compute hash for a fact triple (normalized s|p|o).
    
    Args:
        subject: Subject of the triple
        predicate: Predicate of the triple
        obj: Object of the triple
    
    Returns:
        SHA256 hex digest of normalized triple
    """
    # Normalize: lowercase, strip whitespace
    s = str(subject).lower().strip()
    p = str(predicate).lower().strip()
    o = str(obj).lower().strip()
    
    # Create normalized string representation
    normalized = f"{s}|{p}|{o}"
    
    # Compute hash
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _promote_fact_to_canonical(
    db: StandardDatabase,
    fact: Dict[str, Any],
    reference_id: str,
    source_url: Optional[str],
    project_id: str,
) -> None:
    """Promote a candidate fact to canonical knowledge.
    
    Implements deduplication by fact_hash to prevent duplicate canonical entries.
    If a fact with the same hash exists, merges evidence/provenance instead.
    
    Args:
        db: ArangoDB database instance
        fact: Candidate fact document
        reference_id: External reference ID
        source_url: Source URL from external reference
        project_id: Project ID
    """
    coll_canonical = db.collection(CANONICAL_KNOWLEDGE_COLLECTION)
    
    # Compute fact_hash for deduplication
    subject = fact.get("subject", "")
    predicate = fact.get("predicate", "")
    obj = fact.get("object", "")
    fact_hash = _compute_fact_hash(subject, predicate, obj)
    
    # Check for existing canonical entry by fact_hash
    existing = None
    try:
        # Query for existing canonical entry with same fact_hash
        query = f"""
        FOR entry IN {CANONICAL_KNOWLEDGE_COLLECTION}
        FILTER entry.fact_hash == @fact_hash
        LIMIT 1
        RETURN entry
        """
        cursor = db.aql.execute(query, bind_vars={"fact_hash": fact_hash})
        results = list(cursor)
        if results:
            existing = results[0]
    except Exception:
        pass  # Query failed, will create new entry
    
    # Fallback: Generate entity_id from triple (use subject as primary entity) for backward compatibility
    entity_name = subject
    entity_id = entity_name.lower().replace(" ", "_").replace("-", "_").replace(".", "")
    if not entity_id:
        entity_id = f"fact_{fact.get('fact_id', 'unknown')[:8]}"
    
    # If no hash match found, check by entity_id for backward compatibility
    if not existing:
        try:
            existing_doc = coll_canonical.get(entity_id)
            if existing_doc:
                existing = existing_doc
        except Exception:
            pass  # Entry doesn't exist, create new
    
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Build source pointer (OOB-specific format)
    source_pointer = {
        "reference_id": reference_id,
        "source_url": source_url,
        "snippet": f"{fact.get('subject')} {fact.get('predicate')} {fact.get('object')}",
    }
    
    # Build provenance entry
    provenance_entry = {
        "project_id": project_id,
        "job_id": reference_id,  # Use reference_id as job_id for OOB content
        "contributed_at": now_iso,
        "source_pointer": source_pointer,
    }
    
    if existing:
        # Merge evidence/provenance: add source pointer and provenance without creating duplicate
        existing["source_pointers"] = existing.get("source_pointers", [])
        # Check if this source pointer already exists (avoid duplicates)
        pointer_exists = any(
            ptr.get("reference_id") == reference_id for ptr in existing["source_pointers"]
        )
        if not pointer_exists:
            existing["source_pointers"].append(source_pointer)
        
        existing["provenance_log"] = existing.get("provenance_log", [])
        # Check if provenance entry already exists for this reference_id
        provenance_exists = any(
            log.get("job_id") == reference_id for log in existing["provenance_log"]
        )
        if not provenance_exists:
            existing["provenance_log"].append(provenance_entry)
        
        existing["updated_at"] = now_iso
        # Ensure fact_hash is set on existing entry
        existing["fact_hash"] = fact_hash
        
        coll_canonical.update(existing)
        logger.debug(
            f"Merged evidence into existing canonical entry (deduplicated by fact_hash)",
            extra={
                "payload": {
                    "entity_id": existing.get("entity_id", entity_id),
                    "fact_hash": fact_hash,
                    "reference_id": reference_id,
                }
            },
        )
    else:
        # Create new canonical entry
        entry = {
            "_key": entity_id,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "entity_type": "Unknown",  # OOB facts don't have entity_type; can be enhanced later
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "fact_hash": fact_hash,  # Store hash for deduplication
            "description": f"{subject} {predicate} {obj}",
            "source_pointers": [source_pointer],
            "provenance_log": [provenance_entry],
            "conflict_flags": [],
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        
        try:
            coll_canonical.insert(entry)
            logger.info(
                f"Created new canonical entry from OOB fact",
                extra={
                    "payload": {
                        "entity_id": entity_id,
                        "fact_id": fact.get("fact_id"),
                        "fact_hash": fact_hash,
                        "reference_id": reference_id,
                    }
                },
            )
        except ArangoError as e:
            # May fail if entity_id already exists (race condition), try update
            if "unique constraint" in str(e).lower():
                existing = coll_canonical.get(entity_id)
                if existing:
                    # Merge evidence/provenance
                    existing["source_pointers"] = existing.get("source_pointers", [])
                    pointer_exists = any(
                        ptr.get("reference_id") == reference_id for ptr in existing["source_pointers"]
                    )
                    if not pointer_exists:
                        existing["source_pointers"].append(source_pointer)
                    existing["provenance_log"] = existing.get("provenance_log", [])
                    provenance_exists = any(
                        log.get("job_id") == reference_id for log in existing["provenance_log"]
                    )
                    if not provenance_exists:
                        existing["provenance_log"].append(provenance_entry)
                    existing["updated_at"] = now_iso
                    existing["fact_hash"] = fact_hash
                    coll_canonical.update(existing)
            else:
                raise


@knowledge_bp.route("/references/<reference_id>/promote", methods=["POST"])
def promote_reference(reference_id: str):
    """Promote candidate facts from an external reference to canonical knowledge.
    
    Request body (JSON):
        {
            "fact_ids": List[str] (optional),  # If omitted, auto-promote based on threshold
            "mode": "manual" | "auto"
        }
    
    Promotion rules:
    - manual: promote only selected fact_ids
    - auto: promote facts where confidence >= OOB_PROMOTION_CONFIDENCE_THRESHOLD
      AND if OOB_REQUIRE_SOURCE_URL_FOR_AUTO_PROMOTION then require source_url exists
    
    Response:
        {
            "promoted_count": int,
            "reference_id": str,
            "status": "PROMOTED" | "EXTRACTED"  # PROMOTED if at least one fact promoted
        }
    
    Errors:
        404: Reference not found
        400: Invalid mode or missing fact_ids in manual mode
        503: Database unavailable
    """
    db = _get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        payload = request.json or {}
        mode = payload.get("mode", "auto")
        fact_ids = payload.get("fact_ids", [])
        
        if mode not in ("manual", "auto"):
            return jsonify({"error": "mode must be 'manual' or 'auto'"}), 400
        
        if mode == "manual" and not fact_ids:
            return jsonify({"error": "fact_ids required for manual mode"}), 400
        
        # Get external reference
        coll_refs = db.collection(EXTERNAL_REFERENCES_COLLECTION)
        ref_doc = coll_refs.get(reference_id)
        
        if not ref_doc:
            return jsonify({"error": "Reference not found"}), 404
        
        project_id = ref_doc.get("project_id")
        source_url = ref_doc.get("source_url")
        
        # Get candidate facts
        coll_facts = db.collection(CANDIDATE_KNOWLEDGE_COLLECTION)
        query = f"""
        FOR fact IN {CANDIDATE_KNOWLEDGE_COLLECTION}
        FILTER fact.reference_id == @reference_id
        FILTER fact.promotion_state == "candidate"
        RETURN fact
        """
        
        cursor = db.aql.execute(query, bind_vars={"reference_id": reference_id})
        all_facts = list(cursor)
        
        # Filter facts to promote based on mode
        facts_to_promote = []
        if mode == "manual":
            fact_ids_set = set(fact_ids)
            facts_to_promote = [f for f in all_facts if f.get("fact_id") in fact_ids_set]
        else:  # auto mode
            for fact in all_facts:
                confidence = float(fact.get("confidence", 0.0))
                
                # Check confidence threshold
                if confidence < OOB_PROMOTION_CONFIDENCE_THRESHOLD:
                    continue
                
                # Check source_url requirement if enabled
                if OOB_REQUIRE_SOURCE_URL_FOR_AUTO_PROMOTION and not source_url:
                    continue
                
                facts_to_promote.append(fact)
        
        if not facts_to_promote:
            return jsonify({
                "promoted_count": 0,
                "reference_id": reference_id,
                "status": ref_doc.get("status"),
            }), 200
        
        # Ensure canonical_knowledge collection exists
        if not db.has_collection(CANONICAL_KNOWLEDGE_COLLECTION):
            db.create_collection(CANONICAL_KNOWLEDGE_COLLECTION)
            coll_canonical = db.collection(CANONICAL_KNOWLEDGE_COLLECTION)
            try:
                coll_canonical.ensure_persistent_index(["entity_id"], unique=True)
                coll_canonical.ensure_persistent_index(["entity_name"])
                coll_canonical.ensure_persistent_index(["fact_hash"])  # Index for deduplication
                coll_canonical.ensure_persistent_index(["created_at"])
            except ArangoError:
                pass
        else:
            # Ensure fact_hash index exists on existing collection
            coll_canonical = db.collection(CANONICAL_KNOWLEDGE_COLLECTION)
            try:
                coll_canonical.ensure_persistent_index(["fact_hash"])
            except ArangoError:
                pass  # Index may already exist
        
        # Promote each fact
        promoted_count = 0
        for fact in facts_to_promote:
            try:
                _promote_fact_to_canonical(db, fact, reference_id, source_url, project_id)
                
                # Update candidate fact promotion_state
                coll_facts.update({"_key": fact.get("fact_id"), "promotion_state": "canonical"})
                promoted_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to promote fact {fact.get('fact_id')}: {e}",
                    extra={"payload": {"fact_id": fact.get("fact_id"), "reference_id": reference_id}},
                    exc_info=True,
                )
        
        # Update external reference status if at least one fact promoted
        new_status = "PROMOTED" if promoted_count > 0 else ref_doc.get("status")
        if promoted_count > 0:
            _update_external_reference_status(db, "PROMOTED", reference_id)
        
        # Emit telemetry
        telemetry_emitter.emit_event(
            "knowledge_promoted",
            {
                "reference_id": reference_id,
                "project_id": project_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "promoted_count": promoted_count,
                "mode": mode,
            },
        )
        
        return jsonify({
            "promoted_count": promoted_count,
            "reference_id": reference_id,
            "status": new_status,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to promote reference: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@knowledge_bp.route("/references/<reference_id>/reject", methods=["POST"])
def reject_reference(reference_id: str):
    """Reject an external reference (marks as REJECTED, does not delete facts).
    
    Args:
        reference_id: Reference ID
    
    Response:
        {
            "reference_id": str,
            "status": "REJECTED"
        }
    
    Errors:
        404: Reference not found
        503: Database unavailable
    """
    db = _get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        # Get external reference
        coll_refs = db.collection(EXTERNAL_REFERENCES_COLLECTION)
        ref_doc = coll_refs.get(reference_id)
        
        if not ref_doc:
            return jsonify({"error": "Reference not found"}), 404
        
        # Update status to REJECTED
        _update_external_reference_status(db, "REJECTED", reference_id)
        
        # Emit telemetry
        telemetry_emitter.emit_event(
            "knowledge_rejected",
            {
                "reference_id": reference_id,
                "project_id": ref_doc.get("project_id"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        
        return jsonify({
            "reference_id": reference_id,
            "status": "REJECTED",
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to reject reference: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500
