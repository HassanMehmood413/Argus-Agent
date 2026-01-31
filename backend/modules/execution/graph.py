from langgraph.graph import StateGraph, START, END

from backend.modules.execution.state import ExecutorState
from backend.modules.execution.nodes import (
    # Main nodes
    validate_actions_node,
    prepare_next_action_node,
    request_approval_node,
    execute_action_node,
    notify_slack_node,
    record_result_node,
    record_skip_node,
    notify_skip_node,
    handle_abort_node,
    summarize_results_node,
    # Routing functions
    route_by_risk,
    route_after_approval,
    route_has_more_actions,
)
from backend.modules.orchestrator.checkpointer import get_checkpointer


def build_executor_subgraph() -> StateGraph:
    """
    Build the Executor subgraph with human-in-the-loop.

    This graph:
    1. Validates approved actions
    2. Loops through each action
    3. Auto-executes low-risk, requests approval for high-risk
    4. Notifies Slack after each action
    5. Creates a summary at the end

    Returns:
        StateGraph ready for compilation
    """
    graph = StateGraph(ExecutorState)

    graph.add_node("validate_actions", validate_actions_node)
    graph.add_node("prepare_next_action", prepare_next_action_node)
    graph.add_node("request_approval", request_approval_node)
    graph.add_node("execute_action", execute_action_node)
    graph.add_node("notify_slack", notify_slack_node)
    graph.add_node("record_result", record_result_node)
    graph.add_node("record_skip", record_skip_node)
    graph.add_node("notify_skip", notify_skip_node)
    graph.add_node("handle_abort", handle_abort_node)
    graph.add_node("summarize_results", summarize_results_node)


    graph.add_edge(START, "validate_actions")
    graph.add_edge("validate_actions", "prepare_next_action")
    graph.add_conditional_edges(
        "prepare_next_action",
        route_by_risk,
        {
            "execute_action": "execute_action",
            "request_approval": "request_approval",
        }
    )

    graph.add_conditional_edges(
        "request_approval",
        route_after_approval,
        {
            "execute_action": "execute_action",
            "record_skip": "record_skip",
            "handle_abort": "handle_abort",
        }
    )

    graph.add_edge("execute_action", "notify_slack")
    graph.add_edge("notify_slack", "record_result")

    graph.add_conditional_edges(
        "record_result",
        route_has_more_actions,
        {
            "prepare_next_action": "prepare_next_action",
            "summarize_results": "summarize_results",
        }
    )

    graph.add_edge("record_skip", "notify_skip")
    graph.add_conditional_edges(
        "notify_skip",
        route_has_more_actions,
        {
            "prepare_next_action": "prepare_next_action",
            "summarize_results": "summarize_results",
        }
    )

    graph.add_edge("handle_abort", "summarize_results")
    graph.add_edge("summarize_results", END)

    return graph


_checkpointer = get_checkpointer()
executor_subgraph = build_executor_subgraph().compile(
    checkpointer=_checkpointer
)
