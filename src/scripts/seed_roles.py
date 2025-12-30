"""
Seed roles with a default-overrides model.

- Public defaults live in src/scripts/defaults.json
- Private overrides live in data/private/expertise.json (ignored in git)
- Defaults are merged with private overrides (matching role names)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any

from src.shared.role_manager import RoleRegistry
from src.shared.schema import RoleProfile

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULTS_PATH = Path(__file__).resolve().with_name("defaults.json")
PRIVATE_OVERRIDES_PATH = PROJECT_ROOT / "data" / "private" / "expertise.json"


def _load_roles(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    roles = data.get("roles") if isinstance(data, dict) else {}
    if not isinstance(roles, dict):
        raise ValueError(f"Invalid roles structure in {path}")
    return roles


def merge_roles() -> Dict[str, Dict[str, Any]]:
    """Merge public defaults with private overrides (private wins on conflicts)."""
    baseline = _load_roles(DEFAULTS_PATH)
    overrides = _load_roles(PRIVATE_OVERRIDES_PATH)
    merged = {**baseline}
    for name, payload in overrides.items():
        merged[name] = {**baseline.get(name, {}), **payload}
    return merged


def seed_roles() -> None:
    merged_roles = merge_roles()
    if not merged_roles:
        logger.warning("No roles found to seed (defaults missing?)")
        return

    registry = RoleRegistry()
    logger.info("Seeding roles into ArangoDB (defaults + private overrides)...")
    success = 0
    for name, payload in merged_roles.items():
        try:
            # Ensure name is set even if override omits it
            payload.setdefault("name", name)
            role = RoleProfile(**payload)
            registry.register_role(role)
            success += 1
            logger.info("Registered role", extra={"payload": {"name": role.name, "version": role.version}})
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to register role", extra={"payload": {"name": name, "error": str(exc)}})
    logger.info("Seeding complete", extra={"payload": {"success": success, "total": len(merged_roles)}})


if __name__ == "__main__":
    seed_roles()
