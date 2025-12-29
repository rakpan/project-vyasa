"""
Main orchestrator entry point for Project Vyasa.

This module demonstrates how to use the dynamic role system in the orchestrator.
It replaces hardcoded system prompts with roles fetched from ArangoDB.
"""

import logging
from typing import Optional

from .supervisor import Supervisor
from ..shared.role_manager import RoleRegistry
from ..shared.config import (
    get_cortex_url,
    get_drafter_url,
    get_memory_url,
    ARANGODB_DB,
    ARANGODB_USER,
    ARANGODB_PASSWORD
)
from ..shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

# Global registry instance (singleton pattern)
_registry: Optional[RoleRegistry] = None


def get_registry() -> RoleRegistry:
    """Get or create the global RoleRegistry instance."""
    global _registry
    if _registry is None:
        _registry = RoleRegistry(
            arango_url=get_memory_url(),
            arango_db=ARANGODB_DB,
            arango_user=ARANGODB_USER,
            arango_password=ARANGODB_PASSWORD
        )
    return _registry


def process_with_role(user_input: str, role_name: str = "The Cartographer") -> dict:
    """
    Process user input using a dynamic role from the registry.
    
    Args:
        user_input: The user's input text to process.
        role_name: Name of the role to use. Defaults to "The Cartographer".
    
    Returns:
        Dictionary with the processing result.
    """
    registry = get_registry()
    
    # Get the role dynamically
    extractor_role = registry.get_role(role_name)
    logger.info(f"Using role: {extractor_role.name} v{extractor_role.version}")
    
    # TODO: Use extractor_role.allowed_tools to configure tool availability
    # when SGLang/Cortex supports tool constraints
    
    # Example: Use the role's system prompt with Cortex
    # In a real implementation, this would call Cortex with the dynamic prompt
    cortex_url = get_cortex_url()
    
    # Placeholder for actual Cortex integration
    # response = cortex.chat(
    #     system=extractor_role.system_prompt,
    #     message=user_input,
    #     tools=extractor_role.allowed_tools  # TODO: Implement tool filtering
    # )
    
    logger.info(f"Role '{extractor_role.name}' system prompt length: {len(extractor_role.system_prompt)} chars")
    logger.info(f"Role '{extractor_role.name}' allowed tools: {extractor_role.allowed_tools}")
    logger.info(f"Role '{extractor_role.name}' focus entities: {extractor_role.focus_entities}")
    
    return {
        "role": extractor_role.name,
        "version": extractor_role.version,
        "system_prompt": extractor_role.system_prompt,
        "allowed_tools": extractor_role.allowed_tools,
        "focus_entities": extractor_role.focus_entities,
        "user_input": user_input,
        "cortex_url": cortex_url
    }


if __name__ == "__main__":
    # Example usage
    logger.info("Project Vyasa Orchestrator - Dynamic Role System Demo")
    
    # Initialize registry
    registry = get_registry()
    
    # List available roles
    roles = registry.list_roles()
    logger.info(f"Available roles: {[r.name for r in roles]}")
    
    # Process with a specific role
    result = process_with_role("Extract entities from this text: SQL injection is a vulnerability.", "The Cartographer")
    logger.info(f"Processing result: {result}")

