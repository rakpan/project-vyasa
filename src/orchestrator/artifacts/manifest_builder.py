"""Artifact manifest builder and persistence utilities."""

import json
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...shared.schema import (
    ArtifactManifest,
    ArtifactMetrics,
    BlockArtifact,
    TableArtifact,
    FigureArtifact,
)
from ...shared.schema import ToneFlag  # re-export for typing
from ...shared.logger import get_logger
from ...shared.rigor_config import load_rigor_policy_yaml
from ..guards.tone_guard import scan_text
from ..guards.precision_guard import check_table_precision
from ..guards.precision_contract import validate_table_precision
from ...shared.schema import PrecisionContract
from ...shared.utils import get_utc_now, ensure_utc_datetime
from ...shared.config import get_artifact_root

logger = get_logger("orchestrator", __name__)

ARTIFACT_ROOT = Path(get_artifact_root())


def _word_count(text: str) -> int:
    return len((text or "").split())


def _gather_tables(state: Dict[str, Any], max_decimals: int, rigor: str) -> List[TableArtifact]:
    table_objs: List[Dict[str, Any]] = []
    for key in ("structured_tables", "tables"):
        candidate = state.get(key)
        if isinstance(candidate, list):
            table_objs.extend([t for t in candidate if isinstance(t, dict)])
    artifacts: List[TableArtifact] = []
    for idx, table in enumerate(table_objs):
        table_id = table.get("table_id") or f"table_{idx}"
        rq_id = table.get("rq_id") or "general"
        source_claim_ids = table.get("source_claim_ids") or table.get("source_triples") or []
        precision_flags = check_table_precision(table, max_decimals_default=max_decimals)
        contract_dict = table.get("precision_contract") or {
            "max_decimals": max_decimals,
            "max_sig_figs": int(table.get("max_sig_figs") or 4),
            "rounding_rule": table.get("rounding_rule") or "half_up",
            "consistency_rule": table.get("consistency_rule") or "per_column",
        }
        contract = PrecisionContract(**contract_dict)
        rewritten_table, contract_flags, _warnings = validate_table_precision(table, contract, rigor=rigor)
        if contract_flags:
            precision_flags.extend(contract_flags)
        table = rewritten_table
        artifacts.append(
            TableArtifact(
                table_id=table_id,
                rq_id=rq_id,
                source_claim_ids=source_claim_ids,
                title=table.get("title"),
                precision_contract=contract_dict,
                flags=[f.issue for f in precision_flags] if precision_flags else [],
            )
        )
    return artifacts


def _gather_figures(state: Dict[str, Any]) -> List[FigureArtifact]:
    figures: List[FigureArtifact] = []
    vision_results = state.get("vision_results") or []
    if isinstance(vision_results, list):
        for idx, item in enumerate(vision_results):
            if not isinstance(item, dict):
                continue
            figure_id = item.get("artifact_id") or f"figure_{idx}"
            rq_id = item.get("rq_id") or "general"
            source_claim_ids = item.get("source_claim_ids") or []
            caption = item.get("caption")
            figures.append(
                FigureArtifact(
                    figure_id=figure_id,
                    rq_id=rq_id,
                    source_claim_ids=source_claim_ids,
                    caption=caption,
                    flags=[],
                )
            )
    return figures


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
    blocks: List[BlockArtifact] = []
    rq_links: set[str] = set()
    flags: List[str] = []
    for b in blocks_raw:
        if not isinstance(b, dict):
            continue
        rq_id = b.get("rq_id") or "general"
        content = b.get("content", "") or ""
        word_count = _word_count(content)
        claim_ids = b.get("claim_ids") or b.get("supported_by") or []
        citation_keys = b.get("citation_keys") or []
        tone_flags = scan_text(content)
        if rq_id != "general":
            rq_links.add(rq_id)
        blocks.append(
            BlockArtifact(
                block_id=b.get("block_id", ""),
                rq_id=rq_id,
                word_count=word_count,
                claim_ids=claim_ids,
                citation_keys=citation_keys,
                section=b.get("section_title") or b.get("section"),
                flags=[],
                tone_flags=tone_flags,
            )
        )

    tables = _gather_tables(state, max_decimals=max_decimals, rigor=rigor)
    figures = _gather_figures(state)

    total_words = sum(b.word_count for b in blocks)
    # claims are counted STRICTLY from block.claim_ids only, not from table/figure source_claim_ids
    # This ensures claim density reflects manuscript evidence, not artifact metadata
    total_claims = sum(len(b.claim_ids) if isinstance(b.claim_ids, list) else 0 for b in blocks)
    citation_count = sum(len(b.citation_keys) for b in blocks)
    claims_per_100_words = total_claims / (total_words / 100.0) if total_words > 0 else 0.0
    metrics = ArtifactMetrics(
        total_words=total_words,
        total_claims=total_claims,
        claims_per_100_words=claims_per_100_words,
        citation_count=citation_count,
    )

    project_id = state.get("project_id", "")
    job_id = state.get("job_id", "")
    doc_hash = _infer_doc_hash(state)
    created_at = ensure_utc_datetime(state.get("created_at"))

    # Contract enforcement
    def _enforce_rq_link(rq_id: str) -> None:
        nonlocal flags
        if rq_id == "general" and rigor != "exploratory":
            raise ValueError("rq_id 'general' is only allowed in exploratory rigor")
        if not rq_id:
            raise ValueError("rq_id is required for all artifacts")

    for b in blocks:
        _enforce_rq_link(b.rq_id)
        if rigor == "exploratory" and b.rq_id == "general":
            flags.append(f"block:{b.block_id}:rq_general")
    for t in tables:
        _enforce_rq_link(t.rq_id)
        if not t.source_claim_ids:
            msg = f"table:{t.table_id} missing source_claim_ids"
            if rigor == "conservative":
                raise ValueError(msg)
            flags.append(msg)
        if rigor == "exploratory" and t.rq_id == "general":
            flags.append(f"table:{t.table_id}:rq_general")
    for f in figures:
        _enforce_rq_link(f.rq_id)
        if not f.source_claim_ids:
            msg = f"figure:{f.figure_id} missing source_claim_ids"
            if rigor == "conservative":
                raise ValueError(msg)
            flags.append(msg)
        if rigor == "exploratory" and f.rq_id == "general":
            flags.append(f"figure:{f.figure_id}:rq_general")

    rq_links.update({b.rq_id for b in blocks if b.rq_id})
    rq_links.update({t.rq_id for t in tables if t.rq_id})
    rq_links.update({f.rq_id for f in figures if f.rq_id})

    return ArtifactManifest(
        project_id=project_id,
        job_id=job_id,
        doc_hash=doc_hash,
        created_at=created_at,
        rigor_level=rigor,  # type: ignore[arg-type]
        rq_links=sorted(rq_links),
        blocks=blocks,
        tables=tables,
        figures=figures,
        metrics=metrics,
        flags=flags,
        totals={
            "words": metrics.total_words,
            "claims": metrics.total_claims,
            "citations": metrics.citation_count,
            "tables": len(tables),
            "figures": len(figures),
        },
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
                "total_words": manifest.metrics.total_words,
                "total_claims": manifest.metrics.total_claims,
                "claims_per_100_words": manifest.metrics.claims_per_100_words,
                "table_count": len(manifest.tables),
                "figure_count": len(manifest.figures),
            },
        )
