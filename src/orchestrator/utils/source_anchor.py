"""
Utilities for converting source_pointer to source_anchor for UI context anchors.

source_anchor provides a UI-friendly structure for scrolling and highlighting
evidence spans in the Evidence pane.
"""

from typing import Dict, Any, Optional


def source_pointer_to_anchor(source_pointer: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Convert source_pointer to source_anchor format.
    
    Args:
        source_pointer: Source pointer dict with doc_hash, page, bbox, snippet
    
    Returns:
        source_anchor dict with:
        - doc_id: str (doc_hash)
        - page_number: int (1-based)
        - span: Optional[Dict] with start/end (if snippet available)
        - bbox: Optional[Dict] with x, y, w, h (if bbox available)
        or None if source_pointer is invalid
    """
    if not source_pointer or not isinstance(source_pointer, dict):
        return None
    
    doc_hash = source_pointer.get("doc_hash")
    page = source_pointer.get("page")
    
    # Require at least doc_hash and page
    if not doc_hash or page is None:
        return None
    
    anchor: Dict[str, Any] = {
        "doc_id": doc_hash,
        "page_number": int(page),
    }
    
    # Add bbox if available (convert from [x1,y1,x2,y2] to {x, y, w, h})
    bbox = source_pointer.get("bbox")
    if bbox and isinstance(bbox, list) and len(bbox) == 4:
        x1, y1, x2, y2 = bbox
        anchor["bbox"] = {
            "x": float(x1),
            "y": float(y1),
            "w": float(x2 - x1),
            "h": float(y2 - y1),
        }
    
    # Add span if snippet is available (for text-based highlighting)
    snippet = source_pointer.get("snippet")
    if snippet:
        # For now, we'll use snippet length as a proxy for span
        # In a full implementation, we'd compute actual character offsets
        anchor["span"] = {
            "start": 0,  # Placeholder - would be computed from actual text position
            "end": len(snippet),
        }
        anchor["snippet"] = snippet  # Include snippet for reference
    
    return anchor


def add_source_anchor_to_triple(triple: Dict[str, Any]) -> Dict[str, Any]:
    """Add source_anchor to a triple/claim dict if source_pointer exists.
    
    Args:
        triple: Triple/claim dict that may have source_pointer
    
    Returns:
        Triple dict with source_anchor added (if source_pointer was present)
    """
    source_pointer = triple.get("source_pointer")
    if source_pointer:
        anchor = source_pointer_to_anchor(source_pointer)
        if anchor:
            triple["source_anchor"] = anchor
    return triple


def add_source_anchor_to_triples(triples: list) -> list:
    """Add source_anchor to all triples in a list.
    
    Args:
        triples: List of triple/claim dicts
    
    Returns:
        List of triples with source_anchor added where applicable
    """
    return [add_source_anchor_to_triple(t) for t in triples]

