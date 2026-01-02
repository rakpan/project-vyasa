import json

from datetime import datetime

import pytest

from src.orchestrator.artifacts.manifest_builder import (
    build_manifest,
    persist_manifest,
    ARTIFACT_ROOT,
)
from src.shared.utils import get_utc_now, ensure_utc_datetime


class FakeCollection:
    def __init__(self):
        self.inserted = []

    def insert(self, doc):
        self.inserted.append(doc)


class FakeDB:
    def __init__(self):
        self.collections = {}

    def has_collection(self, name):
        return name in self.collections

    def create_collection(self, name):
        self.collections[name] = FakeCollection()
        return self.collections[name]

    def collection(self, name):
        return self.collections[name]


class FakeTelemetry:
    def __init__(self):
        self.events = []

    def emit_event(self, event_type, data):
        self.events.append((event_type, data))


def test_build_manifest_totals_and_tone(monkeypatch, tmp_path):
    # Override neutral tone config to keep deterministic
    cfg = tmp_path / "neutral_tone.yaml"
    cfg.write_text("hard_ban:\n  - revolutionary\n", encoding="utf-8")
    from src.shared import rigor_config
    monkeypatch.setattr(rigor_config, "DEPLOY_DIR", tmp_path)

    block = {
        "block_id": "b1",
        "section_title": "Intro",
        "content": "A revolutionary idea.",
        "citation_keys": ["cite1", "cite2"],
        "claim_ids": ["t1"],
    }
    state = {
        "project_id": "p1",
        "job_id": "j1",
        "doc_hash": "abc",
        "manuscript_blocks": [block],
        "vision_results": [{"artifact_id": "v1", "kind": "figure"}],
        "tables": [
            {"table_id": "t1", "rows": [{"col": "1.23"}, {"col": "2.34"}]}
        ],
        "created_at": get_utc_now(),
    }
    manifest = build_manifest(state)
    assert manifest.totals["words"] == len(block["content"].split())
    assert manifest.totals["citations"] == 2
    assert manifest.totals["figures"] == 1
    assert manifest.totals["tables"] == 1
    assert manifest.blocks[0].tone_flags  # revolutionary flagged


def test_persist_manifest_writes_file_and_db(tmp_path):
    db = FakeDB()
    telemetry = FakeTelemetry()
    manifest = build_manifest(
        {
            "project_id": "p1",
            "job_id": "j1",
            "doc_hash": "abc",
            "manuscript_blocks": [],
            "created_at": get_utc_now(),
        }
    )
    persist_manifest(manifest, db=db, telemetry_emitter=telemetry, artifact_root=tmp_path)

    # DB insert called
    assert db.has_collection("artifact_manifests")
    assert db.collection("artifact_manifests").inserted

    # File written
    out_path = tmp_path / "p1" / "j1" / "artifact_manifest.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["job_id"] == "j1"

    # Telemetry emitted
    assert telemetry.events


def test_created_at_naive_converts_to_utc():
    naive = datetime.now()
    manifest = build_manifest(
        {
            "project_id": "p1",
            "job_id": "j1",
            "doc_hash": "abc",
            "manuscript_blocks": [],
            "created_at": naive,
        }
    )
    assert manifest.created_at.tzinfo is not None
    assert manifest.created_at.tzinfo.utcoffset(manifest.created_at).total_seconds() == 0
