"""
Unit tests for Citation Integrity Validator.

Ensures:
- Block without bindings fails (conservative)
- Block with unknown claim_id fails (conservative)
- Correct block passes
- Exploratory mode warns but allows
"""

import pytest
from typing import Dict, Any, List

from src.orchestrator.validators.citation_integrity import (
    validate_citation_integrity,
    validate_manuscript_blocks,
    extract_claim_ids_from_text,
)


@pytest.fixture
def sample_block_with_bindings():
    """Sample block with claim bindings."""
    return {
        "block_id": "block-1",
        "text": "This is a test paragraph with claim reference [[claim_123]].",
        "content": "This is a test paragraph with claim reference [[claim_123]].",
        "claim_ids": ["claim_123"],
        "citation_keys": [],
    }


@pytest.fixture
def sample_block_without_bindings():
    """Sample block without claim bindings."""
    return {
        "block_id": "block-2",
        "text": "This is a test paragraph without any claim references.",
        "content": "This is a test paragraph without any claim references.",
        "claim_ids": [],
        "citation_keys": [],
    }


@pytest.fixture
def sample_block_with_unknown_claim_id():
    """Sample block with unknown claim_id."""
    return {
        "block_id": "block-3",
        "text": "This paragraph references [[claim_unknown]].",
        "content": "This paragraph references [[claim_unknown]].",
        "claim_ids": ["claim_unknown"],
        "citation_keys": [],
    }


@pytest.fixture
def available_claim_ids():
    """List of available claim IDs."""
    return ["claim_123", "claim_456", "claim_789"]


class TestExtractClaimIdsFromText:
    """Tests for extracting claim IDs from text."""
    
    def test_extracts_inline_references(self):
        """Asserts inline references are extracted correctly."""
        text = "This paragraph references [[claim_123]] and [[claim_456]]."
        claim_ids = extract_claim_ids_from_text(text)
        
        assert "claim_123" in claim_ids
        assert "claim_456" in claim_ids
        assert len(claim_ids) == 2
    
    def test_handles_no_references(self):
        """Asserts empty list returned when no references found."""
        text = "This paragraph has no claim references."
        claim_ids = extract_claim_ids_from_text(text)
        
        assert claim_ids == []
    
    def test_deduplicates_references(self):
        """Asserts duplicate references are deduplicated."""
        text = "This paragraph references [[claim_123]] twice [[claim_123]]."
        claim_ids = extract_claim_ids_from_text(text)
        
        assert claim_ids == ["claim_123"]  # Should be deduplicated


class TestValidateCitationIntegrity:
    """Tests for citation integrity validation."""
    
    def test_block_with_bindings_passes_conservative(
        self,
        sample_block_with_bindings,
        available_claim_ids,
    ):
        """Asserts block with valid claim bindings passes in conservative mode."""
        is_valid, error_msg = validate_citation_integrity(
            block=sample_block_with_bindings,
            available_claim_ids=available_claim_ids,
            rigor_level="conservative",
        )
        
        assert is_valid is True
        assert error_msg is None
    
    def test_block_without_bindings_fails_conservative(
        self,
        sample_block_without_bindings,
        available_claim_ids,
    ):
        """Asserts block without bindings fails in conservative mode."""
        is_valid, error_msg = validate_citation_integrity(
            block=sample_block_without_bindings,
            available_claim_ids=available_claim_ids,
            rigor_level="conservative",
        )
        
        assert is_valid is False
        assert error_msg is not None
        assert "no claim bindings" in error_msg.lower()
    
    def test_block_with_unknown_claim_id_fails_conservative(
        self,
        sample_block_with_unknown_claim_id,
        available_claim_ids,
    ):
        """Asserts block with unknown claim_id fails in conservative mode."""
        is_valid, error_msg = validate_citation_integrity(
            block=sample_block_with_unknown_claim_id,
            available_claim_ids=available_claim_ids,
            rigor_level="conservative",
        )
        
        assert is_valid is False
        assert error_msg is not None
        assert "unknown claim_id" in error_msg.lower() or "unknown claim_ids" in error_msg.lower()
    
    def test_block_without_bindings_allowed_exploratory(
        self,
        sample_block_without_bindings,
        available_claim_ids,
    ):
        """Asserts block without bindings is allowed in exploratory mode (warns but allows)."""
        is_valid, error_msg = validate_citation_integrity(
            block=sample_block_without_bindings,
            available_claim_ids=available_claim_ids,
            rigor_level="exploratory",
        )
        
        assert is_valid is True  # Exploratory mode allows
        assert error_msg is None
    
    def test_block_with_unknown_claim_id_allowed_exploratory(
        self,
        sample_block_with_unknown_claim_id,
        available_claim_ids,
    ):
        """Asserts block with unknown claim_id is allowed in exploratory mode (warns but allows)."""
        is_valid, error_msg = validate_citation_integrity(
            block=sample_block_with_unknown_claim_id,
            available_claim_ids=available_claim_ids,
            rigor_level="exploratory",
        )
        
        assert is_valid is True  # Exploratory mode allows
        assert error_msg is None
    
    def test_block_with_explicit_claim_ids_only(
        self,
        available_claim_ids,
    ):
        """Asserts block with explicit claim_ids (no inline refs) passes."""
        block = {
            "block_id": "block-4",
            "text": "This paragraph has no inline references.",
            "content": "This paragraph has no inline references.",
            "claim_ids": ["claim_123"],  # Explicit binding
            "citation_keys": [],
        }
        
        is_valid, error_msg = validate_citation_integrity(
            block=block,
            available_claim_ids=available_claim_ids,
            rigor_level="conservative",
        )
        
        assert is_valid is True
        assert error_msg is None
    
    def test_block_with_inline_references_only(
        self,
        available_claim_ids,
    ):
        """Asserts block with inline references (no explicit claim_ids) passes."""
        block = {
            "block_id": "block-5",
            "text": "This paragraph references [[claim_123]] inline.",
            "content": "This paragraph references [[claim_123]] inline.",
            "claim_ids": [],  # No explicit binding, but inline refs exist
            "citation_keys": [],
        }
        
        is_valid, error_msg = validate_citation_integrity(
            block=block,
            available_claim_ids=available_claim_ids,
            rigor_level="conservative",
        )
        
        assert is_valid is True
        assert error_msg is None


