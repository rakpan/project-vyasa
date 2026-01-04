"""
Unit tests for TelemetryEmitter singleton factory.

Tests verify that:
- Only one TelemetryEmitter instance is created across all modules
- reset_for_tests() clears the singleton properly
- Multiple calls to get_telemetry_emitter() return the same instance
"""

import pytest
from unittest.mock import patch, MagicMock

# Import from telemetry package (telemetry/__init__.py re-exports from telemetry.py)
from src.orchestrator.telemetry import (
    get_telemetry_emitter,
    reset_for_tests,
    reset_telemetry_emitter,
    TelemetryEmitter,
)


class TestTelemetryEmitterSingleton:
    """Tests for TelemetryEmitter singleton behavior."""
    
    def test_get_telemetry_emitter_returns_singleton(self):
        """Test that get_telemetry_emitter() returns the same instance on multiple calls."""
        # Reset first to ensure clean state
        reset_for_tests()
        
        emitter1 = get_telemetry_emitter()
        emitter2 = get_telemetry_emitter()
        emitter3 = get_telemetry_emitter()
        
        # All should be the same instance
        assert emitter1 is emitter2
        assert emitter2 is emitter3
        assert emitter1 is emitter3
    
    def test_reset_for_tests_clears_singleton(self):
        """Test that reset_for_tests() clears the singleton."""
        # Get initial instance
        emitter1 = get_telemetry_emitter()
        
        # Reset
        reset_for_tests()
        
        # Get new instance
        emitter2 = get_telemetry_emitter()
        
        # Should be different instances
        assert emitter1 is not emitter2
    
    def test_reset_telemetry_emitter_clears_singleton(self):
        """Test that reset_telemetry_emitter() clears the singleton."""
        # Get initial instance
        emitter1 = get_telemetry_emitter()
        
        # Reset using reset_telemetry_emitter
        reset_telemetry_emitter()
        
        # Get new instance
        emitter2 = get_telemetry_emitter()
        
        # Should be different instances
        assert emitter1 is not emitter2
    
    def test_reset_for_tests_safe_to_call_multiple_times(self):
        """Test that reset_for_tests() is safe to call multiple times."""
        # Call multiple times - should not raise
        reset_for_tests()
        reset_for_tests()
        reset_for_tests()
        
        # Should still work after multiple resets
        emitter = get_telemetry_emitter()
        assert emitter is not None
        assert isinstance(emitter, TelemetryEmitter)
    
    def test_emitter_is_telemetry_emitter_instance(self):
        """Test that get_telemetry_emitter() returns a TelemetryEmitter instance."""
        reset_for_tests()
        
        emitter = get_telemetry_emitter()
        assert isinstance(emitter, TelemetryEmitter)
        assert hasattr(emitter, 'emit_event')
        assert callable(emitter.emit_event)
    
    def test_multiple_modules_get_same_instance(self):
        """Test that different modules calling get_telemetry_emitter() get the same instance."""
        reset_for_tests()
        
        # Simulate different modules importing
        from src.orchestrator.telemetry import get_telemetry_emitter as get_emitter_1
        from src.orchestrator.services.telemetry import get_telemetry_emitter as get_emitter_2
        
        emitter1 = get_emitter_1()
        emitter2 = get_emitter_2()
        
        # Should be the same instance
        assert emitter1 is emitter2


class TestTelemetryEmitterIntegration:
    """Integration tests for telemetry emitter usage across modules."""
    
    def test_server_and_nodes_use_same_instance(self):
        """Test that server.py and nodes modules use the same emitter instance."""
        reset_for_tests()
        
        # Import emitters from different modules
        from src.orchestrator.server import telemetry_emitter as server_emitter
        from src.orchestrator.nodes.nodes import telemetry_emitter as nodes_emitter
        from src.orchestrator.api.jobs import telemetry_emitter as jobs_emitter
        
        # All should be the same instance
        assert server_emitter is nodes_emitter
        assert nodes_emitter is jobs_emitter
        assert server_emitter is jobs_emitter
    
    def test_services_use_same_instance(self):
        """Test that services modules use the same emitter instance."""
        reset_for_tests()
        
        from src.orchestrator.services.telemetry import get_telemetry_emitter as get_service_emitter
        from src.orchestrator.services.metrics import _get_telemetry_emitter as get_metrics_emitter
        from src.orchestrator.telemetry import get_telemetry_emitter as get_main_emitter
        
        service_emitter = get_service_emitter()
        metrics_emitter = get_metrics_emitter()
        main_emitter = get_main_emitter()
        
        # All should be the same instance
        assert service_emitter is metrics_emitter
        assert metrics_emitter is main_emitter
        assert service_emitter is main_emitter

