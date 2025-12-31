"""Neutral tone rewriting (minimal, citation-preserving)."""

import re
from typing import List, Optional

from ...shared.schema import ToneFlag


def _replace_preserve_case(text: str, word: str, replacement: str) -> str:
    pattern = re.compile(rf"\\b{re.escape(word)}\\b", flags=re.IGNORECASE)

    def _repl(match: re.Match) -> str:
        src = match.group(0)
        if src.isupper():
            return replacement.upper()
        if src[0].isupper():
            return replacement.capitalize()
        return replacement

    return pattern.sub(_repl, text)


def rewrite_to_neutral(text: str, tone_flags: List[ToneFlag], evidence_context: Optional[str] = None) -> str:
    """
    Perform a minimal rewrite to neutralize hard-banned tone words.

    - Preserves citations (anything in square brackets) by skipping replacements inside them.
    - Uses suggestions when present; otherwise replaces with a generic neutral term.
    - Avoids introducing new claims; only swaps wording.
    """
    if not tone_flags:
        return text

    # Split on citation-like brackets to avoid touching references
    segments = re.split(r"(\[[^\]]+\])", text)
    rewritten_segments = []
    for seg in segments:
        if seg.startswith("[") and seg.endswith("]"):
            rewritten_segments.append(seg)
            continue
        updated = seg
        for flag in tone_flags:
            if flag.severity != "hard":
                continue
            replacement = flag.suggestion or "balanced"
            updated = _replace_preserve_case(updated, flag.word, replacement)
        rewritten_segments.append(updated)
    return "".join(rewritten_segments)
