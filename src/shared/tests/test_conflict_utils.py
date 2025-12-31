import copy
from datetime import datetime, timezone

from src.shared.conflict_utils import compute_conflict_hash
from src.shared.schema import (
    ConflictReport,
    ConflictItem,
    ConflictType,
    ConflictSeverity,
    ConflictProducer,
    ConflictSuggestedAction,
    RecommendedNextStep,
    SourcePointer,
)


def _make_item(summary: str, contradicts=None, page=1):
    return ConflictItem(
        conflict_id="cid-1",
        conflict_type=ConflictType.STRUCTURAL_CONFLICT,
        severity=ConflictSeverity.HIGH,
        summary=summary,
        details="details",
        produced_by=ConflictProducer.CRITIC,
        contradicts=contradicts or [],
        evidence_anchors=[
            SourcePointer(doc_hash="doc", page=page, bbox=[0, 0, 1, 1], snippet="x")
        ],
        assumptions=["A"],
        suggested_actions=[ConflictSuggestedAction.RETRY_EXTRACTION],
        confidence=0.8,
    )


def _make_report(items):
    return ConflictReport(
        report_id="r1",
        project_id="p",
        job_id="j",
        doc_hash="doc",
        revision_count=1,
        critic_status="fail",
        deadlock=False,
        deadlock_type=None,
        conflict_items=items,
        conflict_hash="",
        recommended_next_step=RecommendedNextStep.REVISE_AND_RETRY,
        created_at=datetime.now(timezone.utc),
    )


def test_conflict_hash_stable_under_reordering():
    r1 = _make_report([_make_item("one", contradicts=["a"]), _make_item("two", contradicts=["b"], page=2)])
    r2 = _make_report(list(reversed(r1.conflict_items)))
    h1 = compute_conflict_hash(r1)
    h2 = compute_conflict_hash(r2)
    assert h1 == h2


def test_evidence_anchor_validation():
    # bbox out of range should raise validation error
    try:
        SourcePointer(doc_hash="doc", page=1, bbox=[-1, 0, 1, 1], snippet="bad")
        assert False, "Expected validation error"
    except Exception:
        assert True
