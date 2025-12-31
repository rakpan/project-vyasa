"""
ASGI entry point for the Vyasa Orchestrator.
"""

from .server import api_app as app

__all__ = ["app"]
