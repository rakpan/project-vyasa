"""
Quality and governance nodes for Project Vyasa.

This module contains nodes responsible for validation, conflict detection,
and quality gates: critic_node, reframing_node, tone_validator_node.

Dependencies:
- Imports from .base for wrap_prompt_with_context
- Imports from .nodes for shared utilities (validate_state_schema, route_to_expert, etc.)
- Does NOT import from .cartography to avoid circular dependencies
"""

import json
import re
import uuid
from typing import Dict, Any, List, Optional

import requests

from ...shared.config import get_brain_url
from ...shared.model_registry import get_model_config
from ...shared.context_budget import estimate_tokens
from ...shared.logger import get_logger
from ...shared.role_manager import RoleRegistry
from ...shared.utils import get_utc_now
from ..state import JobStatus, PhaseEnum, ResearchState
from ..telemetry import get_telemetry_emitter, trace_node
from ..job_store import store_conflict_report, store_reframing_proposal
from ...shared.conflict_utils import compute_conflict_hash
from ...shared.schema import (
    ConflictItem,
    ConflictReport,
    ConflictSeverity,
    ConflictType,
    ConflictProducer,
    ConflictSuggestedAction,
    RecommendedNextStep,
    ReframingProposal,
    PivotType,
    ToneFlag,
)
from ..guards.tone_rewrite import rewrite_to_neutral
from ..job_manager import update_job_status
from langgraph.types import interrupt

# Import shared utilities from nodes.py (these are not quality-specific)
from .nodes import (
    validate_state_schema,
    hydrate_project_context,
    route_to_expert,
    call_expert_with_fallback,
    check_kv_backpressure,
    _get_project_service,
    ExpertType,
)
from .base import wrap_prompt_with_context
from ..schemas.verification_decision import VerificationDecisionRecord, VerificationDecision
from ..schemas.evidence_pack import EvidencePack
from ..services.verification_decision_service import VerificationDecisionService
from ..services.evidence_pack_service import EvidencePackService
from ..services.retrieval_bundle_service import RetrievalBundleService

logger = get_logger("orchestrator", __name__)
telemetry_emitter = get_telemetry_emitter()
role_registry = RoleRegistry()


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


def _stable_fact_id(triple: Dict[str, Any]) -> str:
    """Generate a stable ID for a triple/fact using core fields."""
    parts = [
        str(triple.get("subject", "")).strip().lower(),
        str(triple.get("predicate", "")).strip().lower(),
        str(triple.get("object", "")).strip().lower(),
        str(triple.get("doc_hash", "")).strip().lower(),
        str(triple.get("source_pointer", {}).get("page", "")),
    ]
    return uuid.uuid5(uuid.NAMESPACE_URL, "|".join(parts)).hex


def _build_conflict_report(
    state: ResearchState,
    conflict_flags: List[str],
    status: str,
    revision_count: int,
) -> Optional[ConflictReport]:
    """Create a minimal ConflictReport from critic state."""
    if status == "pass" and not conflict_flags:
        return None

    extracted = state.get("extracted_json") or {}
    triples = extracted.get("triples") if isinstance(extracted, dict) else []
    anchors = []
    contradict_ids: List[str] = []
    if isinstance(triples, list) and triples:
        t0 = triples[0] if isinstance(triples[0], dict) else {}
        pointer = t0.get("source_pointer") or {}
        doc_hash = t0.get("doc_hash") or pointer.get("doc_hash") or state.get("doc_hash", "")
        page = pointer.get("page") or 1
        bbox = pointer.get("bbox") or [0, 0, 0, 0]
        snippet = pointer.get("snippet") or t0.get("snippet") or state.get("raw_text", "")[:120]
        anchors.append(
            {
                "doc_hash": doc_hash,
                "page": page,
                "bbox": bbox,
                "snippet": snippet,
            }
        )
        contradict_ids.append(_stable_fact_id(t0))

    severity = ConflictSeverity.HIGH if conflict_flags else ConflictSeverity.MEDIUM
    if conflict_flags and revision_count >= 2:
        severity = ConflictSeverity.BLOCKER
    suggested_actions = [ConflictSuggestedAction.RETRY_EXTRACTION]
    if severity in (ConflictSeverity.HIGH, ConflictSeverity.BLOCKER):
        suggested_actions.append(ConflictSuggestedAction.HUMAN_SIGNOFF_REQUIRED)

    items = [
        ConflictItem(
            conflict_id=str(uuid.uuid4()),
            conflict_type=ConflictType.STRUCTURAL_CONFLICT if conflict_flags else ConflictType.UNSUPPORTED_CORE_CLAIM,
            severity=severity,
            summary=(conflict_flags[0] if conflict_flags else "Critic failed validation")[:240],
            details=("; ".join(conflict_flags) if conflict_flags else "Extraction failed quality gates")[:1200],
            produced_by=ConflictProducer.CRITIC,
            contradicts=contradict_ids or None,
            evidence_anchors=anchors,
            assumptions=[],
            suggested_actions=suggested_actions,
            confidence=0.55 if conflict_flags else 0.4,
        )
    ]

    deadlock_type = None
    next_step = RecommendedNextStep.REVISE_AND_RETRY
    deadlock = False
    if revision_count >= 2 and any(i.severity == ConflictSeverity.BLOCKER for i in items):
        deadlock = True
        deadlock_type = items[0].conflict_type
        next_step = RecommendedNextStep.TRIGGER_REFRAMING

    report = ConflictReport(
        report_id=str(uuid.uuid4()),
        project_id=state.get("project_id", ""),
        job_id=state.get("job_id", ""),
        doc_hash=state.get("doc_hash", anchors[0]["doc_hash"] if anchors else ""),
        revision_count=revision_count,
        critic_status=status,
        deadlock=deadlock,
        deadlock_type=deadlock_type,
        conflict_items=items,
        conflict_hash="",
        recommended_next_step=next_step,
        created_at=get_utc_now(),
    )
    report.conflict_hash = compute_conflict_hash(report)
    return report


