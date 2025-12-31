import textwrap

import pytest

from src.orchestrator.guards.tone_guard import scan_text


def test_detects_hard_and_soft_words(tmp_path, monkeypatch):
    # Override config to keep test deterministic
    cfg = tmp_path / "neutral_tone.yaml"
    cfg.write_text(
        textwrap.dedent(
            """
            hard_ban:
              - revolutionary
            soft_ban:
              - critical
            """
        ),
        encoding="utf-8",
    )
    from src.shared import rigor_config

    monkeypatch.setattr(rigor_config, "DEPLOY_DIR", tmp_path)
    flags = scan_text("A Revolutionary finding with a critical implication.")
    words = {f.word.lower(): f for f in flags}
    assert "revolutionary" in words and words["revolutionary"].severity == "hard"
    assert "critical" in words and words["critical"].severity == "soft"


def test_word_boundaries_no_substring(tmp_path, monkeypatch):
    cfg = tmp_path / "neutral_tone.yaml"
    cfg.write_text(
        textwrap.dedent(
            """
            hard_ban:
              - breakthrough
            """
        ),
        encoding="utf-8",
    )
    from src.shared import rigor_config

    monkeypatch.setattr(rigor_config, "DEPLOY_DIR", tmp_path)
    flags = scan_text("Mini-breakthroughs are not flagged but breakthrough is.")
    assert len(flags) == 1
    assert flags[0].word.lower() == "breakthrough"


def test_case_insensitive_and_locations(tmp_path, monkeypatch):
    cfg = tmp_path / "neutral_tone.yaml"
    cfg.write_text(
        textwrap.dedent(
            """
            soft_ban:
              - dramatic
            """
        ),
        encoding="utf-8",
    )
    from src.shared import rigor_config

    monkeypatch.setattr(rigor_config, "DEPLOY_DIR", tmp_path)
    text = "A Dramatic shift and another dramatic turn."
    flags = scan_text(text)
    assert len(flags) == 2
    # locations should be character offsets of each match
    assert flags[0].locations == [2]  # "Dramatic" starts at index 2
    assert flags[1].locations == [29]  # second "dramatic" starts at index 29


def test_punctuation_and_boundaries(tmp_path, monkeypatch):
    cfg = tmp_path / "neutral_tone.yaml"
    cfg.write_text("hard_ban:\n  - revolutionary\n", encoding="utf-8")
    from src.shared import rigor_config
    monkeypatch.setattr(rigor_config, "DEPLOY_DIR", tmp_path)
    text = "revolutionary, start Revolutionary! end"
    flags = scan_text(text)
    words = [f.word.lower() for f in flags]
    assert words.count("revolutionary") == 2
    assert flags[0].locations == [0]
    assert flags[1].locations == [21]


def test_multiple_cases_and_empty_text(tmp_path, monkeypatch):
    cfg = tmp_path / "neutral_tone.yaml"
    cfg.write_text("soft_ban:\n  - dramatic\n", encoding="utf-8")
    from src.shared import rigor_config
    monkeypatch.setattr(rigor_config, "DEPLOY_DIR", tmp_path)
    flags = scan_text("")
    assert flags == []
    flags2 = scan_text("Dramatic DRAMATIC dramatic")
    assert len(flags2) == 3
