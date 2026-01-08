"""
Tests for model configuration consolidation to canonical variables.

Validates:
1. Canonical vars (TEXT_MODEL_ID, VISION_MODEL_ID, EMBEDDER_MODEL_ID) work correctly
2. Backward compatibility mapping from legacy vars
3. Deprecation warnings are emitted when legacy vars are used
"""

import os
import warnings
import pytest
from unittest.mock import patch


def test_canonical_text_model_id_takes_precedence(monkeypatch):
    """Test that TEXT_MODEL_ID takes precedence over legacy vars."""
    monkeypatch.setenv("TEXT_MODEL_ID", "canonical/text-model")
    monkeypatch.setenv("BRAIN_MODEL_PATH", "legacy/brain-model")
    monkeypatch.setenv("WORKER_MODEL_PATH", "legacy/worker-model")
    
    # Reload config to pick up new env vars
    import importlib
    import src.shared.config
    importlib.reload(src.shared.config)
    
    assert src.shared.config.TEXT_MODEL_ID == "canonical/text-model"
    assert src.shared.config.BRAIN_MODEL_PATH == "canonical/text-model"
    assert src.shared.config.WORKER_MODEL_PATH == "canonical/text-model"


def test_backward_compat_brain_model_path(monkeypatch):
    """Test backward compatibility: BRAIN_MODEL_PATH maps to TEXT_MODEL_ID."""
    monkeypatch.delenv("TEXT_MODEL_ID", raising=False)
    monkeypatch.delenv("WORKER_MODEL_PATH", raising=False)
    monkeypatch.setenv("BRAIN_MODEL_PATH", "legacy/brain-model")
    
    # Reload config
    import importlib
    import src.shared.config
    importlib.reload(src.shared.config)
    
    assert src.shared.config.TEXT_MODEL_ID == "legacy/brain-model"
    assert src.shared.config.BRAIN_MODEL_PATH == "legacy/brain-model"


def test_backward_compat_worker_model_path(monkeypatch):
    """Test backward compatibility: WORKER_MODEL_PATH maps to TEXT_MODEL_ID."""
    monkeypatch.delenv("TEXT_MODEL_ID", raising=False)
    monkeypatch.delenv("BRAIN_MODEL_PATH", raising=False)
    monkeypatch.setenv("WORKER_MODEL_PATH", "legacy/worker-model")
    
    # Reload config
    import importlib
    import src.shared.config
    importlib.reload(src.shared.config)
    
    assert src.shared.config.TEXT_MODEL_ID == "legacy/worker-model"
    assert src.shared.config.WORKER_MODEL_PATH == "legacy/worker-model"


def test_backward_compat_vision_model_path(monkeypatch):
    """Test backward compatibility: VISION_MODEL_PATH maps to VISION_MODEL_ID."""
    monkeypatch.delenv("VISION_MODEL_ID", raising=False)
    monkeypatch.setenv("VISION_MODEL_PATH", "legacy/vision-model")
    
    # Reload config
    import importlib
    import src.shared.config
    importlib.reload(src.shared.config)
    
    assert src.shared.config.VISION_MODEL_ID == "legacy/vision-model"
    assert src.shared.config.VISION_MODEL_PATH == "legacy/vision-model"


def test_backward_compat_embedding_model_path(monkeypatch):
    """Test backward compatibility: EMBEDDING_MODEL_PATH maps to EMBEDDER_MODEL_ID."""
    monkeypatch.delenv("EMBEDDER_MODEL_ID", raising=False)
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "legacy/embedding-model")
    
    # Reload config
    import importlib
    import src.shared.config
    importlib.reload(src.shared.config)
    
    assert src.shared.config.EMBEDDER_MODEL_ID == "legacy/embedding-model"
    assert src.shared.config.EMBEDDING_MODEL_PATH == "legacy/embedding-model"


def test_deprecation_warning_brain_model_path(monkeypatch):
    """Test that deprecation warning is emitted when BRAIN_MODEL_PATH is used."""
    monkeypatch.delenv("TEXT_MODEL_ID", raising=False)
    monkeypatch.delenv("WORKER_MODEL_PATH", raising=False)
    monkeypatch.setenv("BRAIN_MODEL_PATH", "legacy/brain-model")
    
    # Reload config and capture warnings
    import importlib
    import src.shared.config
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        importlib.reload(src.shared.config)
        
        # Check that deprecation warning was emitted
        deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
        assert len(deprecation_warnings) > 0
        assert "BRAIN_MODEL_PATH is deprecated" in str(deprecation_warnings[0].message)


def test_deprecation_warning_worker_model_path(monkeypatch):
    """Test that deprecation warning is emitted when WORKER_MODEL_PATH is used."""
    monkeypatch.delenv("TEXT_MODEL_ID", raising=False)
    monkeypatch.delenv("BRAIN_MODEL_PATH", raising=False)
    monkeypatch.setenv("WORKER_MODEL_PATH", "legacy/worker-model")
    
    # Reload config and capture warnings
    import importlib
    import src.shared.config
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        importlib.reload(src.shared.config)
        
        # Check that deprecation warning was emitted
        deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
        assert len(deprecation_warnings) > 0
        assert "WORKER_MODEL_PATH is deprecated" in str(deprecation_warnings[0].message)


def test_model_registry_uses_canonical_vars(monkeypatch):
    """Test that model registry uses canonical vars (TEXT_MODEL_ID for both brain and worker)."""
    monkeypatch.setenv("TEXT_MODEL_ID", "test/text-model")
    monkeypatch.setenv("VISION_MODEL_ID", "test/vision-model")
    monkeypatch.setenv("EMBEDDER_MODEL_ID", "test/embedder-model")
    
    # Reload config and model registry
    import importlib
    import src.shared.config
    import src.shared.model_registry
    importlib.reload(src.shared.config)
    importlib.reload(src.shared.model_registry)
    
    # Both brain and worker should use TEXT_MODEL_ID
    brain_config = src.shared.model_registry.get_model_config("brain")
    worker_config = src.shared.model_registry.get_model_config("worker")
    vision_config = src.shared.model_registry.get_model_config("vision")
    embedder_config = src.shared.model_registry.get_model_config("embedder")
    
    assert brain_config.model_id == "test/text-model"
    assert worker_config.model_id == "test/text-model"
    assert vision_config.model_id == "test/vision-model"
    assert embedder_config.model_id == "test/embedder-model"
    
    # Brain and Worker should have the same model_id (same model, different services)
    assert brain_config.model_id == worker_config.model_id

