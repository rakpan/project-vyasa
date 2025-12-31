import textwrap

from src.orchestrator.nodes import synthesizer_node
from src.orchestrator.guards import tone_rewrite
from src.shared import rigor_config
from src.shared.schema import ToneFlag
from src.shared.schema import ToneFlag


def test_rewrite_not_called_in_exploratory(monkeypatch):
    called = False

    def fake_rewrite(text, flags, evidence_context=None):
        nonlocal called
        called = True
        return text

    monkeypatch.setattr(tone_rewrite, "rewrite_to_neutral", fake_rewrite)
    monkeypatch.setattr(rigor_config, "DEPLOY_DIR", rigor_config.DEPLOY_DIR)
    state = {
        "synthesis": "A revolutionary result.",
        "rigor_level": "exploratory",
    }
    out = synthesizer_node(state)
    assert out["synthesis"] == "A revolutionary result."
    assert called is False


def test_rewrite_called_only_on_hard_and_conservative(monkeypatch, tmp_path):
    # Create both config files
    rigor_cfg = tmp_path / "rigor_policy.yaml"
    rigor_cfg.write_text("tone_enforcement: rewrite\nmax_decimals_default: 2\nrigor_level: conservative\n", encoding="utf-8")
    tone_cfg = tmp_path / "neutral_tone.yaml"
    tone_cfg.write_text("hard_ban:\n  - revolutionary\n", encoding="utf-8")
    monkeypatch.setattr(rigor_config, "DEPLOY_DIR", tmp_path)
    # Force scan_text to return a hard flag to guarantee rewrite path
    from src.orchestrator import nodes as nodes_module
    monkeypatch.setattr(nodes_module, "load_rigor_policy_yaml", lambda: {"tone_enforcement": "rewrite"})
    monkeypatch.setattr(
        nodes_module, "scan_text", lambda text: [ToneFlag(word="revolutionary", severity="hard", locations=[0], suggestion=None)]
    )
    synthesizer_node.__globals__["scan_text"] = nodes_module.scan_text
    synthesizer_node.__globals__["load_rigor_policy_yaml"] = nodes_module.load_rigor_policy_yaml

    called = {"flag": False}

    def fake_rewrite(text, flags, evidence_context=None):
        called["flag"] = True
        return text.replace("revolutionary", "balanced")

    monkeypatch.setattr(nodes_module, "rewrite_to_neutral", fake_rewrite)
    synthesizer_node.__globals__["rewrite_to_neutral"] = nodes_module.rewrite_to_neutral

    state = {
        "synthesis": "A revolutionary result.",
        "rigor_level": "conservative",
    }
    out = synthesizer_node(state)
    assert called["flag"] is True
    assert "balanced" in out["synthesis"]


def test_citations_preserved(tmp_path, monkeypatch):
    # Create both config files
    rigor_cfg = tmp_path / "rigor_policy.yaml"
    rigor_cfg.write_text("tone_enforcement: rewrite\nmax_decimals_default: 2\nrigor_level: conservative\n", encoding="utf-8")
    tone_cfg = tmp_path / "neutral_tone.yaml"
    tone_cfg.write_text("hard_ban:\n  - revolutionary\n  - unprecedented\n", encoding="utf-8")
    monkeypatch.setattr(rigor_config, "DEPLOY_DIR", tmp_path)
    from src.orchestrator import nodes as nodes_module
    monkeypatch.setattr(nodes_module, "load_rigor_policy_yaml", lambda: {"tone_enforcement": "rewrite"})
    monkeypatch.setattr(
        nodes_module,
        "scan_text",
        lambda text: [
            ToneFlag(word="revolutionary", severity="hard", locations=[2], suggestion=None),
            ToneFlag(word="unprecedented", severity="hard", locations=[30], suggestion=None),
        ],
    )
    synthesizer_node.__globals__["scan_text"] = nodes_module.scan_text
    synthesizer_node.__globals__["load_rigor_policy_yaml"] = nodes_module.load_rigor_policy_yaml
    monkeypatch.setattr(
        nodes_module,
        "rewrite_to_neutral",
        lambda text, flags, evidence_context=None: text.replace("revolutionary", "balanced").replace(
            "Unprecedented", "Measured"
        ),
    )
    synthesizer_node.__globals__["rewrite_to_neutral"] = nodes_module.rewrite_to_neutral

    text = "A revolutionary idea [Smith2020]. Unprecedented results [1][2]."
    state = {"synthesis": text, "rigor_level": "conservative"}
    out = synthesizer_node(state)
    assert "[Smith2020]" in out["synthesis"]
    assert "[1][2]" in out["synthesis"]
    assert "revolutionary" not in out["synthesis"]
    assert "Unprecedented" not in out["synthesis"]
