"""
Agentic workflow wiring for Project Vyasa using LangGraph.
"""

from langgraph.graph import StateGraph, END

from .state import PaperState
from .nodes import cartographer_node, critic_node, saver_node, vision_node


def _critic_router(state: PaperState) -> str:
    """Route based on critic status and revision budget."""
    status = (state.get("critic_status") or "fail").lower()
    revisions = state.get("revision_count", 0)
    if status == "pass":
        return "pass"
    if revisions < 3:
        return "retry"
    return "manual"


def build_workflow():
    """Compile the Cartographer -> Critic loop with saver terminal."""
    graph = StateGraph(PaperState)

    graph.add_node("vision", vision_node)
    graph.add_node("cartographer", cartographer_node)
    graph.add_node("critic", critic_node)
    graph.add_node("saver", saver_node)

    graph.set_entry_point("vision")
    graph.add_edge("vision", "cartographer")
    graph.add_edge("cartographer", "critic")
    graph.add_conditional_edges(
        "critic",
        _critic_router,
        {
            "pass": "saver",
            "retry": "cartographer",
            "manual": "saver",
        },
    )
    graph.add_edge("saver", END)

    return graph.compile()
