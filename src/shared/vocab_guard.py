"""
Vocabulary Guardrail utility for Project Vyasa.

Loads forbidden vocabulary from ArangoDB (system of record) and applies constraints to prompts
to prevent the use of prohibited words in attorney-style write-ups.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class VocabGuard:
    """Manages forbidden vocabulary constraints (DB-backed)."""
    
    def __init__(self, service=None):
        """Initialize the vocabulary guard.
        
        Args:
            service: Optional VocabGuardService instance. If None, will use global instance.
        """
        from .vocab_guard_service import get_vocab_guard_service
        self.service = service or get_vocab_guard_service()
        self._forbidden_words: Dict[str, str] = {}  # word -> alternative mapping
        self._load_vocab()
    
    def _load_vocab(self) -> None:
        """Load forbidden vocabulary from database."""
        try:
            self._forbidden_words = self.service.get_all_words(include_inactive=False)
            
            logger.info(
                f"Loaded {len(self._forbidden_words)} forbidden words from database",
                extra={"payload": {"count": len(self._forbidden_words)}},
            )
        except Exception as e:
            logger.error(
                f"Failed to load forbidden vocabulary: {e}",
                exc_info=True,
            )
            self._forbidden_words = {}
    
    def apply_constraints(self, prompt: str) -> str:
        """Append negative constraint block to prompt.
        
        Args:
            prompt: Original prompt string.
            
        Returns:
            Prompt with vocabulary constraints appended.
        """
        if not self._forbidden_words:
            return prompt
        
        # Build forbidden words list
        forbidden_list = sorted(self._forbidden_words.keys())
        words_str = ", ".join(f'"{word}"' for word in forbidden_list)
        
        # Build alternatives mapping
        alternatives_list = []
        for word, alt in sorted(self._forbidden_words.items()):
            if alt:
                alternatives_list.append(f'"{word}" → "{alt}"')
            else:
                alternatives_list.append(f'"{word}" → (use appropriate alternative)')
        
        alternatives_str = "\n  ".join(alternatives_list)
        
        # Append constraint block
        constraint_block = f"""

---
NEGATIVE CONSTRAINT:
DO NOT use the following words: [{words_str}]

Use these alternatives instead:
  {alternatives_str}

If you encounter any of these words in your response, replace them with the suggested alternatives or appropriate synonyms that maintain the professional, attorney-style tone.
---
"""
        
        return prompt + constraint_block
    
    def get_forbidden_words(self) -> List[str]:
        """Get list of forbidden words.
        
        Returns:
            List of forbidden words (lowercased).
        """
        return sorted(self._forbidden_words.keys())
    
    def get_alternatives(self) -> Dict[str, str]:
        """Get mapping of forbidden words to alternatives.
        
        Returns:
            Dictionary mapping forbidden words (lowercased) to alternatives.
        """
        return self._forbidden_words.copy()
    
    def check_forbidden(self, text: str) -> Optional[str]:
        """Check if text contains any forbidden words (case-insensitive).
        
        Args:
            text: Text to check.
            
        Returns:
            First forbidden word found (lowercased), or None if none found.
        """
        text_lower = text.lower()
        for word in self._forbidden_words.keys():
            # Simple word boundary check (approximate)
            # This is a basic check; critic_node will use more sophisticated regex
            if word in text_lower:
                return word
        return None


# Global instance (lazy-loaded)
_guard_instance: Optional[VocabGuard] = None


def get_vocab_guard(service=None) -> VocabGuard:
    """Get or create the global VocabGuard instance.
    
    Args:
        service: Optional VocabGuardService instance. If None, will use global instance.
        
    Returns:
        VocabGuard instance.
    """
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = VocabGuard(service=service)
    return _guard_instance

