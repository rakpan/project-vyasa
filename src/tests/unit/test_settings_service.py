"""
Unit tests for Settings Service.

Tests settings persistence, retrieval, and validation.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock

from src.orchestrator.services.settings_service import SettingsService, SYSTEM_SETTINGS_KEY
from src.orchestrator.schemas.settings import SystemSettings, RuntimeBudgets, TierABudgets, TierBBudgets


@pytest.fixture
def mock_db():
    """Mock ArangoDB database."""
    db = Mock()
    coll = Mock()
    db.collection.return_value = coll
    db.has_collection.return_value = True
    coll.get.return_value = None
    coll.insert.return_value = None
    return db


def test_get_settings_defaults(mock_db):
    """Test getting default settings when none exist."""
    service = SettingsService(mock_db)
    settings = service.get_settings()
    
    assert isinstance(settings, SystemSettings)
    assert settings._key == SYSTEM_SETTINGS_KEY
    assert settings.runtime_budgets.tier_a.retrieval_top_k == 64
    assert settings.runtime_budgets.tier_b.critic_bounded_retry_max == 1


def test_get_settings_existing(mock_db):
    """Test getting existing settings."""
    existing_doc = {
        "_key": SYSTEM_SETTINGS_KEY,
        "runtime_budgets": {
            "tier_a": {
                "retrieval_top_k": 128,
                "rerank_top_m": 32,
            },
            "tier_b": {
                "critic_bounded_retry_max": 2,
            },
        },
    }
    mock_db.collection.return_value.get.return_value = existing_doc
    
    service = SettingsService(mock_db)
    settings = service.get_settings()
    
    assert settings.runtime_budgets.tier_a.retrieval_top_k == 128
    assert settings.runtime_budgets.tier_a.rerank_top_m == 32
    assert settings.runtime_budgets.tier_b.critic_bounded_retry_max == 2


def test_update_settings(mock_db):
    """Test updating settings."""
    service = SettingsService(mock_db)
    
    settings = SystemSettings()
    settings.runtime_budgets.tier_a.retrieval_top_k = 96
    
    updated = service.update_settings(settings, updated_by="test_user")
    
    assert updated.runtime_budgets.tier_a.retrieval_top_k == 96
    assert updated.updated_by == "test_user"
    assert updated.updated_at is not None
    mock_db.collection.return_value.insert.assert_called_once()


def test_update_settings_validation_error(mock_db):
    """Test that invalid settings raise validation error."""
    service = SettingsService(mock_db)
    
    settings = SystemSettings()
    settings.runtime_budgets.tier_a.retrieval_top_k = -1  # Invalid: must be >= 1
    
    with pytest.raises(Exception):  # Pydantic validation error
        service.update_settings(settings)


# ============================================================================
# Audit Fields Tests
# ============================================================================

def test_update_settings_sets_audit_fields(mock_db):
    """Test that update_settings sets updated_at and updated_by audit fields."""
    service = SettingsService(mock_db)
    
    settings = SystemSettings()
    settings.runtime_budgets.tier_a.retrieval_top_k = 96
    
    # Capture the update call
    update_called = False
    updated_doc = None
    
    def mock_update(doc):
        nonlocal update_called, updated_doc
        update_called = True
        updated_doc = doc
        return doc
    
    mock_db.collection.return_value.update = mock_update
    
    updated = service.update_settings(settings, updated_by="test_user@example.com")
    
    # Verify audit fields are set
    assert updated.updated_by == "test_user@example.com"
    assert updated.updated_at is not None
    assert isinstance(updated.updated_at, datetime)
    assert updated.updated_at.tzinfo is not None  # Should be timezone-aware
    
    # Verify update was called with audit fields
    assert update_called
    assert updated_doc is not None
    assert updated_doc["updated_by"] == "test_user@example.com"
    assert "updated_at" in updated_doc


def test_update_settings_audit_fields_timezone_aware(mock_db):
    """Test that updated_at is timezone-aware UTC."""
    service = SettingsService(mock_db)
    
    settings = SystemSettings()
    
    updated = service.update_settings(settings, updated_by="test_user")
    
    # Verify timestamp is UTC and timezone-aware
    assert updated.updated_at.tzinfo is not None
    assert updated.updated_at.tzinfo == timezone.utc or updated.updated_at.tzinfo.utcoffset(None).total_seconds() == 0


def test_update_settings_default_updated_by(mock_db):
    """Test that updated_by defaults to 'system' if not provided."""
    service = SettingsService(mock_db)
    
    settings = SystemSettings()
    
    updated = service.update_settings(settings)  # No updated_by provided
    
    assert updated.updated_by == "system"