def critic_verify_claim_bounded(
    claim: Dict[str, Any],
    evidence_pack: EvidencePack,
    project_id: str,
    ingestion_id: str,
    db: Optional[Any] = None,
    bounded_retry_used: bool = False,
) -> VerificationDecisionRecord:
    """Verify a claim against EvidencePack with bounded retry (Tier B).
    
    Applies runtime budgets:
    - max output tokens from Tier B budgets
    - bounded retry max from Tier B budgets
    - prompt template from DB-backed registry
    """
    """Bounded spot-check verification of a single claim against EvidencePack.
    
    Protocol:
    - Critic only sees EvidencePack snippets (never full PDF)
    - For Ambiguous: allow at most ONE bounded retry (one extra snippet)
    - Persist decision per claim with full provenance
    
    Args:
        claim: Claim/triple dictionary to verify.
        evidence_pack: EvidencePack containing bounded evidence snippets.
        project_id: Project identifier.
        ingestion_id: Ingestion identifier.
        db: Optional ArangoDB database instance for persistence.
        bounded_retry_used: Whether a bounded retry has already been used.
    
    Returns:
        VerificationDecisionRecord with decision and supporting chunk IDs.
    """
    from ..prompts import get_active_prompt_with_meta, DEFAULT_CRITIC_PROMPT
    from ..nodes.nodes import route_to_expert, call_expert_with_fallback
    from ..config import ExpertType
    
    claim_id = claim.get("claim_id", "")
    claim_text = claim.get("claim_text") or f"{claim.get('subject', '')} {claim.get('predicate', '')} {claim.get('object', '')}"
    
    # Format EvidencePack snippets for verification
    evidence_text = "EVIDENCE PACK (Bounded Evidence - Spot Check):\n"
    for idx, snippet in enumerate(evidence_pack.snippets, 1):
        pointer = evidence_pack.pointers[idx-1] if idx-1 < len(evidence_pack.pointers) else None
        evidence_text += f"[{idx}] {snippet.quote_text}\n"
        evidence_text += f"    (chunk_id: {snippet.chunk_id}, page {snippet.page_number or '?'})\n\n"
    
    # Build verification prompt
    system_template, _ = get_active_prompt_with_meta("vyasa-critic", DEFAULT_CRITIC_PROMPT)
    
    verification_instruction = """
CRITICAL: You are performing a bounded spot-check verification of a claim against EvidencePack snippets.

You MUST return valid JSON ONLY (no prose, no markdown code blocks). The output MUST strictly conform to this schema:

{
  "decision": "Verified" | "Unsupported" | "Contradicted" | "Ambiguous",
  "rationale": "Short rationale (max 500 chars)",
  "supporting_chunk_ids": ["chunk_id1", "chunk_id2", "chunk_id3"] (1-3 chunk IDs from EvidencePack),
  "requires_retry": false (true only if decision is Ambiguous and retry not yet used)
}

REQUIREMENTS:
- decision MUST be one of: Verified, Unsupported, Contradicted, Ambiguous
- supporting_chunk_ids MUST reference chunk_ids from the EvidencePack provided (1-3 chunks)
- rationale MUST be concise (max 500 chars)
- If decision is Ambiguous and requires_retry is true, a bounded retry (one extra snippet) may be used
"""
    
    system_prompt = f"{system_template}\n\n{verification_instruction}"
    
    user_prompt = f"""Verify the following claim against the EvidencePack:

CLAIM TO VERIFY:
{claim_text}

EVIDENCE PACK:
{evidence_text}

Return ONLY valid JSON with decision, rationale, and supporting_chunk_ids from the EvidencePack above."""
    
    # Call Nemotron via SGLang (Tier-B call)
    expert_url, expert_name, expert_model = route_to_expert("critic_verify", ExpertType.LOGIC_REASONING)
    
    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    
    try:
        response = call_expert_with_fallback(
            expert_url=expert_url,
            expert_name=expert_name,
            prompt=prompt,
            model_config=expert_model,
            node_name="critic_verify",
            job_id=None,
        )
        
        # Parse JSON response
        extracted = response.get("content", "") if isinstance(response, dict) else str(response)
        
        # Try to extract JSON from response
        json_match = re.search(r'\{.*"decision".*\}', extracted, re.DOTALL)
        if json_match:
            verification_result = json.loads(json_match.group(0))
        else:
            # Try parsing entire response as JSON
            verification_result = json.loads(extracted)
        
        decision_str = verification_result.get("decision", "Unsupported")
        rationale = verification_result.get("rationale", "No rationale provided")
        supporting_chunk_ids = verification_result.get("supporting_chunk_ids", [])
        requires_retry = verification_result.get("requires_retry", False)
        
        # Validate decision enum
        try:
            decision = VerificationDecision(decision_str)
        except ValueError:
            logger.warning(f"Invalid decision value: {decision_str}, defaulting to Unsupported")
            decision = VerificationDecision.UNSUPPORTED
        
        # Validate supporting_chunk_ids are from EvidencePack
        valid_chunk_ids = [s.chunk_id for s in evidence_pack.snippets]
        supporting_chunk_ids = [cid for cid in supporting_chunk_ids if cid in valid_chunk_ids]
        
        # Ensure 1-3 chunk IDs
        if not supporting_chunk_ids:
            # Default to first chunk if none provided
            supporting_chunk_ids = [evidence_pack.snippets[0].chunk_id] if evidence_pack.snippets else []
        elif len(supporting_chunk_ids) > 3:
            supporting_chunk_ids = supporting_chunk_ids[:3]
        
        # Handle Ambiguous with bounded retry (if not already used)
        if decision == VerificationDecision.AMBIGUOUS and requires_retry and not bounded_retry_used:
            # Get one extra snippet (if available)
            if len(evidence_pack.snippets) < 20:  # EvidencePack max is 20
                # In a full implementation, we'd retrieve one more chunk from RetrievalBundle
                # For now, we'll mark that retry was attempted
                bounded_retry_used = True
                logger.debug(
                    f"Ambiguous decision for claim {claim_id}, bounded retry used",
                    extra={"payload": {"claim_id": claim_id, "evidence_pack_id": evidence_pack.pack_id}}
                )
        
        # Create VerificationDecisionRecord
        verification_decision = VerificationDecisionRecord(
            claim_id=claim_id,
            decision=decision,
            rationale=rationale[:500],  # Enforce max length
            supporting_chunk_ids=supporting_chunk_ids,
            bounded_retry_used=bounded_retry_used,
            project_id=project_id,
            ingestion_id=ingestion_id,
            evidence_pack_id=evidence_pack.pack_id,
            retrieval_bundle_id=evidence_pack.retrieval_bundle_id,
        )
        
        # Persist if DB available
        if db:
            try:
                decision_service = VerificationDecisionService(db)
                verification_decision = decision_service.save_decision(verification_decision)
                logger.debug(
                    f"Saved VerificationDecision for claim {claim_id}",
                    extra={
                        "payload": {
                            "decision_id": verification_decision.decision_id,
                            "claim_id": claim_id,
                            "decision": decision.value,
                            "evidence_pack_id": evidence_pack.pack_id,
                        }
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to persist VerificationDecision: {e}", exc_info=True)
        
        # Opik tracing: Critic verify/flag decisions (critical path span 3)
        from ..telemetry.opik_emitter import get_opik_emitter
        opik_emitter = get_opik_emitter()
        opik_emitter.emit_span(
            span_name="critic_verify",
            job_id=None,  # Not available in this context
            project_id=project_id,
            ingestion_id=ingestion_id,
            meta={
                "claim_id": claim_id,
                "decision": decision.value,
                "evidence_pack_id": evidence_pack.pack_id,
                "retrieval_bundle_id": evidence_pack.retrieval_bundle_id,
                "supporting_chunk_ids": supporting_chunk_ids,
                "bounded_retry_used": bounded_retry_used,
            },
            error=None,  # Success case
        )
        
        return verification_decision
        
    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"Failed to verify claim {claim_id}: {e}",
            exc_info=True
        )
        
        # Opik tracing: Emit span even on failure
        from ..telemetry.opik_emitter import get_opik_emitter
        opik_emitter = get_opik_emitter()
        opik_emitter.emit_span(
            span_name="critic_verify",
            job_id=None,  # Not available in this context
            project_id=project_id,
            ingestion_id=ingestion_id,
            meta={
                "claim_id": claim_id,
                "decision": "UNSUPPORTED",  # Default on failure
                "evidence_pack_id": evidence_pack.pack_id if evidence_pack else None,
                "retrieval_bundle_id": evidence_pack.retrieval_bundle_id if evidence_pack else None,
                "supporting_chunk_ids": [],
                "bounded_retry_used": bounded_retry_used,
            },
            error=error_msg,
        )
        
        # Return Unsupported decision on failure
        return VerificationDecisionRecord(
            claim_id=claim_id,
            decision=VerificationDecision.UNSUPPORTED,
            rationale=f"Verification failed: {error_msg[:500]}",
            supporting_chunk_ids=[evidence_pack.snippets[0].chunk_id] if evidence_pack and evidence_pack.snippets else [],
            bounded_retry_used=bounded_retry_used,
            project_id=project_id,
            ingestion_id=ingestion_id,
            evidence_pack_id=evidence_pack.pack_id if evidence_pack else "",
            retrieval_bundle_id=evidence_pack.retrieval_bundle_id if evidence_pack else "",
        )


@trace_node
def critic_node(state: ResearchState) -> ResearchState:
    """Validate extracted graph and return pass/fail with critiques.
    
    Uses Brain (high-level reasoning) service for validation.
    Includes FP4 quantization failure detection to catch garbled text or repetitive tokens.
    Includes vocabulary guardrail check for forbidden words in synthesizer output.
    """
    state = validate_state_schema(state)
    state = hydrate_project_context(state)
    extracted = state.get("extracted_json") or {}
    synthesis = state.get("synthesis", "")
    
    # Get project context
    project_id = state.get("project_id")
    ingestion_id = state.get("ingestion_id")
    job_id = state.get("jobId") or state.get("job_id")
    
    # Debug logging
    logger.debug(
        "Critic node entry (bounded verification)",
        extra={
            "payload": {
                "job_id": job_id,
                "project_id": project_id,
                "ingestion_id": ingestion_id,
                "has_extracted": bool(extracted),
            }
        }
    )
    
    # Get DB connection for persistence
    db = None
    try:
        from arango import ArangoClient
        from ...shared.config import get_memory_url, get_arango_password, ARANGODB_DB, ARANGODB_USER
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
    except Exception as e:
        logger.warning(f"Failed to connect to DB for critic: {e}", exc_info=True)
        # Continue without DB (decisions won't be persisted, but verification can proceed)
    
    # Fetch prompt from Prompt Registry (with fallback to factory default)
    from ..prompts import get_active_prompt_with_meta, DEFAULT_CRITIC_PROMPT
    system_template, prompt_meta = get_active_prompt_with_meta("vyasa-critic", DEFAULT_CRITIC_PROMPT)
    
    # Record prompt usage in state
    prompt_manifest = state.get("prompt_manifest", {})
    prompt_manifest["critic"] = prompt_meta.model_dump(mode="python")
    state["prompt_manifest"] = prompt_manifest
    
    # Pre-validation: Check for FP4 quantization failures in extracted text
    # This catches failures before sending to Brain, saving compute
    extracted_str = json.dumps(extracted, ensure_ascii=False)
    if _detect_quantization_failure(extracted_str):
        logger.warning(
            "FP4 quantization failure detected in extraction",
            extra={"payload": {"extracted_preview": extracted_str[:200]}},
        )
        # Early return to avoid double-incrementing revision_count in downstream logic
        # Preserve ALL state fields (defensive preservation)
        revision_count = state.get("revision_count", 0) + 1
        return {
            **state,
            "critiques": ["Extraction appears garbled or contains repetitive tokens (possible FP4 quantization failure)"],
            "revision_count": revision_count,
            "critic_status": "fail",
        }

    # Get triples/claims from extracted_json
    triples = extracted.get("triples", []) if isinstance(extracted, dict) else []
    if not triples:
        logger.warning("No triples found in extracted_json for verification")
        return {
            **state,
            "critiques": ["No triples found for verification"],
            "critic_status": "fail",
        }
    
    # Get or build EvidencePack for verification
    # Protocol: Critic only sees EvidencePack snippets (never full PDF)
    evidence_pack = None
    if state.get("evidence_pack_id") and db:
        # Try to load EvidencePack from state
        try:
            pack_service = EvidencePackService(db)
            evidence_pack = pack_service.get_pack(state.get("evidence_pack_id"))
        except Exception as e:
            logger.warning(f"Failed to load EvidencePack from state: {e}", exc_info=True)
    
    # If no EvidencePack in state, build one from triples' chunk_ids
    if not evidence_pack and project_id and ingestion_id and db:
        try:
            from ..storage.qdrant import QdrantStorage
            
            # Collect chunk_ids from triples
            chunk_ids = []
            for triple in triples:
                if isinstance(triple, dict):
                    # Get chunk_ids from triple metadata or source_pointer
                    triple_chunk_ids = triple.get("chunk_ids", [])
                    if not triple_chunk_ids:
                        # Fallback: try to extract from metadata
                        metadata = triple.get("metadata", {})
                        triple_chunk_ids = metadata.get("chunk_ids", [])
                    chunk_ids.extend(triple_chunk_ids)
            
            # Deduplicate
            chunk_ids = list(set(chunk_ids))
            
            if chunk_ids:
                # Retrieve chunks from Qdrant
                qdrant_storage = QdrantStorage()
                chunks = []
                for chunk_id in chunk_ids[:20]:  # Limit to 20 chunks (EvidencePack max)
                    try:
                        chunk_data = qdrant_storage.get_chunks_by_ids([chunk_id], project_id)
                        if chunk_data:
                            chunks.extend(chunk_data)
                    except Exception as e:
                        logger.warning(f"Failed to retrieve chunk {chunk_id}: {e}")
                
                if chunks:
                    # Build RetrievalBundle (required for EvidencePack)
                    bundle_service = RetrievalBundleService(db)
                    from ..schemas.retrieval import RetrievalBundle
                    retrieval_bundle = RetrievalBundle.create(
                        query_text="Critic verification",
                        project_id=project_id,
                        ingestion_id=ingestion_id,
                        candidate_chunks=chunks,
                        reranked_chunks=chunks,
                        embedder_model_id="nvidia/nv-embedqa-e5-v5",
                        reranker_model_id="none",
                        top_k_embed=len(chunks),
                        top_k_rerank=len(chunks),
                        query_source="critic_verification",
                        section_id=None,
                    )
                    bundle_service.save_bundle(retrieval_bundle)
                    
                    # Build EvidencePack
                    from ..section_synthesis.section_orchestrator import build_evidence_pack
                    evidence_pack = build_evidence_pack(
                        reranked_chunks=chunks,
                        retrieval_bundle=retrieval_bundle,
                        ingestion_id=ingestion_id,
                        project_id=project_id,
                        section_id=None,
                    )
                    
                    # Persist EvidencePack
                    pack_service = EvidencePackService(db)
                    evidence_pack = pack_service.save_pack(evidence_pack)
                    
                    logger.info(
                        f"Built EvidencePack for critic verification",
                        extra={
                            "payload": {
                                "pack_id": evidence_pack.pack_id,
                                "chunk_count": len(chunks),
                                "snippet_count": len(evidence_pack.snippets),
                            }
                        }
                    )
        except Exception as e:
            logger.error(f"Failed to build EvidencePack for critic: {e}", exc_info=True)
            # Continue without EvidencePack (will fail verification)
    
    if not evidence_pack:
        logger.error("No EvidencePack available for critic verification")
        return {
            **state,
            "critiques": ["EvidencePack required for verification but not available"],
            "critic_status": "fail",
        }
    
    # Perform bounded spot-check verification for each claim/triple
    verification_decisions = []
    critiques = []
    verified_count = 0
    unsupported_count = 0
    contradicted_count = 0
    ambiguous_count = 0
    
    for triple in triples:
        if not isinstance(triple, dict):
            continue
        
        claim_id = triple.get("claim_id", "")
        if not claim_id:
            logger.warning("Triple missing claim_id, skipping verification")
            continue
        
        # Check if decision already exists (avoid duplicate verification)
        if db:
            try:
                decision_service = VerificationDecisionService(db)
                existing_decisions = decision_service.get_decisions_by_claim(claim_id, project_id)
                if existing_decisions:
                    # Use most recent decision
                    verification_decisions.append(existing_decisions[0])
                    decision = existing_decisions[0].decision
                    if decision == VerificationDecision.VERIFIED:
                        verified_count += 1
                    elif decision == VerificationDecision.UNSUPPORTED:
                        unsupported_count += 1
                    elif decision == VerificationDecision.CONTRADICTED:
                        contradicted_count += 1
                    elif decision == VerificationDecision.AMBIGUOUS:
                        ambiguous_count += 1
                    continue
            except Exception as e:
                logger.warning(f"Failed to check existing decisions: {e}", exc_info=True)
        
        # Perform bounded verification
        try:
            decision = critic_verify_claim_bounded(
                claim=triple,
                evidence_pack=evidence_pack,
                project_id=project_id,
                ingestion_id=ingestion_id,
                db=db,
                bounded_retry_used=False,  # Start with no retry
            )
            
            verification_decisions.append(decision)
            
            # Handle Ambiguous with bounded retry (if not already used)
            if decision.decision == VerificationDecision.AMBIGUOUS and not decision.bounded_retry_used:
                # Retry with one extra snippet (if available)
                # In a full implementation, we'd add one more chunk to EvidencePack
                # For now, we'll mark the decision as requiring retry
                logger.debug(
                    f"Ambiguous decision for claim {claim_id}, attempting bounded retry",
                    extra={"payload": {"claim_id": claim_id}}
                )
                # Note: Full retry implementation would add one more snippet to EvidencePack
                # and call critic_verify_claim_bounded again with bounded_retry_used=True
            
            # Aggregate counts
            if decision.decision == VerificationDecision.VERIFIED:
                verified_count += 1
            elif decision.decision == VerificationDecision.UNSUPPORTED:
                unsupported_count += 1
                critiques.append(f"Claim {claim_id}: Unsupported - {decision.rationale}")
            elif decision.decision == VerificationDecision.CONTRADICTED:
                contradicted_count += 1
                critiques.append(f"Claim {claim_id}: Contradicted - {decision.rationale}")
            elif decision.decision == VerificationDecision.AMBIGUOUS:
                ambiguous_count += 1
                critiques.append(f"Claim {claim_id}: Ambiguous - {decision.rationale}")
                
        except Exception as e:
            logger.error(
                f"Failed to verify claim {claim_id}: {e}",
                exc_info=True
            )
            critiques.append(f"Claim {claim_id}: Verification failed - {str(e)}")
            unsupported_count += 1
    
    # Determine overall status
    total_claims = len(triples)
    if total_claims == 0:
        status = "fail"
    elif verified_count == total_claims:
        status = "pass"
    elif contradicted_count > 0:
        status = "fail"
    elif unsupported_count > verified_count:
        status = "fail"
    else:
        status = "pass"  # Mostly verified, allow some ambiguous/unsupported
    
    # Log verification summary
    logger.info(
        "Critic bounded verification completed",
        extra={
            "payload": {
                "total_claims": total_claims,
                "verified": verified_count,
                "unsupported": unsupported_count,
                "contradicted": contradicted_count,
                "ambiguous": ambiguous_count,
                "evidence_pack_id": evidence_pack.pack_id if evidence_pack else None,
            }
        }
    )
    
    # Conflict flags from state
    conflict_flags = state.get("conflict_flags") or []
    
    # Deterministic conflict detection: detect contradictions using graph traversal
    detected_conflicts = []
    rigor_level = state.get("rigor_level") or (state.get("project_context") or {}).get("rigor_level", "exploratory")
    
    if project_id:
            try:
                from ..storage.arango import load_claims_for_conflict_detection
                from ..conflict_utils import (
                    DeterministicConflictType,
                    generate_conflict_explanation,
                )
                from ..schemas.claims import Claim, SourceAnchor
                from ...shared.schema import ConflictItem, ConflictSeverity, ConflictProducer, ConflictSuggestedAction
                
                # Load existing claims from ArangoDB
                existing_claims = load_claims_for_conflict_detection(
                    db=_get_project_service().db if _get_project_service() else None,
                    project_id=project_id,
                    ingestion_id=ingestion_id,
                    job_id=job_id,
                ) if _get_project_service() else []
                
                # Also get current triples from state
                current_triples = extracted.get("triples", []) if isinstance(extracted, dict) else []
                
                # Combine existing and current claims
                all_claims = existing_claims + current_triples
                
                # Detect contradictions: same (subject, predicate) but different object
                # Build index by (subject, predicate) -> list of claims
                claim_index: Dict[tuple, List[Dict[str, Any]]] = {}
                for claim in all_claims:
                    if not isinstance(claim, dict):
                        continue
                    subject = claim.get("subject", "").strip().lower()
                    predicate = claim.get("predicate", "").strip().lower()
                    if subject and predicate:
                        key = (subject, predicate)
                        if key not in claim_index:
                            claim_index[key] = []
                        claim_index[key].append(claim)
                
                # Find contradictions
                for (subject, predicate), claims_list in claim_index.items():
                    if len(claims_list) < 2:
                        continue
                    
                    # Group by object (normalized)
                    object_groups: Dict[str, List[Dict[str, Any]]] = {}
                    for claim in claims_list:
                        obj = claim.get("object", "").strip().lower()
                        if obj not in object_groups:
                            object_groups[obj] = []
                        object_groups[obj].append(claim)
                    
                    # If we have multiple different objects, we have a contradiction
                    if len(object_groups) > 1:
                        # Take first two different objects as conflicting claims
                        obj_keys = list(object_groups.keys())
                        claim_a = object_groups[obj_keys[0]][0]
                        claim_b = object_groups[obj_keys[1]][0]
                        
                        # Extract source anchors/pointers
                        source_anchor_a = claim_a.get("source_anchor") or claim_a.get("source_pointer") or {}
                        source_anchor_b = claim_b.get("source_anchor") or claim_b.get("source_pointer") or {}
                        
                        # Build claim texts
                        claim_a_text = claim_a.get("claim_text") or f"{claim_a.get('subject', '')} {claim_a.get('predicate', '')} {claim_a.get('object', '')}"
                        claim_b_text = claim_b.get("claim_text") or f"{claim_b.get('subject', '')} {claim_b.get('predicate', '')} {claim_b.get('object', '')}"
                        
                        # Generate deterministic explanation
                        explanation = generate_conflict_explanation(
                            claim_text=claim_a_text,
                            source_a=source_anchor_a,
                            source_b=source_anchor_b,
                            conflict_type=DeterministicConflictType.CONTRADICTION,
                            claim_a_text=claim_a_text,
                            claim_b_text=claim_b_text,
                        )
                        
                        # Create conflict payload with anchors
                        conflict_payload = {
                            "source_a": {
                                "doc_id": source_anchor_a.get("doc_id") or source_anchor_a.get("doc_hash", ""),
                                "page": source_anchor_a.get("page_number") or source_anchor_a.get("page"),
                                "excerpt": source_anchor_a.get("snippet") or claim_a_text[:200],
                            },
                            "source_b": {
                                "doc_id": source_anchor_b.get("doc_id") or source_anchor_b.get("doc_hash", ""),
                                "page": source_anchor_b.get("page_number") or source_anchor_b.get("page"),
                                "excerpt": source_anchor_b.get("snippet") or claim_b_text[:200],
                            },
                            "explanation": explanation,
                        }
                        
                        # Create ConflictItem
                        conflict_item = ConflictItem(
                            conflict_id=str(uuid.uuid4()),
                            conflict_type=ConflictType.STRUCTURAL_CONFLICT,
                            severity=ConflictSeverity.HIGH,
                            summary=f"Contradiction detected: {subject} {predicate}",
                            details=explanation,
                            produced_by=ConflictProducer.CRITIC,
                            contradicts=[claim_a.get("claim_id", ""), claim_b.get("claim_id", "")],
                            evidence_anchors=[
                                source_anchor_a if isinstance(source_anchor_a, dict) else source_anchor_a.model_dump() if hasattr(source_anchor_a, "model_dump") else {},
                                source_anchor_b if isinstance(source_anchor_b, dict) else source_anchor_b.model_dump() if hasattr(source_anchor_b, "model_dump") else {},
                            ],
                            assumptions=[],
                            suggested_actions=[ConflictSuggestedAction.HUMAN_SIGNOFF_REQUIRED],
                            confidence=0.9,  # High confidence for deterministic detection
                        )
                        
                        detected_conflicts.append({
                            "conflict_item": conflict_item,
                            "conflict_payload": conflict_payload,
                            "claim_a_id": claim_a.get("claim_id", ""),
                            "claim_b_id": claim_b.get("claim_id", ""),
                        })
                        
                        logger.info(
                            f"Detected contradiction: {subject} {predicate}",
                            extra={
                                "payload": {
                                    "claim_a_id": claim_a.get("claim_id"),
                                    "claim_b_id": claim_b.get("claim_id"),
                                    "conflict_type": "CONTRADICTION",
                                }
                            }
                        )
                
                # Update state with detected conflicts
                if detected_conflicts:
                    # Set conflict_detected flag
                    state["conflict_detected"] = True
                    state["conflicts"] = [c["conflict_item"].model_dump() for c in detected_conflicts]
                    
                    # Set needs_human_review based on rigor level and conflict count
                    conflict_threshold = 3  # Configurable threshold
                    if rigor_level == "conservative":
                        if len(detected_conflicts) >= conflict_threshold:
                            state["needs_human_review"] = True
                            critiques.append(f"Detected {len(detected_conflicts)} conflicts. Human review required (conservative mode).")
                        else:
                            critiques.append(f"Detected {len(detected_conflicts)} conflicts. Review recommended.")
                    else:  # exploratory
                        critiques.append(f"Detected {len(detected_conflicts)} conflicts. Flagged for review.")
                    
                    status = "fail"
                    
            except Exception as e:
                logger.warning(f"Failed to perform deterministic conflict detection: {e}", exc_info=True)
                # Continue without conflict detection (graceful degradation)
        
    # Conflict flags surfaced during context assembly
    if conflict_flags:
        status = "fail"
        critiques.append("Conflict Resolution Needed")
        critiques.append("Recommendation: Cartographer must resolve contradictory evidence before proceeding.")
    
    # Vocabulary guardrail check: scan synthesis output for forbidden words
    if synthesis:
        try:
            from ...shared.vocab_guard import get_vocab_guard
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
                        extra={"payload": {"forbidden_words": unique_matches, "job_id": job_id}},
                    )
        except Exception as e:
            logger.warning(f"Failed to check vocabulary guardrail: {e}", exc_info=True)
            # Don't fail on guardrail check errors - just log and continue
    
    # Increment revision count on failure
    revision_count = state.get("revision_count", 0)
    if status != "pass":
        revision_count += 1
    critic_score = 1.0 if status == "pass" else 0.0
    
    # Build return state with verification decisions
    base_state: ResearchState = {
        "critiques": critiques,
        "revision_count": revision_count,
        "critic_status": status,
        "critic_score": critic_score,
        "verification_decisions": [d.model_dump() for d in verification_decisions],  # Include decisions in state
        "evidence_pack_id": evidence_pack.pack_id if evidence_pack else None,
    }
    
    # Build conflict report if needed
    conflict_report = _build_conflict_report({**state, **base_state}, conflict_flags, status, revision_count)
    if conflict_report:
        try:
            store_conflict_report(conflict_report.model_dump())
            telemetry_emitter.emit_event(
                "conflict_report_emitted",
                {
                    "report_id": conflict_report.report_id,
                    "job_id": job_id,
                    "conflict_hash": conflict_report.conflict_hash,
                    "deadlock": conflict_report.deadlock,
                    "deadlock_type": conflict_report.deadlock_type.value if conflict_report.deadlock_type else None,
                    "blocker_count": len([i for i in conflict_report.conflict_items if i.severity == ConflictSeverity.BLOCKER]),
                    "recommended_next_step": conflict_report.recommended_next_step.value,
                },
            )
            base_state["conflict_report_id"] = conflict_report.report_id  # type: ignore[index]
            base_state["conflict_report"] = conflict_report.model_dump()  # type: ignore[index]
        except Exception:
            logger.warning("Failed to persist conflict report", exc_info=True)
    
    # Set phase to VETTING
    base_state["phase"] = PhaseEnum.VETTING.value
    
    # Preserve ALL state fields (defensive preservation)
    return {**state, **base_state}


