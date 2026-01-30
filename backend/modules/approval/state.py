from typing import TypedDict, Dict, List, Any, Optional




"""
APPROVAL SUBGRAPH STATE

Handles human-in-the-loop approval via Slack.
"""

class ApprovalState(TypedDict, total=False):
    """
    State for the Approval subgraph.
    
    INPUT:
    - Incident info to show human
    - Actions to approve
    
    OUTPUT:
    - Approval decision
    """
    
    # ─── INPUT (For displaying to human) ───
    
    incident_id: str
    # To show in Slack message
    
    severity: str
    # To show urgency
    
    root_cause: str
    # What we found
    
    confidence: float
    # How sure we are
    
    evidence: List[str]
    # Supporting evidence
    
    recommended_actions: List[Dict[str, Any]]
    # What we want to do
    
    similar_incidents: List[Dict[str, Any]]
    # Past similar incidents (for context)
    
    
    # ─── SLACK INTEGRATION ───
    
    slack_channel: str
    # Where to post
    
    slack_thread_ts: Optional[str]
    # Existing thread (if any)
    
    approval_message_ts: Optional[str]
    # The message with approve/reject buttons
    
    
    # ─── OUTPUT ───
    
    approved: Optional[bool]
    # None = waiting
    # True = approved
    # False = rejected
    
    approved_by: Optional[str]
    # User who approved/rejected
    # Example: "john.doe" or "U1234567890"
    
    approved_by_name: Optional[str]
    # Human-readable name
    # Example: "John Doe"
    
    approval_time: Optional[str]
    # When decision was made
    
    rejection_reason: Optional[str]
    # If rejected, why
    
    modified_actions: Optional[List[Dict[str, Any]]]
    # If human modified the plan
    # They might remove some actions or change parameters
    
    approval_notes: Optional[str]
    # Any notes from the approver