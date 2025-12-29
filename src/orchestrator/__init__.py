"""Orchestrator module for LangGraph supervisor workflow."""

from typing import TYPE_CHECKING

# Define export list explicitly
__all__ = ["Supervisor", "SupervisorState", "NextStep", "create_supervisor"]

if TYPE_CHECKING:
    from .supervisor import Supervisor, SupervisorState, NextStep, create_supervisor


def __getattr__(name: str):
    """Lazy import pattern to avoid import errors during pytest collection."""
    if name in __all__:
        from .supervisor import (
            Supervisor,
            SupervisorState,
            NextStep,
            create_supervisor,
        )
        # Cache the import in the module namespace
        import sys
        module = sys.modules[__name__]
        attr_map = {
            "Supervisor": Supervisor,
            "SupervisorState": SupervisorState,
            "NextStep": NextStep,
            "create_supervisor": create_supervisor,
        }
        attr = attr_map[name]
        setattr(module, name, attr)
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

