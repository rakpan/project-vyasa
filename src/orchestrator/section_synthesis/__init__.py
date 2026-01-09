"""
Section Synthesis module for Project Vyasa.

Implements the complete section synthesis loop per orchestration spec:
- Query building from blueprint section + linked RQs
- Retrieval + rerank (via RetrievalService)
- Packet A (Primary Sources) and Packet B (Analytical Notes) construction
- Synthesizer and Critic calls (Nemotron 49B)
- Persistence (manuscript blocks + note promotions)
"""

from .section_orchestrator import (
    run_section_synthesis,
    build_section_query,
    build_packet_a,
    build_packet_b,
    synthesize_section,
    criticize_section,
    SectionSynthesisError,
)

__all__ = [
    "run_section_synthesis",
    "build_section_query",
    "build_packet_a",
    "build_packet_b",
    "synthesize_section",
    "criticize_section",
    "SectionSynthesisError",
]
