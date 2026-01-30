from langgraph.graph import StateGraph, START, END
from backend.modules.monitors.state import MonitorState
from backend.modules.monitors.nodes import (
    fetch_metrics_node,
    fetch_pod_status_node,
    fetch_events_node,
    fetch_logs_node,
    fetch_deployments_node,
    summarize_node
)


def build_monitor_subgraph():
    """
    Build and compile the Monitor subgraph.
    
    Flow:
    START → fetch_metrics → fetch_pod_status → fetch_events 
          → fetch_logs → fetch_deployments → summarize → END
    """
    
    # Create the graph
    graph = StateGraph(MonitorState)
    
    graph.add_node("fetch_metrics", fetch_metrics_node)
    graph.add_node("fetch_pod_status", fetch_pod_status_node)
    graph.add_node("fetch_events", fetch_events_node)
    graph.add_node("fetch_logs", fetch_logs_node)
    graph.add_node("fetch_deployments", fetch_deployments_node)
    graph.add_node("summarize", summarize_node)
    
    graph.add_edge(START, "fetch_metrics")
    graph.add_edge("fetch_metrics", "fetch_pod_status")
    graph.add_edge("fetch_pod_status", "fetch_events")
    graph.add_edge("fetch_events", "fetch_logs")
    graph.add_edge("fetch_logs", "fetch_deployments")
    graph.add_edge("fetch_deployments", "summarize")
    graph.add_edge("summarize", END)
    
    return graph.compile()


# Create the subgraph
monitor_subgraph = build_monitor_subgraph()