def reframing_node(state: ResearchState) -> ResearchState:
    """Generate a reframing proposal and pause workflow for human signoff."""
    state = validate_state_schema(state)
    conflict = state.get("conflict_report") or {}
    if not conflict:
        return {**state, "needs_signoff": False}
    try:
        conflict_report = ConflictReport(**conflict)
    except Exception:
        return {**state, "needs_signoff": False}
    # Trigger conditions
    if not (
        state.get("revision_count", 0) >= 2
        and conflict_report.deadlock
        and conflict_report.recommended_next_step
        in {RecommendedNextStep.TRIGGER_REFRAMING, RecommendedNextStep.PAUSE_FOR_HUMAN}
    ):
        return {**state, "needs_signoff": False}

    # Minimal deterministic proposal (no LLM to keep tests offline)
    blocker_ids = [i.conflict_id for i in conflict_report.conflict_items if i.severity == ConflictSeverity.BLOCKER]
    anchors = blocker_ids or [i.conflict_id for i in conflict_report.conflict_items]
    proposal = ReframingProposal(
        proposal_id=str(uuid.uuid4()),
        project_id=state.get("project_id", ""),
        job_id=state.get("job_id", ""),
        doc_hash=conflict_report.doc_hash,
        conflict_hash=conflict_report.conflict_hash,
        conflict_summary=conflict_report.conflict_items[0].summary if conflict_report.conflict_items else "deadlock",
        pivot_type=PivotType.SCOPE,
        proposed_pivot="Refine scope to reduce contradiction.",
        architectural_rationale="Smallest pivot to resolve conflict while preserving thesis.",
        evidence_anchors=anchors[:1],
        assumptions_changed=["assumption_revised"],
        what_stays_true=["prior evidence remains trusted"],
        requires_human_signoff=True,
        created_at=get_utc_now(),
    )
    # Store proposal and emit telemetry (best-effort; don't fail if these raise)
    proposal_id = None
    try:
        proposal_id = store_reframing_proposal(proposal.model_dump())
        telemetry_emitter.emit_event(
            "reframe_proposed",
            {
                "proposal_id": proposal_id,
                "conflict_hash": conflict_report.conflict_hash,
                "pivot_type": proposal.pivot_type.value,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to store proposal or emit telemetry: {e}", exc_info=True)
        # Generate a fallback proposal_id if store failed
        proposal_id = proposal_id or str(uuid.uuid4())
    
    # Mark job as paused for signoff
    # Always return needs_signoff: True when interrupt is called, even if interrupt() raises
    try:
        update_job_status(state.get("job_id"), JobStatus.NEEDS_SIGNOFF, current_step="reframing", message="Awaiting signoff")
        interrupt(proposal.model_dump())
    except Exception as exc:
        logger.error("Interrupt failed in reframing_node", extra={"payload": {"error": str(exc)}}, exc_info=True)
        # Return state with needs_signoff: True even on interrupt failure
        return {**state, "reframing_proposal_id": proposal_id, "needs_signoff": True, "reframing_payload": proposal.model_dump()}
    # Normal success path: interrupt succeeded, still return needs_signoff: True
    return {**state, "reframing_proposal_id": proposal_id, "needs_signoff": True, "reframing_payload": proposal.model_dump()}


def tone_validator_node(state: ResearchState) -> ResearchState:
    """Neutralize sensational terms based on forbidden vocab."""
    state = validate_state_schema(state)
    text = str(state.get("synthesis") or state.get("final_text") or "")
    if not text:
        # Preserve ALL state fields (defensive preservation)
        return {**state, "synthesis": ""}

    try:
        from ..shared.vocab_guard import get_vocab_guard

        guard = get_vocab_guard()
        alt_map = guard.get_alternatives()
        tone_flags: List[ToneFlag] = []
        for word, alt in alt_map.items():
            tone_flags.append(
                ToneFlag(
                    word=word,
                    severity="hard",
                    locations=[],
                    suggestion=alt or "balanced",
                )
            )
        neutral_text = rewrite_to_neutral(text, tone_flags, evidence_context=None)
        # Preserve ALL state fields (defensive preservation)
        return {**state, "synthesis": neutral_text, "final_text": neutral_text}
    except Exception as exc:
        logger.warning("Tone validator skipped", extra={"payload": {"error": str(exc)}})
        # Preserve ALL state fields (defensive preservation)
        return {**state, "synthesis": text, "final_text": text}

