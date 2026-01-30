from typing import TypedDict, Dict, List, Any



"""
ANALYZER SUBGRAPH STATE

Reads monitoring data, outputs analysis and recommendations.
"""

class AnalyzerState(TypedDict, total=False):
    """
    State for the Analyzer subgraph.
    
    INPUT:
    - All the monitoring data (metrics, logs, etc.)
    - Alert info for context
    
    OUTPUT:
    - Root cause analysis
    - Recommended actions
    """
    
    # ─── INPUT (From Monitor + Alert) ───
    
    alert: Dict[str, Any]
    # The original alert for context
    
    severity: str
    # Alert severity
    
    metrics: Dict[str, Any]
    # From Monitor subgraph
    
    logs: List[Dict[str, Any]]
    # From Monitor subgraph
    
    pod_status: Dict[str, Any]
    # From Monitor subgraph
    
    events: List[Dict[str, Any]]
    # From Monitor subgraph
    
    recent_deployments: List[Dict[str, Any]]
    # From Monitor subgraph
    
    
    # ─── INTERNAL (Analysis process) ───
    
    patterns_detected: List[str]
    # Patterns found in the data
    # Example: ["high_memory_growth", "recent_deployment", "cascading_errors"]
    
    hypotheses: List[Dict[str, Any]]
    # Multiple hypotheses before picking one
    # [
    #     {"cause": "memory leak", "confidence": 0.85, "evidence": [...]},
    #     {"cause": "traffic spike", "confidence": 0.30, "evidence": [...]}
    # ]
    
    
    # ─── OUTPUT (To Orchestrator) ───
    
    root_cause: str
    # The identified root cause
    # Example: "Memory leak in api-gateway v2.3.1 introduced in commit abc123"
    
    confidence: float
    # Confidence level 0.0 to 1.0
    
    analysis_reasoning: str
    # Full explanation from LLM
    # Example: "Based on the metrics, I observed..."
    
    evidence: List[str]
    # Key evidence points
    # [
    #     "Memory usage grew from 40% to 85% over 2 hours",
    #     "Deployment of v2.3.1 occurred 2 hours ago",
    #     "No traffic increase detected",
    #     "Similar incident INC-456 had same pattern"
    # ]
    
    similar_incidents: List[Dict[str, Any]]
    # From vector search
    # [
    #     {
    #         "incident_id": "INC-456",
    #         "title": "API Gateway OOM",
    #         "root_cause": "Memory leak in v2.1.0",
    #         "resolution": "Rolled back to v2.0.9",
    #         "similarity": 0.92
    #     }
    # ]
    
    recommended_actions: List[Dict[str, Any]]
    # What to do
    # [
    #     {
    #         "action_id": "action-1",
    #         "type": "rollback",
    #         "target": "deployment/api-gateway",
    #         "target_namespace": "production",
    #         "parameters": {
    #             "to_revision": 41,  # previous revision
    #             "to_image": "api-gateway:v2.3.0"
    #         },
    #         "reason": "Roll back to previous version without memory leak",
    #         "risk_level": "medium",
    #         "estimated_downtime": "30 seconds",
    #         "order": 1
    #     },
    #     {
    #         "action_id": "action-2",
    #         "type": "scale",
    #         "target": "deployment/api-gateway",
    #         "target_namespace": "production",
    #         "parameters": {
    #             "replicas": 8  # scale up for safety
    #         },
    #         "reason": "Increase capacity while rolling back",
    #         "risk_level": "low",
    #         "order": 0  # do this first
    #     }
    # ]
    
    requires_approval: bool
    # Does this need human approval?
    # Based on severity and action risk