"""Shim to keep backward-compatible import path for tone_guard."""

from src.orchestrator.tone_guard import _load_patterns, lint_tone, tone_linter_node  # noqa: F401
from src.orchestrator.guards.tone_guard import scan_text  # noqa: F401
# Import functions that are used in tone_guard.py but need to be accessible for test mocking
# These are imported in tone_guard.py from their source modules, so we import them directly here
from src.shared.rigor_config import load_neutral_tone_yaml  # noqa: F401
from src.shared.llm_client import chat  # noqa: F401

# Re-export for test compatibility
__all__ = ["_load_patterns", "scan_text", "lint_tone", "tone_linter_node", "load_neutral_tone_yaml", "chat"]
