from langgraph.graph import StateGraph, START, END

from backend.modules.orchestrator.state import OrchestratorState
from backend.modules.orchestrator.checkpointer import get_checkpointer
from backend.modules.orchestrator.nodes import (
    # Nodes
    receive_alert_node,
    run_monitor_node,
    run_analyzer_node,
    run_approval_node,
    skip_approval_node,
    handle_rejection_node,
    run_executor_node,
    run_summary_node,
    # Routing functions
    route_after_analyzer,
    route_after_approval,
    route_after_execution,
)


def build_orchestrator_graph() -> StateGraph:
    """
    Build the Orchestrator graph.

    This is the master graph that coordinates all subgraphs:
    - Monitor: Collects metrics, logs, pod status
    - Analyzer: Identifies root cause and recommends actions
    - Approval: Human-in-the-loop via Slack
    - Executor: Executes approved actions
    - Summary: Generates incident summary and postmortem

    Returns:
        StateGraph ready for compilation
    """
    graph = StateGraph(OrchestratorState)

    # ═══════════════════════════════════════════════════════════════════════
    # ADD NODES
    # ═══════════════════════════════════════════════════════════════════════

    # Entry point - initialize incident
    graph.add_node("receive_alert", receive_alert_node)

    # Data collection
    graph.add_node("run_monitor", run_monitor_node)

    # Analysis
    graph.add_node("run_analyzer", run_analyzer_node)

    # Approval (human-in-the-loop)
    graph.add_node("run_approval", run_approval_node)
    graph.add_node("skip_approval", skip_approval_node)

    # Rejection handling
    graph.add_node("handle_rejection", handle_rejection_node)

    # Execution
    graph.add_node("run_executor", run_executor_node)

    # Summary
    graph.add_node("run_summary", run_summary_node)

    # ═══════════════════════════════════════════════════════════════════════
    # ADD EDGES
    # ═══════════════════════════════════════════════════════════════════════

    # START -> receive_alert -> run_monitor -> run_analyzer
    graph.add_edge(START, "receive_alert")
    graph.add_edge("receive_alert", "run_monitor")
    graph.add_edge("run_monitor", "run_analyzer")

    # After analyzer: decide on approval
    graph.add_conditional_edges(
        "run_analyzer",
        route_after_analyzer,
        {
            "run_approval": "run_approval",
            "skip_approval": "skip_approval",
        }
    )

    # After approval: execute or handle rejection
    graph.add_conditional_edges(
        "run_approval",
        route_after_approval,
        {
            "run_executor": "run_executor",
            "handle_rejection": "handle_rejection",
        }
    )

    # Skip approval goes directly to executor
    graph.add_edge("skip_approval", "run_executor")

    # After rejection: go to summary (for record keeping)
    graph.add_edge("handle_rejection", "run_summary")

    # After execution: summary or end
    graph.add_conditional_edges(
        "run_executor",
        route_after_execution,
        {
            "run_summary": "run_summary",
            "__end__": END,
        }
    )

    # Summary -> END
    graph.add_edge("run_summary", END)

    return graph


# ═══════════════════════════════════════════════════════════════════════════════
# COMPILED GRAPH SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

# Get the checkpointer (for interrupt/resume support)
_checkpointer = get_checkpointer()

# Build and compile the orchestrator graph
orchestrator_graph = build_orchestrator_graph().compile(
    checkpointer=_checkpointer
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS FOR API
# ═══════════════════════════════════════════════════════════════════════════════

async def process_incident(
    alert: dict,
    severity: str = "medium",
    incident_id: str = None,
    slack_channel: str = None,
) -> dict:
    """
    Process an incident through the full orchestrator pipeline.

    This is the main entry point for the API.

    Args:
        alert: Alert data (alertname, service, namespace, labels, etc.)
        severity: Incident severity (low, medium, high, critical)
        incident_id: Optional incident ID (generated if not provided)
        slack_channel: Optional Slack channel override

    Returns:
        Final orchestrator state with all results
    """
    import logging
    logger = logging.getLogger(__name__)

    # Build initial state
    initial_state = {
        "alert": alert,
        "severity": severity,
    }

    if incident_id:
        initial_state["incident_id"] = incident_id

    if slack_channel:
        initial_state["slack_channel"] = slack_channel

    # Use incident_id as thread_id (or generate one)
    thread_id = incident_id or f"incident-{__import__('uuid').uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    logger.info(f"[Orchestrator] Processing incident with thread_id: {thread_id}")

    # Invoke the orchestrator graph
    result = await orchestrator_graph.ainvoke(initial_state, config)

    return result


async def get_incident_state(incident_id: str) -> dict:
    """
    Get the current state of an incident.

    Useful for checking status of in-progress incidents.

    Args:
        incident_id: The incident ID (used as thread_id)

    Returns:
        Current state dict or None if not found
    """
    config = {"configurable": {"thread_id": incident_id}}

    try:
        state = await orchestrator_graph.aget_state(config)
        if state and state.values:
            return state.values
        return None
    except Exception:
        return None


async def resume_incident(incident_id: str, decision: dict) -> dict:
    """
    Resume a paused incident (e.g., after approval decision).

    Args:
        incident_id: The incident ID
        decision: The decision data (e.g., {"approved": True, "approved_by": "user"})

    Returns:
        Updated state after resumption
    """
    from langgraph.types import Command

    config = {"configurable": {"thread_id": incident_id}}
    resume_command = Command(resume=decision)

    result = await orchestrator_graph.ainvoke(resume_command, config)
    return result
