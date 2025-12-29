"""
Workflow loop routing tests.
"""

from ...orchestrator.workflow import _critic_router
from ...orchestrator.state import PaperState


def test_router_stops_after_max_retries():
    """When failures exceed the retry budget, workflow should go to saver."""
    state: PaperState = {"critic_status": "fail", "revision_count": 3}
    route = _critic_router(state)
    assert route == "manual"
