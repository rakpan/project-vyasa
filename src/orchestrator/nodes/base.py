"""
Base utilities for LLM-powered nodes in Project Vyasa.

Provides shared context injection wrapper to ensure all nodes are governed
by ProjectConfig (thesis, RQs, anti-scope) and rigor level.
"""

from typing import Dict, Any, List, Optional
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)


def wrap_prompt_with_context(
    state: Dict[str, Any],
    base_system_prompt: str,
) -> str:
    """Wrap system prompt with ProjectConfig context (thesis, RQs, anti-scope).
    
    Prepends Thesis, Research Questions, and Anti-Scope to system prompt.
    In conservative rigor, adds strict instruction to avoid anti-scope topics.
    
    Args:
        state: ResearchState containing project_context and rigor_level
        base_system_prompt: Original system prompt from role definition
    
    Returns:
        Enhanced system prompt with project context prepended
    """
    project_context = state.get("project_context")
    rigor_level = state.get("rigor_level") or (project_context or {}).get("rigor_level", "exploratory")
    
    if not project_context:
        # No project context available, return base prompt unchanged
        return base_system_prompt
    
    context_sections: List[str] = []
    
    # Thesis
    thesis = project_context.get("thesis", "")
    if thesis:
        context_sections.append(f"Thesis: {thesis}")
    
    # Research Questions
    research_questions = project_context.get("research_questions", [])
    if research_questions:
        rq_list = "\n".join([f"- {rq}" for rq in research_questions])
        context_sections.append(f"Research Questions:\n{rq_list}")
    
    # Anti-Scope
    anti_scope = project_context.get("anti_scope")
    if anti_scope and isinstance(anti_scope, list) and len(anti_scope) > 0:
        anti_scope_list = "\n".join([f"- {topic}" for topic in anti_scope])
        context_sections.append(f"Anti-Scope (explicitly out-of-scope):\n{anti_scope_list}")
        
        # In conservative rigor, add strict instruction
        if rigor_level == "conservative":
            context_sections.append(
                "STRICT CONSTRAINT: Do not extract, synthesize, or reference any information "
                "related to the anti-scope topics listed above. If you encounter content "
                "related to anti-scope, ignore it completely. This is a hard requirement "
                "in conservative mode - violations will cause validation failures."
            )
    
    if not context_sections:
        # No context to add, return base prompt
        return base_system_prompt
    
    # Build enhanced prompt
    context_block = "\n\n".join(context_sections)
    enhanced_prompt = f"{base_system_prompt}\n\n---\nProject Context:\n{context_block}"
    
    logger.debug(
        "Wrapped prompt with project context",
        extra={
            "payload": {
                "has_thesis": bool(thesis),
                "rq_count": len(research_questions),
                "has_anti_scope": bool(anti_scope),
                "rigor_level": rigor_level,
            }
        }
    )
    
    return enhanced_prompt

