"""
Vocabulary Guardrail utility for Project Vyasa.

Loads forbidden vocabulary from YAML configuration and applies constraints to prompts
to prevent the use of prohibited words in attorney-style write-ups.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional
import yaml

logger = logging.getLogger(__name__)

# Default path to forbidden vocabulary YAML
DEFAULT_VOCAB_PATH = Path(__file__).resolve().parents[2] / "deploy" / "forbidden_vocab.yaml"


class VocabGuard:
    """Manages forbidden vocabulary constraints."""
    
    def __init__(self, vocab_path: Optional[Path] = None):
        """Initialize the vocabulary guard.
        
        Args:
            vocab_path: Path to forbidden_vocab.yaml file. Defaults to deploy/forbidden_vocab.yaml.
        """
        self.vocab_path = vocab_path or DEFAULT_VOCAB_PATH
        self._forbidden_words: Dict[str, str] = {}  # word -> alternative mapping
        self._load_vocab()
    
    def _load_vocab(self) -> None:
        """Load forbidden vocabulary from YAML file."""
        try:
            if not self.vocab_path.exists():
                logger.warning(
                    f"Forbidden vocabulary file not found: {self.vocab_path}. Using empty vocabulary.",
                    extra={"payload": {"vocab_path": str(self.vocab_path)}},
                )
                self._forbidden_words = {}
                return
            
            with open(self.vocab_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            # Extract forbidden words and alternatives
            forbidden_list = data.get("forbidden_words", [])
            if isinstance(forbidden_list, list):
                for item in forbidden_list:
                    if isinstance(item, dict):
                        word = item.get("word", "").strip().lower()
                        alt_val = item.get("alternative", "")
                        # Handle both string and list formats
                        if isinstance(alt_val, list):
                            alternative = " or ".join(str(a).strip() for a in alt_val if a)
                        else:
                            alternative = str(alt_val).strip()
                        if word:
                            self._forbidden_words[word] = alternative
                    elif isinstance(item, str):
                        # Simple string format: just the word
                        self._forbidden_words[item.strip().lower()] = ""
            elif isinstance(forbidden_list, dict):
                # Dictionary format: {word: alternative}
                self._forbidden_words = {
                    k.strip().lower(): (v.strip() if isinstance(v, str) else "")
                    for k, v in forbidden_list.items()
                }
            
            logger.info(
                f"Loaded {len(self._forbidden_words)} forbidden words from {self.vocab_path}",
                extra={"payload": {"vocab_path": str(self.vocab_path), "count": len(self._forbidden_words)}},
            )
        except Exception as e:
            logger.error(
                f"Failed to load forbidden vocabulary: {e}",
                extra={"payload": {"vocab_path": str(self.vocab_path)}},
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


def get_vocab_guard(vocab_path: Optional[Path] = None) -> VocabGuard:
    """Get or create the global VocabGuard instance.
    
    Args:
        vocab_path: Optional path to vocabulary file. Only used on first call.
        
    Returns:
        VocabGuard instance.
    """
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = VocabGuard(vocab_path)
    return _guard_instance

