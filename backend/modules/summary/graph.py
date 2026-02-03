from langgraph.graph import StateGraph, START, END

from backend.modules.summary.state import SummaryState
from backend.modules.summary.nodes import (
    generate_summary_node,
    post_to_slack_node,
    create_postmortem_node,
)


def build_summary_subgraph() -> StateGraph:
    """
    Build the Summary subgraph.

    WHY THIS STRUCTURE?
    - Simple sequential flow for summary generation
    - Each node has a single responsibility
    - Easy to add more steps (e.g., send email, update dashboard)

    Flow:
        START
          ↓
        generate_summary - Create comprehensive summary text
          ↓
        post_to_slack - Post summary to incident thread
          ↓
        create_postmortem - Create ticket for high/critical incidents
          ↓
        END

    Returns:
        StateGraph ready for compilation
    """
    graph = StateGraph(SummaryState)

    # Add nodes
    graph.add_node("generate_summary", generate_summary_node)
    graph.add_node("post_to_slack", post_to_slack_node)
    graph.add_node("create_postmortem", create_postmortem_node)

    # Add edges (sequential flow)
    graph.add_edge(START, "generate_summary")
    graph.add_edge("generate_summary", "post_to_slack")
    graph.add_edge("post_to_slack", "create_postmortem")
    graph.add_edge("create_postmortem", END)

    return graph


# Compile the subgraph
# NOTE: Summary agent doesn't need a checkpointer since it doesn't use interrupt()
# It runs synchronously after execution completes
summary_subgraph = build_summary_subgraph().compile()
