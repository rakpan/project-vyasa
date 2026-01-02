from src.orchestrator.state import ResearchState


def test_reducer_additive_lists():
    state: ResearchState = {
        "triples": [{"id": 1}],
        "artifacts": [{"id": "a1"}],
    }

    # Simulate second node emission
    update: ResearchState = {
        "triples": [{"id": 2}],
        "artifacts": [{"id": "a2"}],
    }

    # Reducer semantics: extend lists, not overwrite
    merged: ResearchState = {
        "triples": state["triples"] + update["triples"],
        "artifacts": state["artifacts"] + update["artifacts"],
    }

    assert merged["triples"] == [{"id": 1}, {"id": 2}]
    assert merged["artifacts"] == [{"id": "a1"}, {"id": "a2"}]
