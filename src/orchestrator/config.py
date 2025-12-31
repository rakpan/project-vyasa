"""
Orchestrator configuration for expert routing.
"""

from __future__ import annotations


class ExpertType:
    """Expert type enumeration for routing decisions."""

    LOGIC_REASONING = "logic_reasoning"  # Brain (Port 30000)
    EXTRACTION_SCHEMA = "extraction_schema"  # Worker (Port 30001) with Brain fallback
    PROSE_WRITING = "prose_writing"  # Drafter (Port 11434)
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
