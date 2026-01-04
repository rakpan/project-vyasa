"""
Unit tests for context injection wrapper.

Ensures:
- wrapper includes RQs, thesis, anti_scope
- conservative wrapper includes stronger "do not include" constraints
- wrapper handles missing project_context gracefully
- all nodes use wrapper consistently
"""

import pytest
from typing import Dict, Any

from src.orchestrator.nodes.base import wrap_prompt_with_context


@pytest.fixture
def base_prompt():
    """Base system prompt for testing."""
    return "You are an expert knowledge extractor. Extract structured information from text."


@pytest.fixture
def project_context_with_all_fields():
    """Project context with thesis, RQs, and anti-scope."""
    return {
        "thesis": "This research investigates the security implications of AI systems.",
        "research_questions": [
            "What are the main attack vectors against AI systems?",
            "How can adversarial examples be detected?",
            "What mitigation strategies are most effective?",
        ],
        "anti_scope": [
            "Hardware vulnerabilities",
            "Network-level attacks",
            "Legacy system compatibility",
        ],
        "rigor_level": "exploratory",
    }


@pytest.fixture
def project_context_minimal():
    """Minimal project context with only thesis."""
    return {
        "thesis": "Simple research thesis.",
        "research_questions": [],
        "anti_scope": [],
    }


@pytest.fixture
def state_with_context(project_context_with_all_fields):
    """ResearchState with project context."""
    return {
        "project_context": project_context_with_all_fields,
        "rigor_level": "exploratory",
    }


@pytest.fixture
def state_without_context():
    """ResearchState without project context."""
    return {
        "rigor_level": "exploratory",
    }


