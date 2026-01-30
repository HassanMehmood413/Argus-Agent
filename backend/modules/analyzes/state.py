"""
Analyzer State Schema

Defines the TypedDict state schema for the Analyzer subgraph.
"""

from typing import TypedDict, List, Dict, Any, Literal


class AnalyzerState(TypedDict, total=False):
    """
    State for Analyzer subgraph.
    """

    # ─── INPUT (from Monitor/Orchestrator) ───

    # Alert info
    alert: Dict[str, Any]
    severity: Literal["low", "medium", "high", "critical"]

    # Monitor data
    metrics: Dict[str, Any]
    logs: List[Dict[str, Any]]
    pod_status: Dict[str, Any]
    events: List[Dict[str, Any]]
    recent_deployments: List[Dict[str, Any]]
    health_summary: str


    # ─── INTERNAL (analysis process) ───

    # Detected patterns
    patterns: List[Dict[str, Any]]
    # Example: [
    #     {"type": "high_cpu", "value": 95.5, "threshold": 80},
    #     {"type": "memory_leak", "evidence": "growing over 2h"},
    #     {"type": "recent_deployment", "deployment": "v2.3.1"}
    # ]

    # Similar past incidents (from RAG)
    similar_incidents: List[Dict[str, Any]]
    # Example: [
    #     {"id": "INC-123", "similarity": 0.92, "root_cause": "...", "resolution": "..."}
    # ]


    # ─── OUTPUT (to Orchestrator) ───

    root_cause: str
    # Example: "Memory leak in api-gateway v2.3.1 causing OOM kills"

    confidence: float
    # 0.0 to 1.0

    evidence: List[str]
    # Key evidence points supporting the diagnosis

    analysis_reasoning: str
    # Full LLM reasoning (for debugging/audit)

    recommended_actions: List[Dict[str, Any]]
    # Actions to fix the issue
    # Example: [
    #     {
    #         "action_id": "1",
    #         "type": "rollback",
    #         "target": "deployment/api-gateway",
    #         "parameters": {"to_revision": 41},
    #         "reason": "Roll back to version without memory leak",
    #         "risk_level": "medium",
    #         "expected_outcome": "Memory usage should stabilize",
    #         "rollback_plan": "Re-deploy if needed",
    #         "order": 1
    #     }
    # ]

    requires_approval: bool
    # Whether human approval is needed

    actions_reasoning: str
    # Explanation of why these actions were chosen

    approval_reason: str
    # Why approval is needed (if requires_approval is true)
