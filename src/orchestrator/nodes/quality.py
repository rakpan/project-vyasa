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
    raw_text = state.get("raw_text", "")
    synthesis = state.get("synthesis", "")
    
    # Debug logging for raw_text preservation at node entry
    job_id = state.get("jobId") or state.get("job_id")
    logger.debug(
        "Critic node entry",
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
    
    # Use wrap_prompt_with_context for consistent context injection
    # Apply context injection AFTER fetching from Opik
    system_prompt = wrap_prompt_with_context(state, system_template)
    
    # Add claim-specific context segments
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
            # Preserve ALL state fields (defensive preservation)
            return {
                **state,
                "critiques": critiques,
                "revision_count": revision_count,
                "critic_status": status,
                "critic_score": critic_score,
                "synthesis": synthesis_val,
            }
        except Exception:
            pass
        # Route to appropriate expert: Critic uses Brain (logic/reasoning) service
        expert_url, expert_name, expert_model = route_to_expert("critic_node", ExpertType.LOGIC_REASONING)
        decision = check_kv_backpressure(expert_url)
        if decision.get("action") == "retry_later":
            # Preserve ALL state fields (defensive preservation)
            return {**state, "critic_status": "retry_later", "error": "RETRY_LATER"}
        # soft delay already applied inside decision for >85%
        
        # Get role for allowed_tools
        role = role_registry.get_role("critic")
        
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

        # Deterministic conflict detection: detect contradictions using graph traversal
        detected_conflicts = []
        project_id = state.get("project_id")
        ingestion_id = state.get("ingestion_id")
        job_id = state.get("jobId") or state.get("job_id")
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
        conflict_flags = state.get("conflict_flags") or []
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
        enriched_state: ResearchState = {}
        if usage:
            enriched_state["_sglang_usage"] = usage  # type: ignore[index]
        enriched_state["_expert_name"] = meta.get("expert_name", expert_name)  # type: ignore[index]
        enriched_state["_expert_url"] = meta.get("url_base", expert_url)  # type: ignore[index]
        base_state: ResearchState = {
            **enriched_state,
            "critiques": critiques,
            "revision_count": revision_count,
            "critic_status": status,
            "critic_score": critic_score,
        }
        conflict_report = _build_conflict_report({**state, **base_state}, conflict_flags, status, revision_count)
        if conflict_report:
            try:
                store_conflict_report(conflict_report.model_dump())
                telemetry_emitter.emit_event(
                    "conflict_report_emitted",
                    {
                        "report_id": conflict_report.report_id,
                        "job_id": conflict_report.job_id,
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
    except Exception:
        logger.error(
            "Critic validation failed",
            extra={"payload": {"has_extracted": bool(extracted)}},
            exc_info=True,
        )
        # On failure to critique, force manual review path
        # Preserve ALL state fields (defensive preservation)
        revision_count = state.get("revision_count", 0) + 1
        return {
            **state,
            "critiques": ["Critic execution failed"],
            "revision_count": revision_count,
            "critic_status": "fail",
            "phase": PhaseEnum.VETTING.value,
        }


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

