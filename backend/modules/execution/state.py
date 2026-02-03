"""
Executor State Schema

Defines the TypedDict state schema for the Executor subgraph.

This state supports:
- Sequential action execution with loop tracking
- Human-in-the-loop for risky actions via interrupt()
- Slack notifications after each action
- Skip/Abort capabilities
"""

from typing import TypedDict, Dict, List, Any, Optional, Literal


class ExecutorState(TypedDict, total=False):
    """
    State for the Executor subgraph.

    INPUT:
    - Actions to execute (from Approval module)
    - Approval confirmation

    OUTPUT:
    - Execution results for each action
    - Summary of execution
    """

    # ═══════════════════════════════════════════════════════════════════════
    # INPUT (from Orchestrator/Approval)
    # ═══════════════════════════════════════════════════════════════════════
    incident_id: str
    approved: bool
    approved_by: str
    actions_to_execute: List[Dict[str, Any]]

    # ═══════════════════════════════════════════════════════════════════════
    # EXECUTION CONFIG
    # ═══════════════════════════════════════════════════════════════════════
    dry_run: bool
    # If True, simulate actions only
    stop_on_failure: bool
    # If True, stop execution when an action fails
    timeout_seconds: int
    # Timeout per action in seconds

    # ═══════════════════════════════════════════════════════════════════════
    # SLACK INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════
    slack_channel: str
    # Channel for notifications
    slack_thread_ts: Optional[str]
    # Thread for incident updates

    # ═══════════════════════════════════════════════════════════════════════
    # LOOP TRACKING (for iterating through actions)
    # ═══════════════════════════════════════════════════════════════════════
    current_action_index: int
    # Index of action being processed (0-based)
    current_action: Optional[Dict[str, Any]]
    # The action currently being processed
    last_execution_result: Optional[Dict[str, Any]]
    # Result of the last executed action

    # ═══════════════════════════════════════════════════════════════════════
    # HUMAN-IN-THE-LOOP (for risky actions)
    # ═══════════════════════════════════════════════════════════════════════
    action_decision: Optional[Literal["execute", "skip", "abort"]]
    # Human's decision for current action:
    # - "execute": Proceed with the action
    # - "skip": Skip this action, continue with next
    # - "abort": Stop all execution immediately
    awaiting_approval: bool
    # True when waiting for human decision on risky action

    # ═══════════════════════════════════════════════════════════════════════
    # OUTPUT
    # ═══════════════════════════════════════════════════════════════════════
    execution_results: List[Dict[str, Any]]
    # Results of all executed actions
    skipped_actions: List[Dict[str, Any]]
    # Actions that were skipped by human
    all_succeeded: bool
    # True if all executed actions succeeded
    failed_action: Optional[Dict[str, Any]]
    # The action that failed (if any)
    aborted: bool
    # True if human aborted execution
    execution_summary: str
    # Human-readable summary of execution
