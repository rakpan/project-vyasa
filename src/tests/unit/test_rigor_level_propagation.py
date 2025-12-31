import textwrap

from src.orchestrator.artifacts.manifest_builder import build_manifest
from src.shared import rigor_config
from src.shared.utils import get_utc_now


def test_default_rigor_from_policy(tmp_path, monkeypatch):
    cfg = tmp_path / "rigor_policy.yaml"
    cfg.write_text("rigor_level: exploratory\n", encoding="utf-8")
    monkeypatch.setattr(rigor_config, "DEPLOY_DIR", tmp_path)
    manifest = build_manifest({"project_id": "p1", "job_id": "j1", "manuscript_blocks": [], "created_at": get_utc_now()})
    assert manifest.rigor_level == "exploratory"


def test_conservative_overrides(tmp_path, monkeypatch):
    cfg = tmp_path / "rigor_policy.yaml"
    cfg.write_text("rigor_level: exploratory\n", encoding="utf-8")
    monkeypatch.setattr(rigor_config, "DEPLOY_DIR", tmp_path)
    manifest = build_manifest(
        {"project_id": "p1", "job_id": "j1", "manuscript_blocks": [], "rigor_level": "conservative", "created_at": get_utc_now()},
        rigor_level="conservative",
    )
    assert manifest.rigor_level == "conservative"
