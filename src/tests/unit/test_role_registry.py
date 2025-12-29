"""
Unit tests for the dynamic RoleRegistry (Arango-backed).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from ...shared.role_manager import RoleRegistry
from ...shared.schema import RoleProfile
# Older arango client versions may not expose DocumentNotFoundError; define fallback for tests.
try:  # pragma: no cover - defensive import
    from arango.exceptions import DocumentNotFoundError  # type: ignore
except Exception:  # pragma: no cover
    class DocumentNotFoundError(Exception):
        pass


class FakeCollection:
    def __init__(self):
        self.docs: Dict[str, Dict[str, Any]] = {}
        self.indexes = set()

    def get(self, key: str) -> Dict[str, Any] | None:
        return self.docs.get(key)

    def insert(self, doc: Dict[str, Any]) -> None:
        self.docs[doc["_key"]] = doc

    def update(self, doc: Dict[str, Any]) -> None:
        key = doc["_key"]
        if key not in self.docs:
            raise DocumentNotFoundError()
        self.docs[key].update(doc)

    def has_index(self, name: str) -> bool:
        return name in self.indexes

    def add_index(self, spec: Dict[str, Any]) -> None:
        # Track by name or fields for idempotency
        name = spec.get("name") or "_".join(spec.get("fields", []))
        self.indexes.add(name)


class FakeAQL:
    def __init__(self, collection: FakeCollection):
        self.collection = collection

    def execute(self, query: str, bind_vars: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        docs = list(self.collection.docs.values())
        bind_vars = bind_vars or {}

        if "role.name == @name AND role.version == @version" in query:
            return [d for d in docs if d["name"] == bind_vars["name"] and d["version"] == bind_vars["version"]]

        if "role.name == @name AND role.is_enabled == true" in query:
            candidates = [d for d in docs if d["name"] == bind_vars["name"] and d.get("is_enabled", True)]
            return sorted(candidates, key=lambda d: d["version"], reverse=True)[:1]

        if "role.is_enabled == true" in query and "role.name" in query:
            name = bind_vars.get("name")
            filtered = [d for d in docs if (name is None or d["name"] == name) and d.get("is_enabled", True)]
            return sorted(filtered, key=lambda d: (d["name"], -d["version"]))

        return docs


class FakeDB:
    def __init__(self):
        self.collection_obj = FakeCollection()
        self.aql = FakeAQL(self.collection_obj)

    def has_collection(self, _name: str) -> bool:
        return True

    def create_collection(self, _name: str, edge: bool | None = None) -> FakeCollection:
        self.collection_obj = FakeCollection()
        self.aql = FakeAQL(self.collection_obj)
        return self.collection_obj

    def collection(self, _name: str) -> FakeCollection:
        return self.collection_obj


@pytest.fixture
def fake_registry(monkeypatch):
    """RoleRegistry instance backed by an in-memory fake Arango DB."""
    fake_db = FakeDB()

    def fake_init(self):
        self.db = fake_db

    monkeypatch.setattr(RoleRegistry, "_init_arangodb", fake_init)
    registry = RoleRegistry(arango_url="http://fake", arango_db="test", arango_user="root", arango_password="pass")
    return registry, fake_db


def make_role(name="The Cartographer", version=1, enabled=True) -> RoleProfile:
    return RoleProfile(
        name=name,
        description="Extracts graph",
        system_prompt="You are the Cartographer",
        version=version,
        allowed_tools=["extract"],
        focus_entities=["Vulnerability"],
        is_enabled=enabled,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def test_register_and_get_latest(fake_registry):
    registry, fake_db = fake_registry
    role_v1 = make_role(version=1)
    stored = registry.register_role(role_v1)
    assert stored.version == 1

    # Register newer enabled version
    registry.register_role(make_role(version=2))

    fetched = registry.get_role("The Cartographer")
    assert fetched.version == 2
    assert fetched.system_prompt.startswith("You are")


def test_get_specific_version(fake_registry):
    registry, _ = fake_registry
    registry.register_role(make_role(version=1))
    registry.register_role(make_role(version=2))

    fetched = registry.get_role("The Cartographer", version=1)
    assert fetched.version == 1


def test_disable_role_blocks_latest(fake_registry):
    registry, _ = fake_registry
    registry.register_role(make_role(version=1))
    registry.register_role(make_role(version=2))

    registry.disable_role("The Cartographer", version=2)
    fetched = registry.get_role("The Cartographer")
    # Should fall back to v1 because v2 is disabled
    assert fetched.version == 1


def test_get_role_fallback_when_db_unavailable(monkeypatch):
    """When DB is missing, registry should return default role and not crash."""
    registry = RoleRegistry.__new__(RoleRegistry)
    registry.db = None
    default_role = registry._get_default_role("Extractor_v1")
    assert default_role.name == "Extractor_v1"
    assert default_role.system_prompt


def test_list_roles_returns_only_enabled(fake_registry):
    registry, _ = fake_registry
    registry.register_role(make_role(version=1, enabled=True))
    registry.register_role(make_role(version=2, enabled=False))

    roles = registry.list_roles(name="The Cartographer")
    assert len(roles) == 1
    assert roles[0].version == 1
