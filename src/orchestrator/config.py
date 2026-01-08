"""
Orchestrator configuration for expert routing and web augmentation.
"""

from __future__ import annotations


# Web Augmentation Configuration
# These are re-exported from shared.config for convenience
# but the canonical source is src/shared/config.py
from ..shared.config import (
    _env as _get_env,
)

# Web augmentation feature flag
WEB_AUGMENTATION_ENABLED = _get_env("WEB_AUGMENTATION_ENABLED", "false").lower() in ("true", "1", "yes")

# Web augmentation limits
WEB_MAX_URLS = int(_get_env("WEB_MAX_URLS", "10"))
WEB_MAX_PAGES = int(_get_env("WEB_MAX_PAGES", "25"))


class ExpertType:
    """Expert type enumeration for routing decisions."""

    LOGIC_REASONING = "logic_reasoning"  # Brain (Port 30000)
    EXTRACTION_SCHEMA = "extraction_schema"  # Worker (Port 30001) with Brain fallback
    PROSE_WRITING = "prose_writing"  # TEXT model (Brain/Worker) with draft prompt profile
    VISION = "vision"  # Vision (Port 30002)


# Explicit node -> expert mapping
NODE_EXPERT_MAP: dict[str, str] = {
    "cartographer_node": ExpertType.EXTRACTION_SCHEMA,
    "critic_node": ExpertType.LOGIC_REASONING,
    "vision_node": ExpertType.VISION,
    "saver_node": ExpertType.EXTRACTION_SCHEMA,
    # Aliases / semantic names
    "extract_triples": ExpertType.EXTRACTION_SCHEMA,
    "review_logic": ExpertType.LOGIC_REASONING,
    "review": ExpertType.LOGIC_REASONING,
    "draft": ExpertType.PROSE_WRITING,
}
