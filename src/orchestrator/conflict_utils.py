"""
Utilities for generating deterministic conflict explanations and payloads.

This module provides functions to extract conflict information from claims
and generate deterministic explanations without LLM calls.
"""

from typing import Dict, Any, Optional, List
from ..shared.schema import ConflictItem, SourcePointer


def generate_conflict_explanation(
    claim_text: str,
    source_a: SourcePointer,
    source_b: SourcePointer,
    conflict_type: Optional[str] = None,
) -> str:
    """Generate a deterministic conflict explanation from claim and source metadata.
    
    This function creates explanations based on extracted claim text and citation
    metadata, without any LLM calls. The explanation is deterministic and reproducible.
    
    Args:
        claim_text: The claim text (e.g., "Subject predicate Object")
        source_a: Source pointer for the first source
        source_b: Source pointer for the second source
        conflict_type: Optional conflict type (e.g., "STRUCTURAL_CONFLICT")
    
    Returns:
        Deterministic explanation string
    """
    # Extract page numbers
    page_a = source_a.get("page") if isinstance(source_a, dict) else getattr(source_a, "page", None)
    page_b = source_b.get("page") if isinstance(source_b, dict) else getattr(source_b, "page", None)
    
    # Extract doc hashes (shortened for readability)
    doc_hash_a = source_a.get("doc_hash") if isinstance(source_a, dict) else getattr(source_a, "doc_hash", None)
    doc_hash_b = source_b.get("doc_hash") if isinstance(source_b, dict) else getattr(source_b, "doc_hash", None)
    
    # Build explanation based on available metadata
    parts = []
    
    # Start with claim context
    if claim_text:
        # Truncate claim if too long
        claim_short = claim_text[:60] + "..." if len(claim_text) > 60 else claim_text
        parts.append(f"Claim '{claim_short}'")
    
    # Add source A information
    source_a_desc = []
    if page_a:
        source_a_desc.append(f"page {page_a}")
    if doc_hash_a:
        short_hash = doc_hash_a[:8] + "..." if len(doc_hash_a) > 8 else doc_hash_a
        source_a_desc.append(f"doc {short_hash}")
    
    if source_a_desc:
        parts.append(f"asserted by Source A ({', '.join(source_a_desc)})")
    else:
        parts.append("asserted by Source A")
    
    # Add source B information
    source_b_desc = []
    if page_b:
        source_b_desc.append(f"page {page_b}")
    if doc_hash_b:
        short_hash = doc_hash_b[:8] + "..." if len(doc_hash_b) > 8 else doc_hash_b
        source_b_desc.append(f"doc {short_hash}")
    
    if source_b_desc:
        parts.append(f"contradicted by Source B ({', '.join(source_b_desc)})")
    else:
        parts.append("contradicted by Source B")
    
    # Add conflict type if provided
    if conflict_type:
        conflict_type_readable = conflict_type.replace("_", " ").title()
        parts.append(f"({conflict_type_readable})")
    
    explanation = ", ".join(parts) + "."
    
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
            "explanation": str
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
    conflict_type: Optional[str] = None
    
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
        
        # Get conflict type
        if hasattr(conflict_item, "conflict_type"):
            conflict_type = conflict_item.conflict_type.value if hasattr(conflict_item.conflict_type, "value") else str(conflict_item.conflict_type)
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
    
    # Generate deterministic explanation
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
        "explanation": explanation,
    }
    
    # Remove None values
    payload["source_a"] = {k: v for k, v in payload["source_a"].items() if v is not None and v != ""}
    payload["source_b"] = {k: v for k, v in payload["source_b"].items() if v is not None and v != ""}
    
    return payload