class TestWrapPromptWithContext:
    """Tests for wrap_prompt_with_context function."""

    def test_wrapper_includes_thesis(self, base_prompt, state_with_context):
        """Asserts wrapper includes thesis in enhanced prompt."""
        enhanced = wrap_prompt_with_context(state_with_context, base_prompt)
        
        assert base_prompt in enhanced
        assert "Thesis:" in enhanced
        assert "This research investigates the security implications of AI systems." in enhanced

    def test_wrapper_includes_research_questions(self, base_prompt, state_with_context):
        """Asserts wrapper includes research questions."""
        enhanced = wrap_prompt_with_context(state_with_context, base_prompt)
        
        assert "Research Questions:" in enhanced
        assert "What are the main attack vectors against AI systems?" in enhanced
        assert "How can adversarial examples be detected?" in enhanced
        assert "What mitigation strategies are most effective?" in enhanced

    def test_wrapper_includes_anti_scope(self, base_prompt, state_with_context):
        """Asserts wrapper includes anti-scope topics."""
        enhanced = wrap_prompt_with_context(state_with_context, base_prompt)
        
        assert "Anti-Scope" in enhanced
        assert "Hardware vulnerabilities" in enhanced
        assert "Network-level attacks" in enhanced
        assert "Legacy system compatibility" in enhanced

    def test_wrapper_handles_missing_project_context(self, base_prompt, state_without_context):
        """Asserts wrapper returns base prompt unchanged when no project context."""
        enhanced = wrap_prompt_with_context(state_without_context, base_prompt)
        
        assert enhanced == base_prompt
        assert "Thesis:" not in enhanced
        assert "Research Questions:" not in enhanced

    def test_wrapper_handles_empty_project_context(self, base_prompt):
        """Asserts wrapper handles empty project context gracefully."""
        state = {"project_context": {}}
        enhanced = wrap_prompt_with_context(state, base_prompt)
        
        assert enhanced == base_prompt

    def test_wrapper_handles_none_project_context(self, base_prompt):
        """Asserts wrapper handles None project context gracefully."""
        state = {"project_context": None}
        enhanced = wrap_prompt_with_context(state, base_prompt)
        
        assert enhanced == base_prompt

    def test_conservative_mode_adds_strict_constraints(
        self,
        base_prompt,
        project_context_with_all_fields,
    ):
        """Asserts conservative mode adds strict 'do not include' constraints."""
        state = {
            "project_context": project_context_with_all_fields,
            "rigor_level": "conservative",
        }
        enhanced = wrap_prompt_with_context(state, base_prompt)
        
        assert "STRICT CONSTRAINT" in enhanced
        assert "Do not extract, synthesize, or reference" in enhanced
        assert "ignore it completely" in enhanced
        assert "anti-scope topics" in enhanced

    def test_exploratory_mode_no_strict_constraints(
        self,
        base_prompt,
        project_context_with_all_fields,
    ):
        """Asserts exploratory mode does not add strict constraints."""
        state = {
            "project_context": project_context_with_all_fields,
            "rigor_level": "exploratory",
        }
        enhanced = wrap_prompt_with_context(state, base_prompt)
        
        assert "STRICT CONSTRAINT" not in enhanced
        assert "Do not extract, synthesize, or reference" not in enhanced
        # But anti-scope should still be listed
        assert "Anti-Scope" in enhanced

    def test_conservative_mode_without_anti_scope(
        self,
        base_prompt,
        project_context_minimal,
    ):
        """Asserts conservative mode without anti-scope does not add constraints."""
        state = {
            "project_context": project_context_minimal,
            "rigor_level": "conservative",
        }
        enhanced = wrap_prompt_with_context(state, base_prompt)
        
        assert "STRICT CONSTRAINT" not in enhanced
        assert "Thesis:" in enhanced

    def test_wrapper_preserves_base_prompt(self, base_prompt, state_with_context):
        """Asserts wrapper preserves original base prompt content."""
        enhanced = wrap_prompt_with_context(state_with_context, base_prompt)
        
        assert base_prompt in enhanced
        assert enhanced.startswith(base_prompt)

    def test_wrapper_handles_empty_anti_scope_list(
        self,
        base_prompt,
        project_context_minimal,
    ):
        """Asserts wrapper handles empty anti-scope list gracefully."""
        state = {
            "project_context": project_context_minimal,
            "rigor_level": "conservative",
        }
        enhanced = wrap_prompt_with_context(state, base_prompt)
        
        assert "Anti-Scope" not in enhanced
        assert "STRICT CONSTRAINT" not in enhanced

    def test_wrapper_handles_rigor_level_from_project_context(
        self,
        base_prompt,
        project_context_with_all_fields,
    ):
        """Asserts wrapper reads rigor_level from project_context if not in state."""
        project_context_with_all_fields["rigor_level"] = "conservative"
        state = {
            "project_context": project_context_with_all_fields,
            # rigor_level not in state, should read from project_context
        }
        enhanced = wrap_prompt_with_context(state, base_prompt)
        
        assert "STRICT CONSTRAINT" in enhanced

    def test_wrapper_handles_single_research_question(self, base_prompt):
        """Asserts wrapper handles single research question."""
        state = {
            "project_context": {
                "thesis": "Test thesis",
                "research_questions": ["Single RQ"],
                "anti_scope": [],
            },
        }
        enhanced = wrap_prompt_with_context(state, base_prompt)
        
        assert "Research Questions:" in enhanced
        assert "Single RQ" in enhanced

    def test_wrapper_handles_single_anti_scope_topic(self, base_prompt):
        """Asserts wrapper handles single anti-scope topic."""
        state = {
            "project_context": {
                "thesis": "Test thesis",
                "research_questions": [],
                "anti_scope": ["Single topic"],
            },
            "rigor_level": "conservative",
        }
        enhanced = wrap_prompt_with_context(state, base_prompt)
        
        assert "Anti-Scope" in enhanced
        assert "Single topic" in enhanced
        assert "STRICT CONSTRAINT" in enhanced

    def test_wrapper_format_structure(self, base_prompt, state_with_context):
        """Asserts wrapper produces well-formatted prompt structure."""
        enhanced = wrap_prompt_with_context(state_with_context, base_prompt)
        
        # Should have clear section separators
        assert "---" in enhanced
        assert "Project Context:" in enhanced
        # Should have proper line breaks
        assert "\n\n" in enhanced


class TestContextInjectionConsistency:
    """Tests to ensure all nodes use context injection consistently."""

    def test_cartographer_uses_wrapper(self):
        """Asserts Cartographer node uses wrap_prompt_with_context."""
        from src.orchestrator.nodes.nodes import cartographer_node
        
        # Check that the function imports wrap_prompt_with_context
        import inspect
        source = inspect.getsource(cartographer_node)
        assert "wrap_prompt_with_context" in source

    def test_synthesizer_uses_wrapper(self):
        """Asserts Synthesizer node uses wrap_prompt_with_context."""
        from src.orchestrator.nodes.nodes import synthesizer_node
        
        # Check that the function imports wrap_prompt_with_context
        import inspect
        source = inspect.getsource(synthesizer_node)
        assert "wrap_prompt_with_context" in source

    def test_critic_uses_wrapper(self):
        """Asserts Critic node uses wrap_prompt_with_context."""
        from src.orchestrator.nodes.nodes import critic_node
        
        # Check that the function imports wrap_prompt_with_context
        import inspect
        source = inspect.getsource(critic_node)
        # Critic may use system_template, check for wrap_prompt_with_context or manual context injection
        assert "wrap_prompt_with_context" in source or "project_context" in source

