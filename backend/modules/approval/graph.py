from langgraph.graph import StateGraph, START, END

from backend.modules.approval.state import ApprovalState
from backend.modules.approval.nodes import (
    format_approval_node,
    send_to_slack_node,
    wait_for_decision_node,
    process_decision_node,
)

from backend.modules.orchestrator.checkpointer import get_checkpointer

def build_approval_subgraph() -> StateGraph:
    """
    Build the Approval subgraph.

    This creates the graph structure but does NOT compile it.
    The orchestrator will compile it with a checkpointer.

    WHY NOT COMPILE HERE?
    - The checkpointer needs to be shared across subgraphs
    - The orchestrator controls the checkpointer configuration
    - This allows different checkpointers for dev/test/prod

    Returns:
        StateGraph ready for compilation
    """
    # Create the graph with our state schema
    graph = StateGraph(ApprovalState)

    graph.add_node("format_approval", format_approval_node)
    graph.add_node("send_to_slack", send_to_slack_node)
    graph.add_node("wait_for_decision", wait_for_decision_node)
    graph.add_node("process_decision", process_decision_node)

    graph.add_edge(START, "format_approval")
    graph.add_edge("format_approval", "send_to_slack")
    graph.add_edge("send_to_slack", "wait_for_decision")
    graph.add_edge("wait_for_decision", "process_decision")
    graph.add_edge("process_decision", END)

    return graph



_checkpointer = get_checkpointer()
approval_subgraph = build_approval_subgraph().compile(
    checkpointer=_checkpointer
)
