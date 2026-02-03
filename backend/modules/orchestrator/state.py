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
    created_at: str
    updated_at: str
    iteration_count: int
    error: Optional[str]
    # ══════════════════════════════════════════════════════════════
    # INPUT FIELDS
    # ══════════════════════════════════════════════════════════════
    alert: Dict[str, Any]
    severity: Literal["low", "medium", "high", "critical"]
    # ══════════════════════════════════════════════════════════════
    # MONITOR OUTPUT FIELDS
    # ══════════════════════════════════════════════════════════════
    metrics: Dict[str, Any]
    logs: List[Dict[str, Any]]
    pod_status: Dict[str, Any]
    recent_deployments: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    # ══════════════════════════════════════════════════════════════
    # ANALYZER OUTPUT FIELDS
    # ══════════════════════════════════════════════════════════════
    root_cause: str
    confidence: float
    analysis_reasoning: str
    similar_incidents: List[Dict[str, Any]]
    recommended_actions: List[Dict[str, Any]]
    # ══════════════════════════════════════════════════════════════
    # APPROVAL FIELDS
    # ══════════════════════════════════════════════════════════════
    needs_approval: bool
    approval_requested_at: Optional[str]
    approved: Optional[bool]
    approved_by: Optional[str]
    approval_time: Optional[str]
    rejection_reason: Optional[str]
    modified_actions: Optional[List[Dict[str, Any]]]
    # ══════════════════════════════════════════════════════════════
    # EXECUTION FIELDS
    # ══════════════════════════════════════════════════════════════
    execution_started_at: Optional[str]
    execution_results: List[Dict[str, Any]]
    all_succeeded: bool
    execution_completed_at: Optional[str]
    # ══════════════════════════════════════════════════════════════
    # COMMUNICATION FIELDS
    # ══════════════════════════════════════════════════════════════
    slack_channel: str
    slack_thread_ts: Optional[str]
    messages_sent: List[Dict[str, Any]]
    # ══════════════════════════════════════════════════════════════
    # SUMMARY FIELDS
    # ══════════════════════════════════════════════════════════════
    summary: str
    resolution_time_seconds: float
    postmortem_created: bool
