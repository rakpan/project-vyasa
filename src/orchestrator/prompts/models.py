"""
Prompt metadata models for tracking prompt usage in Vyasa.

Provides models for recording which prompts were used by which nodes,
enabling reproducibility and Opik-driven refinement.
"""

import hashlib
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class PromptUse(BaseModel):
    """Metadata about a prompt used in a job run.
    
    Records which prompt asset was used, where it came from (Opik or default),
    and when it was retrieved. This enables reproducibility and traceability.
    """
    prompt_name: str = Field(..., description="Name of the prompt (e.g., 'vyasa-cartographer')")
    tag: str = Field(default="production", description="Tag/version of the prompt")
    resolved_source: Literal["opik", "default"] = Field(
        ...,
        description="Source of the prompt: 'opik' if fetched from Opik, 'default' if using factory default"
    )
    retrieved_at: str = Field(..., description="ISO timestamp when prompt was retrieved")
    prompt_hash: str = Field(..., description="SHA256 hash of the prompt template for verification")
    cache_hit: Optional[bool] = Field(None, description="Whether the prompt was served from cache (None if unknown)")

    @classmethod
    def from_template(
        cls,
        prompt_name: str,
        template: str,
        resolved_source: Literal["opik", "default"],
        tag: str = "production",
        cache_hit: Optional[bool] = None,
    ) -> "PromptUse":
        """Create PromptUse from a template string.
        
        Args:
            prompt_name: Name of the prompt
            template: Prompt template string
            resolved_source: Source of the prompt
            tag: Tag/version of the prompt
            cache_hit: Whether this was a cache hit
        
        Returns:
            PromptUse instance with computed hash and timestamp
        """
        # Compute SHA256 hash of template
        prompt_hash = hashlib.sha256(template.encode("utf-8")).hexdigest()
        
        # Get current UTC timestamp
        from datetime import timezone
        retrieved_at = datetime.now(timezone.utc).isoformat()
        
        return cls(
            prompt_name=prompt_name,
            tag=tag,
            resolved_source=resolved_source,
            retrieved_at=retrieved_at,
            prompt_hash=prompt_hash,
            cache_hit=cache_hit,
        )

