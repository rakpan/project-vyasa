"""Deterministic tone linter and rewrite hook."""

import re
from typing import Any, Dict, List, Literal, Optional

from .guards.tone_guard import _compile_terms, _build_regex  # reuse existing loader logic
from ..shared.rigor_config import load_neutral_tone_yaml
from ..shared.logger import get_logger
from ..shared.llm_client import chat
from ..shared.config import get_brain_url
from ..shared.role_manager import RoleRegistry
from ..shared.utils import get_utc_now
from .state import ResearchState

logger = get_logger("orchestrator", __name__)
role_registry = RoleRegistry()


class ToneFinding(Dict[str, Any]):
    """Structured finding dictionary for tone violations."""
    word: str
    severity: Literal["warn", "fail"]
    location: Dict[str, int]
    suggestion: Optional[str]
    category: Optional[str]


def _load_patterns():
    cfg = load_neutral_tone_yaml()
    # Normalize to entries {word, replacement, severity, category}
    entries = []
    for item in cfg.get("terms", []) if isinstance(cfg.get("terms"), list) else []:
        if not isinstance(item, dict):
            continue
        word = str(item.get("word", "")).strip().lower()
        if not word:
            continue
        entries.append(
            {
                "word": word,
                "replacement": item.get("replacement"),
                "severity": item.get("severity") or "warn",
                "category": item.get("category"),
            }
        )
    # Fallback to legacy hard_ban/soft_ban
    term_to_severity = _compile_terms(cfg)
    for term, sev in term_to_severity.items():
        entries.append({"word": term, "severity": "fail" if sev == "hard" else "warn", "replacement": None, "category": None})

    words = [e["word"] for e in entries]
    pattern = _build_regex(words)
    replacement_map = {e["word"]: e.get("replacement") for e in entries}
    severity_map = {e["word"]: e.get("severity", "warn") for e in entries}
    category_map = {e["word"]: e.get("category") for e in entries}
    return pattern, replacement_map, severity_map, category_map


_PATTERN, _REPLACEMENTS, _SEVERITIES, _CATEGORIES = _load_patterns()


def lint_tone(text: str) -> List[ToneFinding]:
    findings: List[ToneFinding] = []
    for match in _PATTERN.finditer(text or ""):
        word = match.group(1)
        start = match.start(1)
        end = match.end(1)
        key = word.lower()
        findings.append(
            {
                "word": word,
                "severity": _SEVERITIES.get(key, "warn"),
                "location": {"start": start, "end": end},
                "suggestion": _REPLACEMENTS.get(key),
                "category": _CATEGORIES.get(key),
            }
        )
    return findings


def _rewrite_sentences(text: str, sentences: List[str], replacements: Dict[str, str], state: Dict[str, Any]) -> str:
    """Call Brain to rewrite flagged sentences with required invariants."""
    role = role_registry.get_role("The Brain")
    rewritten = text
    for sent in sentences:
        replacement = replacements.get(sent)
        if not replacement:
            continue
        prompt = [
            {"role": "system", "content": f"{role.system_prompt}\nPreserve claim_ids and citation_keys; rewrite for neutral tone."},
            {"role": "user", "content": f"Sentence: {sent}\nReplacement guidance: {replacement}\nReturn only the rewritten sentence."},
        ]
        data, _meta = chat(
            primary_url=get_brain_url(),
            model="brain",
            messages=prompt,
            request_params={"temperature": 0.2, "max_tokens": 256},
            state=state,
            node_name="tone_rewrite",
            expert_name="Brain",
            fallback_url=None,
            fallback_model=None,
        )
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "") if isinstance(data, dict) else ""
        if content:
            rewritten = rewritten.replace(sent, content)
    return rewritten


def tone_linter_node(state: ResearchState) -> ResearchState:
    """Deterministic tone linter with rigor-aware enforcement and optional rewrite."""
    rigor = state.get("rigor_level") or (state.get("project_context") or {}).get("rigor_level") or "exploratory"
    synthesis = state.get("synthesis") or state.get("final_text") or ""
    if not synthesis:
        return {}

    findings = lint_tone(synthesis)
    if not findings:
        return {"tone_findings": []}

    fail_findings = [f for f in findings if f.get("severity") == "fail"]
    warn_findings = [f for f in findings if f.get("severity") == "warn"]

    if rigor == "exploratory":
        return {"tone_findings": findings, "tone_flags": [f"{f['word']}@{f['location']['start']}" for f in warn_findings]}

    # conservative path: rewrite and re-lint; if still failing, raise
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", synthesis) if s.strip()]
    flagged_sentences = []
    replacements = {}
    for sent in sentences:
        for f in fail_findings:
            start = f["location"]["start"]
            end = f["location"]["end"]
            if synthesis.find(sent) <= start < synthesis.find(sent) + len(sent):
                flagged_sentences.append(sent)
                replacements[sent] = f.get("suggestion") or "balanced"
                break
    rewritten = _rewrite_sentences(synthesis, flagged_sentences, replacements, state)
    final_findings = lint_tone(rewritten)
    if any(f.get("severity") == "fail" for f in final_findings):
        raise ValueError("Tone linter failed to neutralize forbidden terms in conservative mode")
    return {"synthesis": rewritten, "tone_findings": final_findings, "tone_rewrite_at": get_utc_now().isoformat()}
