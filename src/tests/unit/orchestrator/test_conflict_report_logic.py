from datetime import datetime, timezone

import pytest

from src.shared.schema import (
    ConflictItem,
    ConflictReport,
    ConflictType,
    ConflictSeverity,
    ConflictProducer,
    ConflictSuggestedAction,
    RecommendedNextStep,
    SourcePointer,
)
from src.shared.conflict_utils import compute_conflict_hash
from src.orchestrator import nodes


def _base_item(severity=ConflictSeverity.BLOCKER):
    return ConflictItem(
        conflict_id="cid",
        conflict_type=ConflictType.STRUCTURAL_CONFLICT,
        severity=severity,
        summary="conflict",
        details="details",
        produced_by=ConflictProducer.CRITIC,
        contradicts=["fact1"],
        evidence_anchors=[SourcePointer(doc_hash="doc", page=1, bbox=[0, 0, 1, 1], snippet="s")],
        assumptions=["a1"],
        suggested_actions=[ConflictSuggestedAction.HUMAN_SIGNOFF_REQUIRED],
        confidence=0.9,
    )


def test_conflict_hash_deterministic():
    r = ConflictReport(
        report_id="r",
        project_id="p",
        job_id="j",
        doc_hash="doc",
        revision_count=2,
        critic_status="fail",
        deadlock=False,
        deadlock_type=None,
        conflict_items=[_base_item(), _base_item(severity=ConflictSeverity.HIGH)],
        conflict_hash="",
        recommended_next_step=RecommendedNextStep.REVISE_AND_RETRY,
        created_at=datetime.now(timezone.utc),
    )
    r.conflict_hash = compute_conflict_hash(r)
    r2 = r.model_copy(deep=True)
    r2.conflict_items = list(reversed(r2.conflict_items))
    assert compute_conflict_hash(r) == compute_conflict_hash(r2)


def test_deadlock_trigger_conditions():
    report = nodes._build_conflict_report(
        {"project_id": "p", "job_id": "j", "doc_hash": "doc"},
        conflict_flags=["blocker"],
        status="fail",
        revision_count=3,
    )
    assert report.deadlock is True
    assert report.recommended_next_step == RecommendedNextStep.TRIGGER_REFRAMING


def test_conflict_length_constraints():
    with pytest.raises(Exception):
        ConflictItem(
            conflict_id="cid",
            conflict_type=ConflictType.STRUCTURAL_CONFLICT,
            severity=ConflictSeverity.HIGH,
            summary="x" * 241,
            details="y",
            produced_by=ConflictProducer.CRITIC,
            evidence_anchors=[SourcePointer(doc_hash="doc", page=1, bbox=[0, 0, 1, 1], snippet="s")],
            assumptions=[],
            suggested_actions=[],
            confidence=0.5,
        )
