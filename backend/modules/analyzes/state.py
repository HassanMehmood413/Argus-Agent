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
    alert: Dict[str, Any]
    severity: Literal["low", "medium", "high", "critical"]
    metrics: Dict[str, Any]
    logs: List[Dict[str, Any]]
    pod_status: Dict[str, Any]
    events: List[Dict[str, Any]]
    recent_deployments: List[Dict[str, Any]]
    health_summary: str
    # ─── INTERNAL (analysis process) ───
    patterns: List[Dict[str, Any]]
    similar_incidents: List[Dict[str, Any]]
    # ─── OUTPUT (to Orchestrator) ───
    root_cause: str
    confidence: float
    evidence: List[str]
    analysis_reasoning: str
    recommended_actions: List[Dict[str, Any]]
    requires_approval: bool
    actions_reasoning: str
    approval_reason: str
