"""
Triple transformation utilities for graph extraction.

Deterministic transforms that extract nodes and edges from triple structures.
Pure functions with no side effects.
"""

from typing import List, Dict, Any


def extract_nodes_from_triples(triples: list) -> list:
    """Extract unique nodes from triples.
    
    Args:
        triples: List of triple dictionaries.
    
    Returns:
        List of node dictionaries with id, label, type.
    """
    nodes_map: Dict[str, Dict[str, Any]] = {}
    
    for triple in triples:
        if not isinstance(triple, dict):
            continue
        
        subject = triple.get("subject", "")
        obj = triple.get("object", "")
        
        if subject and subject not in nodes_map:
            nodes_map[subject] = {
                "id": subject,
                "label": subject,
                "type": "entity",
            }
        
        if obj and obj not in nodes_map:
            nodes_map[obj] = {
                "id": obj,
                "label": obj,
                "type": "entity",
            }
    
    return list(nodes_map.values())


def extract_edges_from_triples(triples: list) -> list:
    """Extract edges from triples.
    
    Preserves source_anchor metadata through the "Anchor Thread" to ensure
    anchor information is available in ArangoDB edge documents.
    
    Args:
        triples: List of triple dictionaries (may be Claim instances or dicts).
    
    Returns:
        List of edge dictionaries with source, target, label, evidence, confidence,
        and source_anchor (if present).
    """
    edges = []
    
    for triple in triples:
        if not isinstance(triple, dict):
            continue
        
        subject = triple.get("subject", "")
        obj = triple.get("object", "")
        
        if subject and obj:
            edge = {
                "source": subject,
                "target": obj,
                "label": triple.get("predicate", ""),
                "evidence": triple.get("evidence", ""),
                "confidence": triple.get("confidence", 0.0),
            }
            
            # Preserve source_anchor in edge (Anchor Thread)
            if triple.get("source_anchor"):
                edge["source_anchor"] = triple["source_anchor"]
            elif triple.get("source_pointer"):
                # Convert source_pointer to source_anchor format for edge
                from ..schemas.claims import SourceAnchor
                sp = triple["source_pointer"]
                anchor_data = {
                    "doc_id": sp.get("doc_hash", ""),
                    "page_number": sp.get("page", 1),
                }
                # Add bbox if present
                bbox = sp.get("bbox")
                if bbox and isinstance(bbox, list) and len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    anchor_data["bbox"] = {
                        "x": float(x1),
                        "y": float(y1),
                        "w": float(x2 - x1),
                        "h": float(y2 - y1),
                    }
                # Add snippet if present
                if sp.get("snippet"):
                    anchor_data["snippet"] = sp.get("snippet")
                try:
                    edge["source_anchor"] = SourceAnchor(**anchor_data).model_dump()
                except Exception:
                    # If anchor validation fails, skip it but keep edge
                    pass
            
            edges.append(edge)
    
    return edges

