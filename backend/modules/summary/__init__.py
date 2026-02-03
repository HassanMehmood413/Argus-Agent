"""
Summary Agent Module

Generates comprehensive incident summaries and posts them to Slack.

This module:
1. Creates a formatted summary of the incident lifecycle
2. Calculates resolution time
3. Posts the summary to the incident's Slack thread
4. Creates postmortem tickets for high-severity incidents

Usage:
    from backend.modules.summary import summary_subgraph, SummaryState

    # Invoke the summary agent
    result = summary_subgraph.invoke({
        "incident_id": "INC-2024-01-15-abc123",
        "severity": "high",
        "root_cause": "Memory leak in api-gateway",
        "confidence": 0.85,
        "evidence": ["High memory usage", "OOMKilled pods"],
        "recommended_actions": [...],
        "approved_by": "john.doe",
        "execution_results": [...],
        "all_succeeded": True,
        "created_at": "2024-01-15T10:00:00Z",
        "slack_channel": "#incidents",
        "slack_thread_ts": "1234567890.123456",
    })

    print(result["summary"])
    print(f"Resolution time: {result['resolution_time_seconds']} seconds")
"""

from backend.modules.summary.state import SummaryState
from backend.modules.summary.graph import summary_subgraph, build_summary_subgraph
from backend.modules.summary.nodes import (
    generate_summary_node,
    post_to_slack_node,
    create_postmortem_node,
)

__all__ = [
    # State
    "SummaryState",
    # Graph
    "summary_subgraph",
    "build_summary_subgraph",
    # Nodes
    "generate_summary_node",
    "post_to_slack_node",
    "create_postmortem_node",
]
