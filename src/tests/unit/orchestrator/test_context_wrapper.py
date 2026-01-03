"""
Unit tests for context injection wrapper.

Tests verify that wrap_prompt_with_context includes all ProjectConfig fields
and changes behavior in conservative mode.
"""

import pytest
from src.orchestrator.nodes.base import wrap_prompt_with_context


class TestContextWrapper:
    """Test wrap_prompt_with_context function."""
    
    def test_wrap_prompt_with_thesis_and_rqs(self):
        """Test wrapper includes thesis and research questions."""
        state = {
            "project_context": {
                "thesis": "Modern web applications are vulnerable to injection attacks",
                "research_questions": [
                    "What are the most common injection vulnerabilities?",
                    "How effective are input validation mechanisms?",
                ],
                "anti_scope": None,
            },
            "rigor_level": "exploratory",
        }
        base_prompt = "You are a Cartographer. Extract knowledge from documents."
        
        result = wrap_prompt_with_context(state, base_prompt)
        
        assert "Thesis:" in result
        assert "Modern web applications are vulnerable" in result
        assert "Research Questions:" in result
        assert "What are the most common injection vulnerabilities?" in result
        assert "How effective are input validation mechanisms?" in result
        assert base_prompt in result
    
    def test_wrap_prompt_with_anti_scope(self):
        """Test wrapper includes anti-scope."""
        state = {
            "project_context": {
                "thesis": "Test thesis",
                "research_questions": [],
                "anti_scope": ["Mobile applications", "Hardware security"],
            },
            "rigor_level": "exploratory",
        }
        base_prompt = "You are a Cartographer."
        
        result = wrap_prompt_with_context(state, base_prompt)
        
        assert "Anti-Scope" in result
        assert "Mobile applications" in result
        assert "Hardware security" in result
    
    def test_wrap_prompt_conservative_mode_strict_instruction(self):
        """Test conservative mode adds strict anti-scope instruction."""
        state = {
            "project_context": {
                "thesis": "Test thesis",
                "research_questions": [],
                "anti_scope": ["Mobile applications"],
            },
            "rigor_level": "conservative",
        }
        base_prompt = "You are a Cartographer."
        
        result = wrap_prompt_with_context(state, base_prompt)
        
        assert "STRICT CONSTRAINT" in result
        assert "Do not extract, synthesize, or reference" in result
        assert "ignore it completely" in result
    
    def test_wrap_prompt_exploratory_mode_no_strict_instruction(self):
        """Test exploratory mode does not add strict instruction."""
        state = {
            "project_context": {
                "thesis": "Test thesis",
                "research_questions": [],
                "anti_scope": ["Mobile applications"],
            },
            "rigor_level": "exploratory",
        }
        base_prompt = "You are a Cartographer."
        
        result = wrap_prompt_with_context(state, base_prompt)
        
        assert "STRICT CONSTRAINT" not in result
    
    def test_wrap_prompt_no_project_context(self):
        """Test wrapper returns base prompt when no project context."""
        state = {}
        base_prompt = "You are a Cartographer."
        
        result = wrap_prompt_with_context(state, base_prompt)
        
        assert result == base_prompt
    
    def test_wrap_prompt_empty_project_context(self):
        """Test wrapper handles empty project context gracefully."""
        state = {
            "project_context": {},
        }
        base_prompt = "You are a Cartographer."
        
        result = wrap_prompt_with_context(state, base_prompt)
        
        assert result == base_prompt
    
    def test_wrap_prompt_rigor_level_from_project_context(self):
        """Test wrapper reads rigor_level from project_context if not in state."""
        state = {
            "project_context": {
                "thesis": "Test thesis",
                "research_questions": [],
                "anti_scope": ["Mobile applications"],
                "rigor_level": "conservative",
            },
        }
        base_prompt = "You are a Cartographer."
        
        result = wrap_prompt_with_context(state, base_prompt)
        
        assert "STRICT CONSTRAINT" in result

