import hashlib
import json
from typing import List, Dict, Any

from .schema import ConflictReport


def _normalize_field(val: Any) -> Any:
    if isinstance(val, str):
        return val.strip().lower()
    if isinstance(val, list):
        return [_normalize_field(v) for v in val]
    if isinstance(val, dict):
        return {k: _normalize_field(v) for k, v in val.items()}
    return val


def compute_conflict_hash(report: ConflictReport) -> str:
    """Deterministic hash over conflict_items to detect persistent conflicts."""
    items: List[Dict[str, Any]] = []
    for item in report.conflict_items:
        anchors = []
        for ref in item.evidence_anchors:
            anchors.append(
                {
                    "doc_hash": ref.doc_hash,
                    "page": ref.page,
                    "bbox": ref.bbox,
                }
            )
        payload = {
            "type": item.conflict_type.value,
            "severity": item.severity.value,
            "contradicts": sorted(item.contradicts or []),
            "anchors": sorted(anchors, key=lambda a: (a["doc_hash"], a["page"], json.dumps(a["bbox"]))),
            "assumptions": sorted([_normalize_field(a) for a in item.assumptions]),
        }
        items.append(payload)
    items_sorted = sorted(items, key=lambda i: json.dumps(i, sort_keys=True))
    normalized = _normalize_field(items_sorted)
    blob = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
