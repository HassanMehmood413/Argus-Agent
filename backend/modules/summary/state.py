from typing import TypedDict, Optional, Dict, List, Any




"""
SUMMARY SUBGRAPH STATE

Creates and sends the final summary.
"""

class SummaryState(TypedDict, total=False):
    """
    State for the Summary subgraph.
    
    INPUT:
    - Everything (to create summary)
    
    OUTPUT:
    - Summary text
    - Slack message confirmation
    """
    
    # ─── INPUT (Everything for summary) ───
    
    incident_id: str
    severity: str
    alert: Dict[str, Any]
    root_cause: str
    confidence: float
    evidence: List[str]
    recommended_actions: List[Dict[str, Any]]
    approved_by: Optional[str]
    execution_results: List[Dict[str, Any]]
    all_succeeded: bool
    created_at: str
    
    
    # ─── SLACK ───
    
    slack_channel: str
    slack_thread_ts: Optional[str]
    
    
    # ─── OUTPUT ───
    
    summary: str
    # The full summary text
    # Example:
    # """
    # ══════════════════════════════════════════════
    # ✅ INCIDENT RESOLVED: INC-2024-01-15-abc123
    # ══════════════════════════════════════════════
    # 
    # Severity: HIGH
    # Duration: 12 minutes
    # 
    # Root Cause:
    # Memory leak in api-gateway v2.3.1
    # 
    # Actions Taken:
    # 1. ✅ Scaled api-gateway to 8 replicas
    # 2. ✅ Rolled back to v2.3.0
    # 
    # Approved by: John Doe
    # 
    # ══════════════════════════════════════════════
    # """
    
    resolution_time_seconds: float
    # Time from alert to resolution
    
    summary_message_ts: Optional[str]
    # Slack message ID of summary
    
    postmortem_ticket: Optional[str]
    # If we created a Jira ticket
    # Example: "POST-123"