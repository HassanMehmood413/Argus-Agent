from typing import TypedDict, Dict, List, Any, Optional



"""
EXECUTOR SUBGRAPH STATE

Executes the approved actions.
"""

class ExecutorState(TypedDict, total=False):
    """
    State for the Executor subgraph.
    
    INPUT:
    - Actions to execute
    - Approval confirmation
    
    OUTPUT:
    - Execution results
    """
    
    # ─── INPUT ───
    
    incident_id: str
    # For logging
    
    approved: bool
    # Must be True to execute
    # Safety check!
    
    approved_by: str
    # Who approved (for audit log)
    
    actions_to_execute: List[Dict[str, Any]]
    # Either recommended_actions or modified_actions
    # Sorted by "order" field
    
    
    # ─── EXECUTION CONFIG ───
    
    dry_run: bool
    # If True, don't actually execute, just simulate
    # Default: False
    
    stop_on_failure: bool
    # If True, stop executing if any action fails
    # Default: True
    
    timeout_seconds: int
    # Max time for each action
    # Default: 300 (5 minutes)
    
    
    # ─── INTERNAL (During execution) ───
    
    current_action_index: int
    # Which action we're on
    
    
    # ─── OUTPUT ───
    
    execution_results: List[Dict[str, Any]]
    # Result of each action
    # [
    #     {
    #         "action_id": "action-2",  # scale (order: 0)
    #         "type": "scale",
    #         "target": "deployment/api-gateway",
    #         "success": True,
    #         "message": "Scaled to 8 replicas",
    #         "started_at": "2024-01-15T10:35:00Z",
    #         "completed_at": "2024-01-15T10:35:15Z",
    #         "duration_seconds": 15,
    #         "output": "deployment.apps/api-gateway scaled"
    #     },
    #     {
    #         "action_id": "action-1",  # rollback (order: 1)
    #         "type": "rollback",
    #         "target": "deployment/api-gateway",
    #         "success": True,
    #         "message": "Rolled back to revision 41",
    #         "started_at": "2024-01-15T10:35:15Z",
    #         "completed_at": "2024-01-15T10:35:45Z",
    #         "duration_seconds": 30,
    #         "output": "deployment.apps/api-gateway rolled back"
    #     }
    # ]
    
    all_succeeded: bool
    # Did everything work?
    
    failed_action: Optional[Dict[str, Any]]
    # If something failed, which one?
    
    execution_summary: str
    # Quick summary
    # Example: "2/2 actions succeeded in 45 seconds"