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
    
    Args:
        triples: List of triple dictionaries.
    
    Returns:
        List of edge dictionaries with source, target, label, evidence, confidence.
    """
    edges = []
    
    for triple in triples:
        if not isinstance(triple, dict):
            continue
        
        subject = triple.get("subject", "")
        obj = triple.get("object", "")
        
        if subject and obj:
            edges.append({
                "source": subject,
                "target": obj,
                "label": triple.get("predicate", ""),
                "evidence": triple.get("evidence", ""),
                "confidence": triple.get("confidence", 0.0),
            })
    
    return edges