class TestValidateManuscriptBlocks:
    """Tests for validating multiple manuscript blocks."""
    
    def test_all_blocks_pass(
        self,
        sample_block_with_bindings,
        available_claim_ids,
    ):
        """Asserts all valid blocks pass validation."""
        blocks = [sample_block_with_bindings]
        
        valid_blocks, errors = validate_manuscript_blocks(
            blocks=blocks,
            available_claim_ids=available_claim_ids,
            rigor_level="conservative",
        )
        
        assert len(valid_blocks) == 1
        assert len(errors) == 0
    
    def test_some_blocks_fail(
        self,
        sample_block_with_bindings,
        sample_block_without_bindings,
        available_claim_ids,
    ):
        """Asserts invalid blocks are filtered out."""
        blocks = [sample_block_with_bindings, sample_block_without_bindings]
        
        valid_blocks, errors = validate_manuscript_blocks(
            blocks=blocks,
            available_claim_ids=available_claim_ids,
            rigor_level="conservative",
        )
        
        assert len(valid_blocks) == 1
        assert len(errors) == 1
        assert "block-2" in errors[0]  # Error should mention block_id
    
    def test_exploratory_mode_allows_all(
        self,
        sample_block_with_bindings,
        sample_block_without_bindings,
        available_claim_ids,
    ):
        """Asserts exploratory mode allows all blocks (warns but allows)."""
        blocks = [sample_block_with_bindings, sample_block_without_bindings]
        
        valid_blocks, errors = validate_manuscript_blocks(
            blocks=blocks,
            available_claim_ids=available_claim_ids,
            rigor_level="exploratory",
        )
        
        assert len(valid_blocks) == 2  # All blocks allowed
        assert len(errors) == 0  # No errors (warnings logged but not returned)
    
    def test_handles_empty_blocks_list(self, available_claim_ids):
        """Asserts empty blocks list is handled gracefully."""
        blocks = []
        
        valid_blocks, errors = validate_manuscript_blocks(
            blocks=blocks,
            available_claim_ids=available_claim_ids,
            rigor_level="conservative",
        )
        
        assert len(valid_blocks) == 0
        assert len(errors) == 0
    
    def test_handles_none_available_claim_ids(
        self,
        sample_block_with_bindings,
    ):
        """Asserts validation works when available_claim_ids is None."""
        blocks = [sample_block_with_bindings]
        
        valid_blocks, errors = validate_manuscript_blocks(
            blocks=blocks,
            available_claim_ids=None,  # No validation against known IDs
            rigor_level="conservative",
        )
        
        # Should still require bindings, but not validate against known IDs
        assert len(valid_blocks) == 1  # Has bindings, so passes
        assert len(errors) == 0

