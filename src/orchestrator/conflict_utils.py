"""
Utilities for generating deterministic conflict explanations and payloads.

This module provides functions to extract conflict information from claims
and generate deterministic explanations without LLM calls.

All explanations use enum-based conflict types and template-based formatting
to ensure determinism and repeatability.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from ..shared.schema import ConflictItem, SourcePointer, ConflictType


# Conflict type enum for deterministic explanations
class DeterministicConflictType(str, Enum):
    """Deterministic conflict types for template-based explanations."""
    CONTRADICTION = "CONTRADICTION"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    AMBIGUOUS = "AMBIGUOUS"
    OUTDATED = "OUTDATED"


# Template-based explanation generators
_CONFLICT_TEMPLATES = {
    DeterministicConflictType.CONTRADICTION: (
        "Source A (page {page_a}) asserts '{claim_a}', "
        "while Source B (page {page_b}) asserts '{claim_b}'. "
        "These statements contradict each other."
    ),
    DeterministicConflictType.MISSING_EVIDENCE: (
        "Claim '{claim}' lacks sufficient evidence. "
        "Source A (page {page_a}) provides partial support, "
        "but Source B (page {page_b}) does not confirm this claim."
    ),
    DeterministicConflictType.AMBIGUOUS: (
        "Claim '{claim}' is ambiguous. "
        "Source A (page {page_a}) and Source B (page {page_b}) "
        "provide conflicting interpretations."
    ),
    DeterministicConflictType.OUTDATED: (
        "Claim '{claim}' may be outdated. "
        "Source A (page {page_a}) provides an earlier assertion, "
        "while Source B (page {page_b}) provides a more recent one."
    ),
}


def _map_conflict_type_to_deterministic(conflict_type: Optional[Any]) -> DeterministicConflictType:
    """Map ConflictType enum to deterministic conflict type.
    
    Args:
        conflict_type: ConflictType enum value, DeterministicConflictType enum, or string.
    
    Returns:
        DeterministicConflictType enum value.
    """
    if conflict_type is None:
        return DeterministicConflictType.CONTRADICTION
    
    # If already a DeterministicConflictType, return it directly
    if isinstance(conflict_type, DeterministicConflictType):
        return conflict_type
    
    # Handle enum
    if hasattr(conflict_type, "value"):
        conflict_type = conflict_type.value
    elif not isinstance(conflict_type, str):
        conflict_type = str(conflict_type)
    
    conflict_type_upper = conflict_type.upper()
    
    # Check if it's already a DeterministicConflictType value
    try:
        return DeterministicConflictType(conflict_type_upper)
    except ValueError:
        pass
    
    # Map ConflictType enum values to deterministic types
    if conflict_type_upper in (
        "STRUCTURAL_CONFLICT",
        "INCOMPATIBLE_ASSUMPTIONS",
        "NUMERICAL_INCONSISTENCY",
        "ONTOLOGY_COLLISION",
    ):
        return DeterministicConflictType.CONTRADICTION
    elif conflict_type_upper in (
        "EVIDENCE_BINDING_FAILURE",
        "UNSUPPORTED_CORE_CLAIM",
    ):
        return DeterministicConflictType.MISSING_EVIDENCE
    elif conflict_type_upper == "SCOPE_MISMATCH":
        return DeterministicConflictType.AMBIGUOUS
    else:
        # Default to CONTRADICTION
        return DeterministicConflictType.CONTRADICTION


def generate_conflict_explanation(
    claim_text: str,
    source_a: SourcePointer,
    source_b: SourcePointer,
    conflict_type: Optional[Any] = None,
    claim_a_text: Optional[str] = None,
    claim_b_text: Optional[str] = None,
) -> str:
    """Generate a deterministic conflict explanation using templates.
    
    This function creates explanations based on extracted claim text and citation
    metadata, using enum-based conflict types and template-based formatting.
    No LLM calls are made. The explanation is deterministic and reproducible.
    
    Args:
        claim_text: The claim text (e.g., "Subject predicate Object") - used as fallback
        source_a: Source pointer for the first source
        source_b: Source pointer for the second source
        conflict_type: Optional ConflictType enum or string (mapped to deterministic type)
        claim_a_text: Optional claim text from source A (for CONTRADICTION)
        claim_b_text: Optional claim text from source B (for CONTRADICTION)
    
    Returns:
        Deterministic explanation string using templates
    """
    # Map conflict type to deterministic enum
    det_type = _map_conflict_type_to_deterministic(conflict_type)
    
    # Extract page numbers
    page_a = source_a.get("page") if isinstance(source_a, dict) else getattr(source_a, "page", None)
    page_b = source_b.get("page") if isinstance(source_b, dict) else getattr(source_b, "page", None)
    
    # Truncate claim if too long
    claim_short = claim_text[:60] + "..." if len(claim_text) > 60 else claim_text
    claim_a_short = (claim_a_text[:60] + "..." if claim_a_text and len(claim_a_text) > 60 else claim_a_text) or claim_short
    claim_b_short = (claim_b_text[:60] + "..." if claim_b_text and len(claim_b_text) > 60 else claim_b_text) or claim_short
    
    # Get template for this conflict type
    template = _CONFLICT_TEMPLATES[det_type]
    
    # Format template with available data
    # Use defaults if page numbers are missing
    page_a_str = str(page_a) if page_a is not None else "unknown"
    page_b_str = str(page_b) if page_b is not None else "unknown"
    
    # Format based on template requirements
    if det_type == DeterministicConflictType.CONTRADICTION:
        explanation = template.format(
            claim_a=claim_a_short,
            claim_b=claim_b_short,
            page_a=page_a_str,
            page_b=page_b_str,
        )
    else:
        explanation = template.format(
            claim=claim_short,
            page_a=page_a_str,
            page_b=page_b_str,
        )
    
    return explanation


def extract_conflict_payload(
    triple: Dict[str, Any],
    conflict_item: Optional[ConflictItem] = None,
    all_triples: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Extract conflict payload for a flagged claim.
    
    Args:
        triple: The triple/claim dictionary
        conflict_item: Optional ConflictItem from conflict report
        all_triples: Optional list of all triples (for finding contradicting claims)
    
    Returns:
        Conflict payload dictionary or None if no conflict:
        {
            "source_a": {
                "doc_id": str,
                "page": int,
                "excerpt": str
            },
            "source_b": {
                "doc_id": str,
                "page": int,
                "excerpt": str
            },
            "explanation": str (template-based, deterministic)
        }
    """
    # Check if claim is flagged
    conflict_flags = triple.get("conflict_flags", [])
    if not conflict_flags:
        return None
    
    # Get source pointer from triple
    source_pointer_a = triple.get("source_pointer") or {}
    if not isinstance(source_pointer_a, dict):
        source_pointer_a = {}
    
    # Extract claim text
    subject = triple.get("subject", "")
    predicate = triple.get("predicate", "")
    obj = triple.get("object", "")
    claim_text = f"{subject} {predicate} {obj}".strip()
    
    # Try to get conflict data from conflict_item
    source_pointer_b: Dict[str, Any] = {}
    conflict_type: Optional[Any] = None
    
    if conflict_item:
        # Use evidence_anchors from conflict_item
        evidence_anchors = conflict_item.evidence_anchors if hasattr(conflict_item, "evidence_anchors") else []
        if isinstance(conflict_item, dict):
            evidence_anchors = conflict_item.get("evidence_anchors", [])
        
        if evidence_anchors and len(evidence_anchors) >= 2:
            # Find which anchor matches source_pointer_a
            anchor_a = None
            anchor_b = None
            
            for anchor in evidence_anchors:
                anchor_dict = anchor if isinstance(anchor, dict) else anchor.model_dump() if hasattr(anchor, "model_dump") else {}
                anchor_doc = anchor_dict.get("doc_hash")
                anchor_page = anchor_dict.get("page")
                
                source_doc = source_pointer_a.get("doc_hash")
                source_page = source_pointer_a.get("page")
                
                # Match by doc_hash and page if available
                if anchor_doc == source_doc and (not source_page or anchor_page == source_page):
                    anchor_a = anchor_dict
                else:
                    anchor_b = anchor_dict if anchor_b is None else anchor_b
            
            # If we didn't find a match, use first two anchors
            if not anchor_a and evidence_anchors:
                anchor_a = evidence_anchors[0]
                anchor_a = anchor_a if isinstance(anchor_a, dict) else anchor_a.model_dump() if hasattr(anchor_a, "model_dump") else {}
                if len(evidence_anchors) > 1:
                    anchor_b = evidence_anchors[1]
                    anchor_b = anchor_b if isinstance(anchor_b, dict) else anchor_b.model_dump() if hasattr(anchor_b, "model_dump") else {}
            
            if anchor_b:
                source_pointer_b = anchor_b
        
        # Get conflict type (must use enum, not LLM-generated string)
        if hasattr(conflict_item, "conflict_type"):
            conflict_type = conflict_item.conflict_type  # Use enum directly
        elif isinstance(conflict_item, dict):
            conflict_type = conflict_item.get("conflict_type")
            if isinstance(conflict_type, dict):
                conflict_type = conflict_type.get("value")
    
    # If we don't have source_b yet, try to find contradicting claim
    if not source_pointer_b and all_triples:
        # Look for a contradicting triple with different source
        for other_triple in all_triples:
            if other_triple == triple:
                continue
            
            other_subject = other_triple.get("subject", "")
            other_object = other_triple.get("object", "")
            other_source = other_triple.get("source_pointer") or {}
            
            # Check if this might be a contradiction
            # Simple heuristic: same subject/object but different predicate or inverted
            if (other_subject == subject and other_object == obj) or (other_subject == obj and other_object == subject):
                other_doc = other_source.get("doc_hash") if isinstance(other_source, dict) else None
                source_doc = source_pointer_a.get("doc_hash")
                
                # If different document, use as source_b
                if other_doc and other_doc != source_doc:
                    source_pointer_b = other_source if isinstance(other_source, dict) else {}
                    break
    
    # If still no source_b, create placeholder
    if not source_pointer_b:
        source_pointer_b = {}
    
    # Generate deterministic explanation using templates (NO LLM CALLS)
    explanation = generate_conflict_explanation(
        claim_text=claim_text,
        source_a=source_pointer_a,
        source_b=source_pointer_b,
        conflict_type=conflict_type,
    )
    
    # Build conflict payload
    payload = {
        "source_a": {
            "doc_id": source_pointer_a.get("doc_hash", ""),
            "page": source_pointer_a.get("page"),
            "excerpt": source_pointer_a.get("snippet", source_pointer_a.get("evidence", "")),
        },
        "source_b": {
            "doc_id": source_pointer_b.get("doc_hash", "") if source_pointer_b else "",
            "page": source_pointer_b.get("page") if source_pointer_b else None,
            "excerpt": source_pointer_b.get("snippet", source_pointer_b.get("evidence", "")) if source_pointer_b else "",
        },
        "explanation": explanation,  # Template-based, deterministic
    }
    
    # Remove None values
    payload["source_a"] = {k: v for k, v in payload["source_a"].items() if v is not None and v != ""}
    payload["source_b"] = {k: v for k, v in payload["source_b"].items() if v is not None and v != ""}
    
    return payload
