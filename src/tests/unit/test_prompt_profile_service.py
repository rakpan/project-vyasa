"""
Unit tests for Prompt Profile Service.

Tests prompt profile creation, versioning, activation, and validation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch

from src.orchestrator.services.prompt_profile_service import PromptProfileService
from src.orchestrator.schemas.settings import PromptProfile, ActivePromptSet


@pytest.fixture
def mock_db():
    """Mock ArangoDB database."""
    db = Mock()
    profiles_coll = Mock()
    active_coll = Mock()
    
    db.collection.side_effect = lambda name: profiles_coll if name == "prompt_profiles" else active_coll
    db.has_collection.return_value = True
    db.aql.execute.return_value = []
    
    profiles_coll.get.return_value = None
    profiles_coll.insert.return_value = None
    active_coll.get.return_value = None
    active_coll.insert.return_value = None
    
    return db


def test_create_profile_first_version(mock_db):
    """Test creating first version of a prompt profile."""
    service = PromptProfileService(mock_db)
    
    profile = service.create_profile(
        prompt_id="critic_verify",
        template="You are a critic...",
        output_type="json",
        required_fields=["decision", "rationale"],
        created_by="test_user",
    )
    
    assert profile.prompt_id == "critic_verify"
    assert profile.version == 1
    assert profile.template == "You are a critic..."
    assert profile.output_type == "json"
    assert profile.required_fields == ["decision", "rationale"]
    assert profile.created_by == "test_user"


def test_create_profile_auto_increment_version(mock_db):
    """Test that version auto-increments."""
    # Mock existing version
    def mock_aql_execute(query, bind_vars):
        if "SORT p.version DESC" in query:
            return iter([3])  # Latest version is 3
        return iter([])
    
    mock_db.aql.execute.side_effect = mock_aql_execute
    
    service = PromptProfileService(mock_db)
    
    profile = service.create_profile(
        prompt_id="critic_verify",
        template="Updated template...",
        output_type="json",
        required_fields=["decision"],
    )
    
    assert profile.version == 4  # Next version after 3


def test_get_profile_by_version(mock_db):
    """Test getting a specific prompt profile version."""
    existing_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Template v2",
        "output_type": "json",
        "required_fields": ["decision"],
    }
    mock_db.collection.return_value.get.return_value = existing_doc
    
    service = PromptProfileService(mock_db)
    profile = service.get_profile("critic_verify", version=2)
    
    assert profile is not None
    assert profile.version == 2
    assert profile.template == "Template v2"


def test_get_profile_active_version(mock_db):
    """Test getting active version of a prompt profile."""
    # Mock active prompt set
    active_doc = {
        "_key": "active_prompt_set",
        "active_versions": {
            "critic_verify": 2,
        },
    }
    
    profile_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Active template",
        "output_type": "json",
        "required_fields": ["decision"],
    }
    
    def mock_collection(name):
        coll = Mock()
        if name == "active_prompt_set":
            coll.get.return_value = active_doc
        else:
            coll.get.return_value = profile_doc
        return coll
    
    mock_db.collection.side_effect = mock_collection
    
    service = PromptProfileService(mock_db)
    profile = service.get_profile("critic_verify")
    
    assert profile is not None
    assert profile.version == 2  # Active version


def test_activate_version(mock_db):
    """Test activating a prompt profile version."""
    # Mock profile exists with valid validation (required for activation)
    recent_timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
    profile_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Template",
        "output_type": "json",
        "required_fields": ["decision"],
        "validation_status": "valid",
        "validation_timestamp": recent_timestamp.isoformat(),
        "validation_errors": [],
    }
    
    active_doc = {
        "_key": "active_prompt_set",
        "active_versions": {},
    }
    
    def mock_collection(name):
        coll = Mock()
        if name == "prompt_profiles":
            coll.get.return_value = profile_doc
        elif name == "active_prompt_set":
            coll.get.return_value = active_doc
            coll.insert = Mock()
        return coll
    
    mock_db.collection.side_effect = mock_collection
    
    service = PromptProfileService(mock_db)
    active_set = service.activate_version("critic_verify", version=2, updated_by="test_user")
    
    assert active_set.active_versions["critic_verify"] == 2
    assert active_set.updated_by == "test_user"


def test_activate_version_not_found(mock_db):
    """Test that activating non-existent version raises error."""
    mock_db.collection.return_value.get.return_value = None  # Profile not found
    
    service = PromptProfileService(mock_db)
    
    with pytest.raises(ValueError, match="does not exist"):
        service.activate_version("critic_verify", version=999)


def test_validate_template_valid(mock_db):
    """Test validating a valid prompt template."""
    service = PromptProfileService(mock_db)
    
    result = service.validate_template(
        template="You are a critic...",
        output_type="json",
        required_fields=["decision", "rationale"],
    )
    
    assert result["valid"] is True
    assert len(result["errors"]) == 0


def test_validate_template_empty_required_fields_for_json(mock_db):
    """Test that JSON output type requires non-empty required_fields."""
    service = PromptProfileService(mock_db)
    
    result = service.validate_template(
        template="You are a critic...",
        output_type="json",
        required_fields=[],  # Empty!
    )
    
    assert result["valid"] is False
    assert any("required_fields" in error for error in result["errors"])


def test_validate_template_invalid_output_type(mock_db):
    """Test that invalid output_type is rejected."""
    service = PromptProfileService(mock_db)
    
    result = service.validate_template(
        template="Template",
        output_type="invalid_type",
        required_fields=[],
    )
    
    assert result["valid"] is False
    assert any("output_type" in error for error in result["errors"])


# ============================================================================
# Validation Persistence Tests
# ============================================================================

def test_update_validation_status_valid_result(mock_db):
    """Test that valid validation result persists correctly."""
    profile_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Template",
        "output_type": "json",
        "required_fields": ["decision"],
    }
    
    profiles_coll = Mock()
    profiles_coll.get.return_value = profile_doc
    profiles_coll.update = Mock()
    
    mock_db.collection.return_value = profiles_coll
    
    service = PromptProfileService(mock_db)
    
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": [],
    }
    
    service.update_validation_status("critic_verify", 2, validation_result)
    
    # Verify update was called with correct fields
    assert profiles_coll.update.called
    update_call_args = profiles_coll.update.call_args[0][0]
    assert update_call_args["validation_status"] == "valid"
    assert "validation_timestamp" in update_call_args
    assert update_call_args["validation_errors"] == []


def test_update_validation_status_invalid_result(mock_db):
    """Test that invalid validation result persists correctly."""
    profile_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Template",
        "output_type": "json",
        "required_fields": ["decision"],
    }
    
    profiles_coll = Mock()
    profiles_coll.get.return_value = profile_doc
    profiles_coll.update = Mock()
    
    mock_db.collection.return_value = profiles_coll
    
    service = PromptProfileService(mock_db)
    
    validation_result = {
        "valid": False,
        "errors": ["Template must include required fields", "Missing citation format"],
        "warnings": [],
    }
    
    service.update_validation_status("critic_verify", 2, validation_result)
    
    # Verify update was called with correct fields
    assert profiles_coll.update.called
    update_call_args = profiles_coll.update.call_args[0][0]
    assert update_call_args["validation_status"] == "invalid"
    assert "validation_timestamp" in update_call_args
    assert len(update_call_args["validation_errors"]) == 2
    assert "Template must include required fields" in update_call_args["validation_errors"]


def test_update_validation_status_profile_not_found(mock_db):
    """Test that updating validation status for non-existent profile raises error."""
    profiles_coll = Mock()
    profiles_coll.get.return_value = None  # Profile not found
    
    mock_db.collection.return_value = profiles_coll
    
    service = PromptProfileService(mock_db)
    
    validation_result = {"valid": True, "errors": []}
    
    with pytest.raises(ValueError, match="not found"):
        service.update_validation_status("critic_verify", 999, validation_result)


# ============================================================================
# Activation Gating Tests
# ============================================================================

def test_activate_version_no_validation_status(mock_db):
    """Test that activation fails if validation_status is missing."""
    profile_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Template",
        "output_type": "json",
        "required_fields": ["decision"],
        # No validation_status field
    }
    
    profiles_coll = Mock()
    profiles_coll.get.return_value = profile_doc
    
    def mock_collection(name):
        if name == "prompt_profiles":
            return profiles_coll
        return Mock()
    
    mock_db.collection.side_effect = mock_collection
    
    service = PromptProfileService(mock_db)
    
    with pytest.raises(ValueError, match="not validated"):
        service.activate_version("critic_verify", version=2)


def test_activate_version_invalid_status(mock_db):
    """Test that activation fails if validation_status is not 'valid'."""
    profile_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Template",
        "output_type": "json",
        "required_fields": ["decision"],
        "validation_status": "invalid",  # Invalid status
        "validation_timestamp": datetime.now(timezone.utc).isoformat(),
        "validation_errors": ["Some error"],
    }
    
    profiles_coll = Mock()
    profiles_coll.get.return_value = profile_doc
    
    def mock_collection(name):
        if name == "prompt_profiles":
            return profiles_coll
        return Mock()
    
    mock_db.collection.side_effect = mock_collection
    
    service = PromptProfileService(mock_db)
    
    with pytest.raises(ValueError, match="validation failed"):
        service.activate_version("critic_verify", version=2)


def test_activate_version_stale_timestamp(mock_db):
    """Test that activation fails if validation_timestamp is older than 30 minutes."""
    # Create a timestamp 31 minutes ago
    stale_timestamp = datetime.now(timezone.utc) - timedelta(minutes=31)
    
    profile_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Template",
        "output_type": "json",
        "required_fields": ["decision"],
        "validation_status": "valid",
        "validation_timestamp": stale_timestamp.isoformat(),
        "validation_errors": [],
    }
    
    profiles_coll = Mock()
    profiles_coll.get.return_value = profile_doc
    
    def mock_collection(name):
        if name == "prompt_profiles":
            return profiles_coll
        return Mock()
    
    mock_db.collection.side_effect = mock_collection
    
    service = PromptProfileService(mock_db)
    
    with pytest.raises(ValueError, match="validation is stale"):
        service.activate_version("critic_verify", version=2)


def test_activate_version_success_recent_valid(mock_db):
    """Test that activation succeeds with recent valid validation."""
    # Create a timestamp 5 minutes ago (within 30 minute threshold)
    recent_timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
    
    profile_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Template",
        "output_type": "json",
        "required_fields": ["decision"],
        "validation_status": "valid",
        "validation_timestamp": recent_timestamp.isoformat(),
        "validation_errors": [],
    }
    
    active_doc = {
        "_key": "active_prompt_set",
        "active_versions": {},
    }
    
    profiles_coll = Mock()
    profiles_coll.get.return_value = profile_doc
    
    active_coll = Mock()
    active_coll.get.return_value = active_doc
    active_coll.insert = Mock()
    
    def mock_collection(name):
        if name == "prompt_profiles":
            return profiles_coll
        elif name == "active_prompt_set":
            return active_coll
        return Mock()
    
    mock_db.collection.side_effect = mock_collection
    
    service = PromptProfileService(mock_db)
    
    active_set = service.activate_version("critic_verify", version=2, updated_by="test_user")
    
    assert active_set.active_versions["critic_verify"] == 2
    assert active_set.updated_by == "test_user"


# ============================================================================
# Timestamp Parsing Tests
# ============================================================================

def test_activate_version_timestamp_iso_with_timezone(mock_db):
    """Test that activation accepts ISO timestamp with +00:00 timezone."""
    recent_timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
    iso_timestamp = recent_timestamp.isoformat()  # Includes +00:00
    
    profile_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Template",
        "output_type": "json",
        "required_fields": ["decision"],
        "validation_status": "valid",
        "validation_timestamp": iso_timestamp,
        "validation_errors": [],
    }
    
    profiles_coll = Mock()
    profiles_coll.get.return_value = profile_doc
    
    active_coll = Mock()
    active_coll.get.return_value = {"_key": "active_prompt_set", "active_versions": {}}
    active_coll.insert = Mock()
    
    def mock_collection(name):
        if name == "prompt_profiles":
            return profiles_coll
        elif name == "active_prompt_set":
            return active_coll
        return Mock()
    
    mock_db.collection.side_effect = mock_collection
    
    service = PromptProfileService(mock_db)
    
    # Should not raise an error
    active_set = service.activate_version("critic_verify", version=2)
    assert active_set is not None


def test_activate_version_timestamp_iso_with_z(mock_db):
    """Test that activation accepts ISO timestamp with Z suffix."""
    recent_timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
    iso_timestamp_z = recent_timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")  # Z format
    
    profile_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Template",
        "output_type": "json",
        "required_fields": ["decision"],
        "validation_status": "valid",
        "validation_timestamp": iso_timestamp_z,
        "validation_errors": [],
    }
    
    profiles_coll = Mock()
    profiles_coll.get.return_value = profile_doc
    
    active_coll = Mock()
    active_coll.get.return_value = {"_key": "active_prompt_set", "active_versions": {}}
    active_coll.insert = Mock()
    
    def mock_collection(name):
        if name == "prompt_profiles":
            return profiles_coll
        elif name == "active_prompt_set":
            return active_coll
        return Mock()
    
    mock_db.collection.side_effect = mock_collection
    
    service = PromptProfileService(mock_db)
    
    # Should not raise an error
    active_set = service.activate_version("critic_verify", version=2)
    assert active_set is not None


def test_activate_version_timestamp_naive_datetime(mock_db):
    """Test that naive datetime is handled by assuming UTC."""
    # Create a naive datetime (no timezone)
    naive_timestamp = datetime.now() - timedelta(minutes=5)
    
    profile_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Template",
        "output_type": "json",
        "required_fields": ["decision"],
        "validation_status": "valid",
        "validation_timestamp": naive_timestamp,  # Naive datetime object
        "validation_errors": [],
    }
    
    profiles_coll = Mock()
    profiles_coll.get.return_value = profile_doc
    
    active_coll = Mock()
    active_coll.get.return_value = {"_key": "active_prompt_set", "active_versions": {}}
    active_coll.insert = Mock()
    
    def mock_collection(name):
        if name == "prompt_profiles":
            return profiles_coll
        elif name == "active_prompt_set":
            return active_coll
        return Mock()
    
    mock_db.collection.side_effect = mock_collection
    
    service = PromptProfileService(mock_db)
    
    # Should not raise an error (naive datetime assumed UTC)
    active_set = service.activate_version("critic_verify", version=2)
    assert active_set is not None


def test_activate_version_invalid_timestamp_blocks_activation(mock_db):
    """Test that invalid timestamp format blocks activation with clear error, no crash."""
    profile_doc = {
        "_key": "critic_verify_v2",
        "prompt_id": "critic_verify",
        "version": 2,
        "template": "Template",
        "output_type": "json",
        "required_fields": ["decision"],
        "validation_status": "valid",
        "validation_timestamp": "not-a-valid-timestamp",  # Invalid format
        "validation_errors": [],
    }
    
    profiles_coll = Mock()
    profiles_coll.get.return_value = profile_doc
    
    def mock_collection(name):
        if name == "prompt_profiles":
            return profiles_coll
        return Mock()
    
    mock_db.collection.side_effect = mock_collection
    
    service = PromptProfileService(mock_db)
    
    # Should raise ValueError with clear message, not crash
    with pytest.raises(ValueError, match="validation timestamp missing or invalid"):
        service.activate_version("critic_verify", version=2)
