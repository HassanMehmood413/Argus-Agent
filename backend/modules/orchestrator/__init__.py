"""
Orchestrator Module

Master controller for the entire incident lifecycle.

The Orchestrator coordinates all subgraphs:
- Monitor: Collect metrics, logs, pod status
- Analyzer: Identify root cause and recommend actions
- Approval: Human-in-the-loop via Slack
- Executor: Execute approved actions
- Summary: Generate incident summary and postmortem

Usage:
    from backend.modules.orchestrator import orchestrator_graph, process_incident

    # Option 1: Use the high-level API
    result = await process_incident(
        alert={"alertname": "HighMemoryUsage", "service": "api-gateway"},
        severity="critical"
    )

    # Option 2: Invoke the graph directly
    result = await orchestrator_graph.ainvoke(
        {"alert": {...}, "severity": "critical"},
        config={"configurable": {"thread_id": "INC-001"}}
    )
"""

from backend.modules.orchestrator.state import OrchestratorState
from backend.modules.orchestrator.checkpointer import (
    get_checkpointer,
    get_production_checkpointer,
    get_async_checkpointer,
)
from backend.modules.orchestrator.graph import (
    orchestrator_graph,
    build_orchestrator_graph,
    process_incident,
    get_incident_state,
    resume_incident,
)
from backend.modules.orchestrator.nodes import (
    receive_alert_node,
    run_monitor_node,
    run_analyzer_node,
    run_approval_node,
    skip_approval_node,
    handle_rejection_node,
    run_executor_node,
    run_summary_node,
    route_after_analyzer,
    route_after_approval,
    route_after_execution,
)

__all__ = [
    # State
    "OrchestratorState",
    # Checkpointer
    "get_checkpointer",
    "get_production_checkpointer",
    "get_async_checkpointer",
    # Graph
    "orchestrator_graph",
    "build_orchestrator_graph",
    # API helpers
    "process_incident",
    "get_incident_state",
    "resume_incident",
    # Nodes
    "receive_alert_node",
    "run_monitor_node",
    "run_analyzer_node",
    "run_approval_node",
    "skip_approval_node",
    "handle_rejection_node",
    "run_executor_node",
    "run_summary_node",
    # Routing
    "route_after_analyzer",
    "route_after_approval",
    "route_after_execution",
]
