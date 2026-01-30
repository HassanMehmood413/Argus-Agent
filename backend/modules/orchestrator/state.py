from typing import TypedDict, Literal, Optional, List, Dict, Any




class OrchestratorState(TypedDict, total=False):
    """
    Master state for the entire incident lifecycle.
    
    This state:
    - Gets saved to PostgreSQL via checkpointer
    - Contains the union of all subgraph outputs
    - Controls the routing logic
    """
    
    incident_id: str
    # Unique identifier for this incident
    # Example: "inc-2024-01-15-abc123"
    # Set once at the beginning, never changes
    
    status: Literal[
        "new",               # Just received, nothing done yet
        "monitoring",        # Monitor subgraph is running
        "analyzing",         # Analyzer subgraph is running
        "pending_approval",  # Waiting for human to approve
        "approved",          # Human approved, ready to execute
        "rejected",          # Human rejected
        "executing",         # Executor subgraph is running
        "verifying",         # Re-checking if fix worked
        "resolved",          # Successfully fixed!
        "failed",            # Something went wrong
        "escalated"          # Sent to humans, agent gave up
    ]
    # Current status - determines which subgraph runs next
    
    created_at: str
    # ISO timestamp when incident was created
    # Example: "2024-01-15T10:30:00Z"
    
    updated_at: str
    # ISO timestamp of last update
    
    iteration_count: int
    # How many times we've gone through the loop
    # Safety check to prevent infinite loops
    # If iteration_count > 10, something is wrong
    
    error: Optional[str]
    # If something went wrong, the error message
    # None if no error
    
    
    # ══════════════════════════════════════════════════════════════
    # INPUT FIELDS
    # ══════════════════════════════════════════════════════════════
    # The alert that triggered this incident
    
    alert: Alert
    # The original alert from Prometheus/AlertManager
    # Set once at the beginning, never changes
    # See Alert type definition below
    
    severity: Literal["low", "medium", "high", "critical"]
    # Extracted from alert for easy access
    # Used for routing decisions (high/critical need approval)
    
    
    # ══════════════════════════════════════════════════════════════
    # MONITOR OUTPUT FIELDS
    # ══════════════════════════════════════════════════════════════
    # Filled by the Monitor subgraph
    
    metrics: Dict[str, Any]
    # Metrics from Prometheus
    # Example: {"cpu": 85.5, "memory": 72.3, "error_rate": 5.2}
    
    logs: List[Dict[str, Any]]
    # Recent logs from Loki/Elasticsearch
    # Example: [{"ts": "...", "level": "ERROR", "msg": "..."}]
    
    pod_status: Dict[str, Any]
    # Kubernetes pod information
    # Example: {"total": 5, "running": 3, "failed": 2, "pods": [...]}
    
    recent_deployments: List[Dict[str, Any]]
    # Deployments in the last 24 hours
    # Example: [{"name": "api-v2.3.1", "time": "...", "by": "ci-bot"}]
    
    events: List[Dict[str, Any]]
    # Kubernetes events
    # Example: [{"type": "Warning", "reason": "OOMKilled", "msg": "..."}]
    
    
    # ══════════════════════════════════════════════════════════════
    # ANALYZER OUTPUT FIELDS
    # ══════════════════════════════════════════════════════════════
    # Filled by the Analyzer subgraph
    
    root_cause: str
    # The identified root cause
    # Example: "Memory leak in api-gateway v2.3.1 causing OOM kills"
    
    confidence: float
    # How confident the analyzer is (0.0 to 1.0)
    # Example: 0.85 means 85% confident
    
    analysis_reasoning: str
    # The full reasoning/explanation from the LLM
    # Useful for debugging and auditing
    
    similar_incidents: List[Dict[str, Any]]
    # Past incidents that look similar
    # From vector search over incident history
    
    recommended_actions: List[Dict[str, Any]]
    # What the agent wants to do
    # Example: [{"type": "rollback", "target": "api-gateway", ...}]
    
    
    # ══════════════════════════════════════════════════════════════
    # APPROVAL FIELDS
    # ══════════════════════════════════════════════════════════════
    # Filled by the Approval subgraph
    
    needs_approval: bool
    # Whether this incident needs human approval
    # True for high/critical severity
    
    approval_requested_at: Optional[str]
    # When we asked for approval
    
    approved: Optional[bool]
    # None = not yet decided
    # True = approved
    # False = rejected
    
    approved_by: Optional[str]
    # Who approved/rejected
    # Example: "john.doe" or "U1234567890" (Slack user ID)
    
    approval_time: Optional[str]
    # When they approved/rejected
    
    rejection_reason: Optional[str]
    # If rejected, why
    
    modified_actions: Optional[List[Dict[str, Any]]]
    # If human modified the action plan
    
    
    # ══════════════════════════════════════════════════════════════
    # EXECUTION FIELDS
    # ══════════════════════════════════════════════════════════════
    # Filled by the Executor subgraph
    
    execution_started_at: Optional[str]
    # When execution began
    
    execution_results: List[Dict[str, Any]]
    # Results of each action
    # Example: [{"action_id": "1", "success": True, "output": "..."}]
    
    all_succeeded: bool
    # Quick flag: did everything work?
    
    execution_completed_at: Optional[str]
    # When execution finished
    
    
    # ══════════════════════════════════════════════════════════════
    # COMMUNICATION FIELDS
    # ══════════════════════════════════════════════════════════════
    # For Slack integration
    
    slack_channel: str
    # Which channel to post to
    # Example: "#incidents" or "C1234567890"
    
    slack_thread_ts: Optional[str]
    # The thread timestamp (for threading messages)
    # Example: "1705312200.123456"
    
    messages_sent: List[Dict[str, Any]]
    # Record of all Slack messages sent
    
    
    # ══════════════════════════════════════════════════════════════
    # SUMMARY FIELDS
    # ══════════════════════════════════════════════════════════════
    # Final summary
    
    summary: str
    # Human-readable summary of what happened
    
    resolution_time_seconds: float
    # How long it took to resolve
    
    postmortem_created: bool
    # Whether a postmortem ticket was created