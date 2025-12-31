import pytest

from src.shared.model_router import ModelRouter, RouteRequest
from src.shared.model_registry import get_model_config


def test_router_disabled_uses_defaults():
    router = ModelRouter(enabled=False)
    req = RouteRequest(task_type="extract")
    cfg = router.route(req)
    assert cfg == get_model_config("worker")


@pytest.mark.parametrize(
    "task,expected",
    [
        ("extract", "worker"),
        ("kg", "worker"),
        ("qa", "brain"),
        ("summarize", "brain"),
        ("adjudicate", "brain"),
        ("vision", "vision"),
        ("embeddings", "embedder"),
    ],
)
def test_router_enabled_routes_examples(task, expected):
    router = ModelRouter(enabled=True)
    req = RouteRequest(task_type=task)
    cfg = router.route(req)
    assert cfg == get_model_config(expected)
