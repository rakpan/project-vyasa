"""
Normalization utilities for extracted JSON to ensure consistent structure.

This module provides functions to normalize various JSON shapes from model outputs
into a consistent format expected by the console, specifically guaranteeing
a `triples` array is always present.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def normalize_extracted_json(raw: Any) -> Dict[str, Any]:
    """Normalize extracted JSON to guarantee `triples` array structure.
    
    Takes various JSON shapes from model outputs and normalizes them to a
    consistent format with a guaranteed `triples` array. This ensures the
    console can always find `extracted_json.triples` regardless of model output.
    
    Supported input formats:
    - Already correct: {"triples": [...]}
    - List of lists: [["subject", "predicate", "object"], ...]
    - Alternative keys: {"relations": [...]} or {"edges": [...]}
    - String JSON: "{\"triples\": [...]}"
    - Invalid/missing: {} or None -> returns empty triples
    
    Args:
        raw: Raw JSON output from model. Can be dict, list, string, or None.
        
    Returns:
        Dict with guaranteed structure:
        {
            "triples": List[Dict] - Always present, even if empty
            "entities": List[Dict] - Optional, preserved if present
            "claims": List[Dict] - Optional, preserved if present
            "metadata": Dict - Optional, preserved if present
        }
        
    Examples:
        >>> normalize_extracted_json({"triples": [{"subject": "A", "predicate": "relates", "object": "B"}]})
        {"triples": [{"subject": "A", "predicate": "relates", "object": "B"}]}
        
        >>> normalize_extracted_json([["A", "relates", "B"]])
        {"triples": [{"subject": "A", "predicate": "relates", "object": "B"}]}
        
        >>> normalize_extracted_json({"relations": [...]})
        {"triples": [...], "relations": [...]}
    """
    if raw is None:
        logger.warning("Normalize: Received None, returning empty structure")
        return {"triples": []}
    
    # Handle string JSON
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"Normalize: Failed to parse JSON string: {e}")
            return {"triples": []}
    
    # Handle list of lists (tuple format)
    if isinstance(raw, list):
        if len(raw) > 0 and isinstance(raw[0], (list, tuple)):
            logger.info(f"Normalize: Converting list of {len(raw)} tuples to triples")
            triples = []
            for item in raw:
                if len(item) >= 3:
                    triple = {
                        "subject": str(item[0]),
                        "predicate": str(item[1]),
                        "object": str(item[2]),
                    }
                    if len(item) >= 4:
                        triple["evidence"] = str(item[3])
                    if len(item) >= 5:
                        triple["confidence"] = float(item[4]) if isinstance(item[4], (int, float)) else 0.0
                    else:
                        triple["confidence"] = 0.0
                    triples.append(triple)
            return {"triples": triples}
        else:
            # List of objects - assume they're triples
            logger.info(f"Normalize: Converting list of {len(raw)} objects to triples")
            triples = []
            for item in raw:
                if isinstance(item, dict):
                    # Normalize individual triple object
                    triple = {
                        "subject": str(item.get("subject", item.get("s", item.get("source", "")))),
                        "predicate": str(item.get("predicate", item.get("p", item.get("rel", item.get("relation", ""))))),
                        "object": str(item.get("object", item.get("o", item.get("target", "")))),
                        "confidence": float(item.get("confidence", item.get("conf", 0.0))),
                    }
                    if "evidence" in item or "evidence_span" in item:
                        triple["evidence"] = str(item.get("evidence", item.get("evidence_span", "")))
                    triples.append(triple)
            return {"triples": triples}
    
    # Handle dict
    if isinstance(raw, dict):
        result: Dict[str, Any] = {}
        
        # Find triples under various key names
        triples = None
        if "triples" in raw:
            triples = raw["triples"]
        elif "relations" in raw:
            triples = raw["relations"]
            logger.info("Normalize: Found 'relations' key, mapping to 'triples'")
        elif "edges" in raw:
            triples = raw["edges"]
            logger.info("Normalize: Found 'edges' key, mapping to 'triples'")
        elif "relationships" in raw:
            triples = raw["relationships"]
            logger.info("Normalize: Found 'relationships' key, mapping to 'triples'")
        
        # Normalize triples array
        if triples is None:
            logger.warning("Normalize: No triples found in dict, returning empty triples")
            result["triples"] = []
        elif isinstance(triples, list):
            normalized_triples = []
            for item in triples:
                if isinstance(item, dict):
                    # Already an object - ensure required fields
                    triple = {
                        "subject": str(item.get("subject", item.get("s", item.get("source", "")))),
                        "predicate": str(item.get("predicate", item.get("p", item.get("rel", item.get("relation", ""))))),
                        "object": str(item.get("object", item.get("o", item.get("target", "")))),
                        "confidence": float(item.get("confidence", item.get("conf", 0.0))),
                    }
                    if "evidence" in item or "evidence_span" in item:
                        triple["evidence"] = str(item.get("evidence", item.get("evidence_span", "")))
                    normalized_triples.append(triple)
                elif isinstance(item, (list, tuple)) and len(item) >= 3:
                    # Tuple format
                    triple = {
                        "subject": str(item[0]),
                        "predicate": str(item[1]),
                        "object": str(item[2]),
                        "confidence": float(item[3]) if len(item) >= 4 and isinstance(item[3], (int, float)) else 0.0,
                    }
                    if len(item) >= 5:
                        triple["evidence"] = str(item[4])
                    normalized_triples.append(triple)
            result["triples"] = normalized_triples
        else:
            logger.warning(f"Normalize: Triples is not a list (type: {type(triples)}), returning empty")
            result["triples"] = []
        
        # Preserve other keys
        for key, value in raw.items():
            if key not in ["triples", "relations", "edges", "relationships"]:
                result[key] = value
        
        return result
    
    # Unknown type
    logger.warning(f"Normalize: Unknown input type {type(raw)}, returning empty structure")
    return {"triples": []}
