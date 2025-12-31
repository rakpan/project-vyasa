"""
Loader utilities for rigor and tone policy configuration.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import logging

import yaml

BASE_DIR = Path(__file__).resolve().parents[2]
DEPLOY_DIR = BASE_DIR / "deploy"
logger = logging.getLogger(__name__)


def _load_yaml(default_path: Path, override_path: Optional[Path] = None) -> Dict[str, Any]:
    path = override_path or default_path
    if not path.exists():
        logger.warning(f"Rigor config missing: {path}")
        return {}
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        logger.warning(f"Rigor config empty: {path}")
        return {}
    data = yaml.safe_load(raw)
    return data or {}


def load_neutral_tone_yaml(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load neutral tone configuration."""
    return _load_yaml(DEPLOY_DIR / "neutral_tone.yaml", path)


def load_rigor_policy_yaml(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load rigor policy configuration."""
    return _load_yaml(DEPLOY_DIR / "rigor_policy.yaml", path)
