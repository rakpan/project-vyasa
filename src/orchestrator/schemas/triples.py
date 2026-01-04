"""
Triple schema aliases and utilities.

This module provides aliases and compatibility shims for triple structures.
The canonical Claim schema is in schemas/claims.py.
"""

from typing import Dict, Any, List
from .claims import Claim, SourceAnchor

# Alias: Triple is a Claim (for backward compatibility)
Triple = Claim

# Alias: TripleDict is a dict representation of a Claim
TripleDict = Dict[str, Any]


def triple_to_claim(triple: Dict[str, Any], ingestion_id: str, rigor_level: str = "exploratory") -> Claim:
    """Convert triple dictionary to Claim instance.
    
    Args:
        triple: Triple dictionary
        ingestion_id: Ingestion identifier
        rigor_level: Rigor level for validation
    
    Returns:
        Claim instance
    """
    return Claim.from_triple_dict(triple, ingestion_id, rigor_level)


def claim_to_triple_dict(claim: Claim) -> Dict[str, Any]:
    """Convert Claim instance to triple dictionary (for backward compatibility).
    
    Args:
        claim: Claim instance
    
    Returns:
        Triple dictionary with subject, predicate, object, etc.
    """
    result = {
        "subject": claim.subject,
        "predicate": claim.predicate,
        "object": claim.object,
        "confidence": claim.confidence,
        "rq_hits": claim.rq_hits,
        "file_hash": claim.file_hash,
        "claim_id": claim.claim_id,
        "ingestion_id": claim.ingestion_id,
    }
    
    # Add source_anchor as source_pointer for backward compatibility
    if claim.source_anchor:
        result["source_anchor"] = claim.source_anchor.model_dump()
        # Also add as source_pointer (convert bbox back to [x1,y1,x2,y2] format)
        source_pointer = {
            "doc_hash": claim.source_anchor.doc_id,
            "page": claim.source_anchor.page_number,
        }
        if claim.source_anchor.bbox:
            bbox = claim.source_anchor.bbox
            source_pointer["bbox"] = [
                bbox["x"],
                bbox["y"],
                bbox["x"] + bbox["w"],
                bbox["y"] + bbox["h"],
            ]
        if claim.source_anchor.snippet:
            source_pointer["snippet"] = claim.source_anchor.snippet
        result["source_pointer"] = source_pointer
    
    # Add optional fields
    if claim.claim_text:
        result["claim_text"] = claim.claim_text
    if claim.relevance_score is not None:
        result["relevance_score"] = claim.relevance_score
    if claim.is_expert_verified:
        result["is_expert_verified"] = True
    if claim.expert_notes:
        result["expert_notes"] = claim.expert_notes
    
    return result


__all__ = [
    "Triple",
    "TripleDict",
    "triple_to_claim",
    "claim_to_triple_dict",
]

