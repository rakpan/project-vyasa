"""
Citation Integrity Validator for Manuscript Blocks.

Ensures that every synthesized output is bound to claim IDs.
Prevents free prose by requiring structural claim bindings.

Conservative mode: fails if block has no claim bindings or references unknown claim_id.
Exploratory mode: warns + allows, but still prefers bindings.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)


def extract_claim_ids_from_text(text: str) -> List[str]:
    """Extract claim IDs from inline references in text.
    
    Supports format: [[claim_id_123]] or [[claim_id_456]]
    
    Args:
        text: Block text content.
    
    Returns:
        List of claim IDs found in inline references.
    """
    if not text:
        return []
    
    # Match inline references: [[claim_id_...]]
    pattern = r'\[\[([^\]]+)\]\]'
    matches = re.findall(pattern, text)
    
    # Filter out empty matches and normalize
    claim_ids = [match.strip() for match in matches if match.strip()]
    
    return claim_ids


def validate_citation_integrity(
    block: Dict[str, Any],
    available_claim_ids: Optional[List[str]] = None,
    rigor_level: str = "exploratory",
) -> Tuple[bool, Optional[str]]:
    """Validate citation integrity for a manuscript block.
    
    Ensures:
    - Block has claim_ids (required in conservative mode)
    - All referenced claim_ids exist in available_claim_ids (if provided)
    
    Args:
        block: Manuscript block dictionary with:
            - text or content: Block text
            - claim_ids: List of claim IDs (explicit bindings)
        available_claim_ids: Optional list of valid claim IDs to check against.
        rigor_level: "conservative" or "exploratory"
    
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if block passes validation
        - error_message: None if valid, error description if invalid
    """
    if not isinstance(block, dict):
        return False, "Block must be a dictionary"
    
    # Get block text
    block_text = block.get("text") or block.get("content", "")
    
    # Get explicit claim_ids from block metadata
    explicit_claim_ids = block.get("claim_ids", [])
    if not isinstance(explicit_claim_ids, list):
        explicit_claim_ids = []
    
    # Extract inline claim references from text
    inline_claim_ids = extract_claim_ids_from_text(block_text)
    
    # Combine all claim IDs (deduplicate)
    all_claim_ids = list(set(explicit_claim_ids + inline_claim_ids))
    
    # Conservative mode: require at least one claim binding
    if rigor_level == "conservative":
        if not all_claim_ids:
            return False, "Block has no claim bindings. Conservative mode requires at least one claim_id reference."
        
        # Validate that all claim IDs exist (if available_claim_ids provided)
        if available_claim_ids is not None:
            invalid_ids = [cid for cid in all_claim_ids if cid not in available_claim_ids]
            if invalid_ids:
                return False, f"Block references unknown claim_ids: {invalid_ids}"
    
    # Exploratory mode: warn but allow
    elif rigor_level == "exploratory":
        if not all_claim_ids:
            logger.warning(
                "Block has no claim bindings (exploratory mode allows)",
                extra={"payload": {"block_id": block.get("block_id", "unknown")}}
            )
        elif available_claim_ids is not None:
            invalid_ids = [cid for cid in all_claim_ids if cid not in available_claim_ids]
            if invalid_ids:
                logger.warning(
                    f"Block references unknown claim_ids: {invalid_ids} (exploratory mode allows)",
                    extra={"payload": {"block_id": block.get("block_id", "unknown")}}
                )
    
    return True, None


def validate_manuscript_blocks(
    blocks: List[Dict[str, Any]],
    available_claim_ids: Optional[List[str]] = None,
    rigor_level: str = "exploratory",
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Validate multiple manuscript blocks for citation integrity.
    
    Args:
        blocks: List of manuscript block dictionaries.
        available_claim_ids: Optional list of valid claim IDs to check against.
        rigor_level: "conservative" or "exploratory"
    
    Returns:
        Tuple of (valid_blocks, errors)
        - valid_blocks: List of blocks that passed validation
        - errors: List of error messages for invalid blocks
    """
    valid_blocks = []
    errors = []
    
    for block in blocks:
        is_valid, error_msg = validate_citation_integrity(
            block=block,
            available_claim_ids=available_claim_ids,
            rigor_level=rigor_level,
        )
        
        if is_valid:
            valid_blocks.append(block)
        else:
            block_id = block.get("block_id", "unknown")
            errors.append(f"Block {block_id}: {error_msg}")
            logger.error(
                f"Citation integrity validation failed for block {block_id}",
                extra={"payload": {"error": error_msg, "rigor_level": rigor_level}}
            )
    
    return valid_blocks, errors

