"""Tone guard for flagging sensational language (flag-only, no rewrites)."""

import re
from typing import Dict, List

from ...shared.schema import ToneFlag
from ...shared.rigor_config import load_neutral_tone_yaml


def _compile_terms(config: Dict) -> Dict[str, str]:
    hard = [w.strip().lower() for w in config.get("hard_ban", []) if isinstance(w, str)]
    soft = [w.strip().lower() for w in config.get("soft_ban", []) if isinstance(w, str)]
    mapping: Dict[str, str] = {}
    for term in hard:
        mapping[term] = "hard"
    for term in soft:
        mapping[term] = "soft"
    return mapping


def _build_regex(terms: List[str]) -> re.Pattern:
    escaped = [re.escape(t) for t in terms if t]
    pattern = r"\b(" + "|".join(escaped) + r")\b" if escaped else r"$^"
    return re.compile(pattern, flags=re.IGNORECASE)


def scan_text(text: str) -> List[ToneFlag]:
    """
    Scan text for sensational tone words defined in deploy/neutral_tone.yaml.

    Returns a list of ToneFlag with word, severity, locations (character offsets), and optional suggestion.
    """
    config = load_neutral_tone_yaml()
    term_to_severity = _compile_terms(config)
    if not term_to_severity:
        return []

    pattern = _build_regex(list(term_to_severity.keys()))
    matches = []
    for match in pattern.finditer(text or ""):
        word = match.group(1)
        start = match.start(1)
        severity = term_to_severity.get(word.lower(), "soft")
        suggestion_map = config.get("suggestions", {}) if isinstance(config.get("suggestions", {}), dict) else {}
        suggestion = suggestion_map.get(word.lower())
        matches.append(
            ToneFlag(
                word=word,
                severity=severity,  # type: ignore[arg-type]
                locations=[start],
                suggestion=suggestion,
            )
        )
    return matches
