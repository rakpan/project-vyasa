"""Artifact manifest builder and persistence utilities."""

import json
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...shared.schema import (
    ArtifactManifest,
    BlockStats,
    TableArtifact,
    VisualArtifact,
)
from ...shared.schema import ToneFlag  # re-export for typing
from ...shared.logger import get_logger
from ...shared.rigor_config import load_rigor_policy_yaml
from ..guards.tone_guard import scan_text
from ..guards.precision_guard import check_table_precision
from ...shared.utils import get_utc_now, ensure_utc_datetime
from ...shared.config import get_artifact_root

logger = get_logger("orchestrator", __name__)

ARTIFACT_ROOT = Path(get_artifact_root())


def _word_count(text: str) -> int:
    return len((text or "").split())


def build_block_stats(block: Dict[str, Any]) -> BlockStats:
    content = block.get("content", "") or ""
    tone_flags = scan_text(content)
    return BlockStats(
        block_id=block.get("block_id", ""),
        section=block.get("section_title") or block.get("section"),
        word_count=_word_count(content),
        citation_count=len(block.get("citation_keys") or []),
        claims_density=block.get("claims_density"),
        tone_flags=tone_flags,
        supported_by=block.get("claim_ids") or block.get("supported_by") or [],
    )


def _gather_tables(state: Dict[str, Any], max_decimals: int) -> List[TableArtifact]:
    table_objs: List[Dict[str, Any]] = []
    for key in ("structured_tables", "tables"):
        candidate = state.get(key)
        if isinstance(candidate, list):
            table_objs.extend([t for t in candidate if isinstance(t, dict)])
    artifacts: List[TableArtifact] = []
    for idx, table in enumerate(table_objs):
        table_id = table.get("table_id") or f"table_{idx}"
        precision_flags = check_table_precision(table, max_decimals_default=max_decimals)
        artifacts.append(
            TableArtifact(
                table_id=table_id,
                title=table.get("title"),
                source_triples=table.get("source_triples") or [],
                unit_verification=table.get("unit_verification", "unknown"),
                precision_flags=precision_flags,
            )
        )
    return artifacts


def _gather_visuals(state: Dict[str, Any]) -> List[VisualArtifact]:
    visuals: List[VisualArtifact] = []
    vision_results = state.get("vision_results") or []
    if isinstance(vision_results, list):
        for idx, item in enumerate(vision_results):
            if not isinstance(item, dict):
                continue
            artifact_id = item.get("artifact_id") or f"vision_{idx}"
            kind = item.get("kind") or "figure"
            caption = item.get("caption")
            visuals.append(
                VisualArtifact(
                    artifact_id=artifact_id,
                    kind=kind,
                    source_bbox=item.get("bbox"),
                    generation_seed=item.get("seed"),
                    caption=caption,
                )
            )
    return visuals


def _infer_doc_hash(state: Dict[str, Any]) -> str:
    doc_hash = state.get("doc_hash") or state.get("pdf_hash")
    if doc_hash:
        return str(doc_hash)
    raw_text = state.get("raw_text") or ""
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest() if raw_text else "unknown"


def build_manifest(
    state: Dict[str, Any],
    persisted_objects: Optional[Dict[str, Any]] = None,
    rigor_level: Optional[str] = None,
) -> ArtifactManifest:
    policy = load_rigor_policy_yaml()
    rigor = rigor_level or policy.get("rigor_level", "exploratory")
    if rigor == "conservative":
        max_decimals = 2
    else:
        max_decimals = int(policy.get("max_decimals_default", 3))

    blocks_raw = state.get("manuscript_blocks")
    if not isinstance(blocks_raw, list):
        blocks_raw = []
    blocks: List[BlockStats] = []
    for b in blocks_raw:
        if isinstance(b, dict):
            blocks.append(build_block_stats(b))

    tables = _gather_tables(state, max_decimals=max_decimals)
    visuals = _gather_visuals(state)

    totals = {
        "words": sum(b.word_count for b in blocks),
        "citations": sum(b.citation_count for b in blocks),
        "figures": len(visuals),
        "tables": len(tables),
    }

    project_id = state.get("project_id", "")
    job_id = state.get("job_id", "")
    doc_hash = _infer_doc_hash(state)
    created_at = ensure_utc_datetime(state.get("created_at"))

    return ArtifactManifest(
        project_id=project_id,
        job_id=job_id,
        doc_hash=doc_hash,
        created_at=created_at,
        rigor_level=rigor,  # type: ignore[arg-type]
        blocks=blocks,
        tables=tables,
        visuals=visuals,
        totals=totals,
    )


def persist_manifest(
    manifest: ArtifactManifest,
    db: Any,
    telemetry_emitter: Optional[Any] = None,
    artifact_root: Path = ARTIFACT_ROOT,
) -> None:
    """Persist manifest to DB and filesystem; emit telemetry if provided."""
    if not manifest.project_id or not manifest.job_id:
        raise ValueError("Manifest must include project_id and job_id")

    # DB persistence
    if db is not None:
        if not db.has_collection("artifact_manifests"):
            db.create_collection("artifact_manifests")
        coll = db.collection("artifact_manifests")
        coll.insert(manifest.model_dump(mode="json"))

    # Filesystem persistence
    out_dir = artifact_root / manifest.project_id / manifest.job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "artifact_manifest.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(manifest.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

    # Telemetry
    if telemetry_emitter:
        telemetry_emitter.emit_event(
            "artifact_manifest_written",
            {
                "job_id": manifest.job_id,
                "project_id": manifest.project_id,
                "total_words": manifest.totals.get("words", 0),
                "tone_flag_count": sum(len(b.tone_flags) for b in manifest.blocks),
                "table_count": manifest.totals.get("tables", 0),
                "figure_count": manifest.totals.get("figures", 0),
            },
        )
