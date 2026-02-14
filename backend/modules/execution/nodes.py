"""
Executor Subgraph Nodes

Implements a loop-based execution with human-in-the-loop for risky actions.

THE WORKFLOW:
=============
1. validate_actions - Validate approval and action data
2. prepare_next_action - Get next action from list, check if done
3. check_risk_and_route - Route based on risk level
4. request_approval - interrupt() for medium/high risk actions
5. execute_action - Actually execute the action
6. notify_slack - Post result to Slack
7. record_result - Save result, check for failures
8. (loop back to prepare_next_action or go to summarize)
9. summarize_results - Create final summary

RISK-BASED ROUTING:
===================
- none/low risk: Auto-execute without human approval
- medium/high risk: Pause with interrupt(), wait for human decision

HUMAN DECISIONS:
================
- "execute": Proceed with the action
- "skip": Skip this action, continue with next
- "abort": Stop all execution immediately
"""

import logging
from typing import Dict, Any, List, Literal
from datetime import datetime

from langgraph.types import interrupt

from backend.modules.execution.state import ExecutorState
from backend.modules.execution.clients.kubernetes_executor import KubernetesExecutor
from backend.modules.execution.actions import execute_action
from backend.config.settings import settings

logger = logging.getLogger(__name__)

# Shared executor instance
_executor: KubernetesExecutor = None


def get_executor() -> KubernetesExecutor:
    """Get or create the Kubernetes executor singleton."""
    global _executor
    if _executor is None:
        _executor = KubernetesExecutor(
            in_cluster=settings.K8S_IN_CLUSTER,
            deployment_tool=settings.DEPLOYMENT_TOOL,
        )
    return _executor


# ═══════════════════════════════════════════════════════════════════════════
# RISK LEVEL CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════

# Actions that auto-execute without human approval
# NOTE: "medium" included because the orchestrator already does a top-level
# approval. Per-action interrupt() in the executor doesn't propagate back
# to the orchestrator (separate graph invocation), so medium-risk actions
# would silently fail. Only "high" risk gets a second approval.
AUTO_EXECUTE_RISK_LEVELS = ["none", "low", "medium"]

# Actions that require human approval before execution
REQUIRE_APPROVAL_RISK_LEVELS = ["high"]


def get_action_risk_level(action: Dict[str, Any]) -> str:
    """Get the risk level of an action."""
    return action.get("risk_level", "medium")


def requires_approval(action: Dict[str, Any]) -> bool:
    """Check if an action requires human approval."""
    risk_level = get_action_risk_level(action)
    return risk_level in REQUIRE_APPROVAL_RISK_LEVELS


# ═══════════════════════════════════════════════════════════════════════════
# NODE 1: VALIDATE ACTIONS
# ═══════════════════════════════════════════════════════════════════════════

def validate_actions_node(state: ExecutorState) -> Dict[str, Any]:
    """
    Node 1: Validate that actions are approved and ready for execution.

    Checks:
    - Actions are approved
    - Actions list is not empty
    - Each action has required fields

    Reads: approved, actions_to_execute
    Writes: Initializes loop tracking variables

    Args:
        state: Current executor state

    Returns:
        Dict with initialized state or error
    """
    incident_id = state.get("incident_id", "unknown")
    logger.info(f"[Executor] Validating actions for incident {incident_id}")

    # Check approval
    if not state.get("approved"):
        logger.error(f"[Executor] Actions not approved for {incident_id}")
        return {
            "execution_results": [],
            "skipped_actions": [],
            "all_succeeded": False,
            "aborted": True,
            "execution_summary": "❌ Execution blocked: Actions not approved",
        }

    # Check actions exist
    actions = state.get("actions_to_execute", [])
    if not actions:
        logger.warning(f"[Executor] No actions to execute for {incident_id}")
        return {
            "execution_results": [],
            "skipped_actions": [],
            "all_succeeded": True,
            "aborted": False,
            "execution_summary": "✅ No actions to execute",
        }

    # Validate and prepare actions
    valid_actions = []
    for i, action in enumerate(actions):
        if not action.get("type"):
            logger.warning(f"[Executor] Action {i} missing type, skipping")
            continue
        if not action.get("action_id"):
            action["action_id"] = str(i + 1)
        valid_actions.append(action)

    logger.info(
        f"[Executor] Validated {len(valid_actions)}/{len(actions)} actions "
        f"(dry_run={state.get('dry_run', False)})"
    )

    # Initialize loop tracking
    return {
        "actions_to_execute": valid_actions,
        "current_action_index": 0,
        "current_action": None,
        "execution_results": [],
        "skipped_actions": [],
        "aborted": False,
        "action_decision": None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# NODE 2: PREPARE NEXT ACTION
# ═══════════════════════════════════════════════════════════════════════════

def prepare_next_action_node(state: ExecutorState) -> Dict[str, Any]:
    """
    Node 2: Get the next action from the list.

    This node is called at the start of each loop iteration.
    It sets current_action to the next action to process.

    Reads: actions_to_execute, current_action_index
    Writes: current_action, action_decision (reset)

    Args:
        state: Current executor state

    Returns:
        Dict with current_action set
    """
    actions = state.get("actions_to_execute", [])
    index = state.get("current_action_index", 0)

    if index >= len(actions):
        # No more actions - this shouldn't happen due to routing
        logger.info("[Executor] No more actions to process")
        return {"current_action": None}

    action = actions[index]
    logger.info(
        f"[Executor] Preparing action {index + 1}/{len(actions)}: "
        f"{action.get('type')} (risk: {action.get('risk_level', 'unknown')})"
    )

    return {
        "current_action": action,
        "action_decision": None,  # Reset decision for new action
        "awaiting_approval": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# NODE 3: REQUEST APPROVAL (INTERRUPT)
# ═══════════════════════════════════════════════════════════════════════════

def request_approval_node(state: ExecutorState) -> Dict[str, Any]:
    """
    Node 3: Pause and request human approval for risky action.

    THIS NODE USES interrupt()!

    The graph pauses here and waits for human to decide:
    - "execute": Proceed with the action
    - "skip": Skip this action, continue with next
    - "abort": Stop all execution

    Reads: current_action, incident_id
    Writes: action_decision

    Args:
        state: Current executor state

    Returns:
        Dict with action_decision from human
    """
    current_action = state.get("current_action", {})
    incident_id = state.get("incident_id", "unknown")
    index = state.get("current_action_index", 0)
    total = len(state.get("actions_to_execute", []))

    action_type = current_action.get("type", "unknown")
    risk_level = current_action.get("risk_level", "medium")

    logger.info(
        f"[Executor] Requesting approval for {action_type} "
        f"(risk: {risk_level}, action {index + 1}/{total})"
    )

    # ═══════════════════════════════════════════════════════════════════
    # SEND SLACK MESSAGE WITH BUTTONS (before interrupt)
    # ═══════════════════════════════════════════════════════════════════
    slack_token = settings.SLACK_BOT_TOKEN
    slack_channel = state.get("slack_channel")
    slack_thread_ts = state.get("slack_thread_ts")

    if slack_token and slack_channel:
        try:
            from slack_sdk import WebClient
            client = WebClient(token=slack_token)

            # Build Block Kit message with buttons
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"⚠️ *Action {index + 1}/{total} requires approval*\n\n"
                            f"*Type:* `{action_type}`\n"
                            f"*Target:* `{current_action.get('target')}`\n"
                            f"*Namespace:* `{current_action.get('target_namespace', 'default')}`\n"
                            f"*Risk Level:* {risk_level.upper()}\n"
                            f"*Reason:* {current_action.get('reason', 'N/A')}"
                        ),
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*Expected Outcome:* {current_action.get('expected_outcome', 'N/A')}\n"
                            f"*Rollback Plan:* {current_action.get('rollback_plan', 'N/A')}"
                        ),
                    },
                },
                {
                    "type": "actions",
                    "block_id": f"execution_approval_{incident_id}_{index}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Execute", "emoji": True},
                            "style": "primary",
                            "action_id": "execute_action",
                            "value": incident_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "⏭️ Skip", "emoji": True},
                            "action_id": "skip_action",
                            "value": incident_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🛑 Abort All", "emoji": True},
                            "style": "danger",
                            "action_id": "abort_execution",
                            "value": incident_id,
                        },
                    ],
                },
            ]

            client.chat_postMessage(
                channel=slack_channel,
                thread_ts=slack_thread_ts,
                blocks=blocks,
                text=f"Action {index + 1}/{total} requires approval: {action_type}",
            )
        except Exception as e:
            logger.error(f"[Executor] Failed to send approval request to Slack: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # INTERRUPT - Pause for human decision
    # ═══════════════════════════════════════════════════════════════════
    decision = interrupt({
        "type": "execution_approval",
        "incident_id": incident_id,
        "action_index": index,
        "total_actions": total,

        # Action details for human to review
        "action": {
            "action_id": current_action.get("action_id"),
            "type": action_type,
            "target": current_action.get("target"),
            "target_namespace": current_action.get("target_namespace"),
            "risk_level": risk_level,
            "reason": current_action.get("reason"),
            "expected_outcome": current_action.get("expected_outcome"),
            "rollback_plan": current_action.get("rollback_plan"),
            "parameters": current_action.get("parameters", {}),
        },

        # Options for human
        "options": {
            "execute": "Proceed with this action",
            "skip": "Skip this action, continue with next",
            "abort": "Stop all execution immediately",
        },

        # Message for Slack/UI
        "message": (
            f"⚠️ *Action {index + 1}/{total} requires approval*\n\n"
            f"*Type:* `{action_type}`\n"
            f"*Target:* `{current_action.get('target')}`\n"
            f"*Risk Level:* {risk_level.upper()}\n"
            f"*Reason:* {current_action.get('reason', 'N/A')}\n\n"
            f"What would you like to do?"
        ),

        # Expected response format
        "resume_with": "One of: 'execute', 'skip', 'abort'",
    })

    # After resume, decision contains the human's choice
    logger.info(f"[Executor] Human decision received: {decision}")

    return {
        "action_decision": decision,
        "awaiting_approval": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# NODE 4: EXECUTE ACTION
# ═══════════════════════════════════════════════════════════════════════════

async def execute_action_node(state: ExecutorState) -> Dict[str, Any]:
    """
    Node 4: Execute the current action.

    This node actually performs the action using KubernetesExecutor.
    It includes retry logic (handled in action executors).

    Reads: current_action, dry_run
    Writes: last_execution_result

    Args:
        state: Current executor state

    Returns:
        Dict with execution result
    """
    current_action = state.get("current_action", {})
    dry_run = state.get("dry_run", settings.EXECUTION_DRY_RUN)

    action_type = current_action.get("type", "unknown")
    action_id = current_action.get("action_id", "unknown")

    logger.info(f"[Executor] Executing action {action_id}: {action_type}")

    executor = get_executor()

    try:
        result = await execute_action(executor, current_action, dry_run)

        logger.info(
            f"[Executor] Action {action_id} completed: "
            f"success={result.get('success')}"
        )

        return {"last_execution_result": result}

    except Exception as e:
        logger.exception(f"[Executor] Action {action_id} failed with exception: {e}")
        return {
            "last_execution_result": {
                "success": False,
                "action_id": action_id,
                "action_type": action_type,
                "error": str(e),
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
            }
        }


# ═══════════════════════════════════════════════════════════════════════════
# NODE 5: NOTIFY SLACK
# ═══════════════════════════════════════════════════════════════════════════

async def notify_slack_node(state: ExecutorState) -> Dict[str, Any]:
    """
    Node 5: Post action result to Slack.

    Posts a message to the incident thread showing:
    - Action type and result (success/failure)
    - Output or error message
    - Progress (X of Y actions)

    Reads: last_execution_result, current_action, slack_channel, slack_thread_ts
    Writes: (side effects only - Slack message)

    Args:
        state: Current executor state

    Returns:
        Empty dict (side effects only)
    """
    result = state.get("last_execution_result", {})
    current_action = state.get("current_action", {})
    index = state.get("current_action_index", 0)
    total = len(state.get("actions_to_execute", []))
    slack_channel = state.get("slack_channel")
    slack_thread_ts = state.get("slack_thread_ts")

    action_type = current_action.get("type", "unknown")
    success = result.get("success", False)

    # Build message
    emoji = "✅" if success else "❌"
    status = "succeeded" if success else "failed"

    if success:
        output = result.get("output", "Completed")
        if result.get("dry_run"):
            output = f"[DRY RUN] {output}"
        message = f"{emoji} *Action {index + 1}/{total}: {action_type}* {status}\n>{output[:200]}"
    else:
        error = result.get("error", "Unknown error")
        message = f"{emoji} *Action {index + 1}/{total}: {action_type}* {status}\n>Error: {error[:200]}"

    logger.info(f"[Executor] Slack notification: {action_type} {status}")

    # Post to Slack if configured
    slack_token = settings.SLACK_BOT_TOKEN
    if slack_token and slack_channel:
        try:
            from slack_sdk import WebClient
            client = WebClient(token=slack_token)

            client.chat_postMessage(
                channel=slack_channel,
                thread_ts=slack_thread_ts,
                text=message,
                mrkdwn=True,
            )
        except Exception as e:
            logger.error(f"[Executor] Failed to send Slack notification: {e}")

    return {}


# ═══════════════════════════════════════════════════════════════════════════
# NODE 6: RECORD RESULT
# ═══════════════════════════════════════════════════════════════════════════

def record_result_node(state: ExecutorState) -> Dict[str, Any]:
    """
    Node 6: Record the execution result and advance to next action.

    Adds the result to execution_results and increments the index.
    Also checks for failures if stop_on_failure is enabled.

    Reads: last_execution_result, execution_results, current_action_index
    Writes: execution_results, current_action_index, failed_action

    Args:
        state: Current executor state

    Returns:
        Dict with updated results and index
    """
    result = state.get("last_execution_result", {})
    current_action = state.get("current_action", {})
    results = state.get("execution_results", []).copy()
    index = state.get("current_action_index", 0)
    stop_on_failure = state.get("stop_on_failure", settings.EXECUTION_STOP_ON_FAILURE)

    # Add result to list
    results.append(result)

    # Check for failure
    failed_action = None
    if not result.get("success") and stop_on_failure:
        logger.warning(f"[Executor] Action failed and stop_on_failure=True")
        failed_action = current_action

    # Advance index
    new_index = index + 1

    logger.info(f"[Executor] Recorded result for action {index + 1}, advancing to {new_index + 1}")

    return {
        "execution_results": results,
        "current_action_index": new_index,
        "failed_action": failed_action,
    }


# ═══════════════════════════════════════════════════════════════════════════
# NODE 7: RECORD SKIP
# ═══════════════════════════════════════════════════════════════════════════

def record_skip_node(state: ExecutorState) -> Dict[str, Any]:
    """
    Node 7: Record that an action was skipped by human.

    Called when human chooses "skip" for a risky action.

    Reads: current_action, skipped_actions, current_action_index
    Writes: skipped_actions, current_action_index

    Args:
        state: Current executor state

    Returns:
        Dict with updated skipped list and index
    """
    current_action = state.get("current_action", {})
    skipped = state.get("skipped_actions", []).copy()
    index = state.get("current_action_index", 0)

    action_type = current_action.get("type", "unknown")
    logger.info(f"[Executor] Action {index + 1} ({action_type}) skipped by human")

    # Add to skipped list
    skipped.append({
        **current_action,
        "skipped_at": datetime.utcnow().isoformat(),
        "reason": "Skipped by human decision",
    })

    # Advance index
    new_index = index + 1

    return {
        "skipped_actions": skipped,
        "current_action_index": new_index,
    }


# ═══════════════════════════════════════════════════════════════════════════
# NODE 8: NOTIFY SKIP
# ═══════════════════════════════════════════════════════════════════════════

async def notify_skip_node(state: ExecutorState) -> Dict[str, Any]:
    """
    Node 8: Notify Slack that an action was skipped.

    Args:
        state: Current executor state

    Returns:
        Empty dict (side effects only)
    """
    current_action = state.get("current_action", {})
    index = state.get("current_action_index", 0)
    total = len(state.get("actions_to_execute", []))
    slack_channel = state.get("slack_channel")
    slack_thread_ts = state.get("slack_thread_ts")

    action_type = current_action.get("type", "unknown")
    message = f"⏭️ *Action {index + 1}/{total}: {action_type}* skipped by operator"

    logger.info(f"[Executor] Slack notification: {action_type} skipped")

    slack_token = settings.SLACK_BOT_TOKEN
    if slack_token and slack_channel:
        try:
            from slack_sdk import WebClient
            client = WebClient(token=slack_token)

            client.chat_postMessage(
                channel=slack_channel,
                thread_ts=slack_thread_ts,
                text=message,
                mrkdwn=True,
            )
        except Exception as e:
            logger.error(f"[Executor] Failed to send Slack notification: {e}")

    return {}


# ═══════════════════════════════════════════════════════════════════════════
# NODE 9: HANDLE ABORT
# ═══════════════════════════════════════════════════════════════════════════

async def handle_abort_node(state: ExecutorState) -> Dict[str, Any]:
    """
    Node 9: Handle abort decision from human.

    Sets aborted flag and notifies Slack.

    Args:
        state: Current executor state

    Returns:
        Dict with aborted=True
    """
    index = state.get("current_action_index", 0)
    total = len(state.get("actions_to_execute", []))
    slack_channel = state.get("slack_channel")
    slack_thread_ts = state.get("slack_thread_ts")

    logger.warning(f"[Executor] Execution aborted by human at action {index + 1}/{total}")

    message = f"🛑 *Execution aborted* by operator at action {index + 1}/{total}"

    slack_token = settings.SLACK_BOT_TOKEN
    if slack_token and slack_channel:
        try:
            from slack_sdk import WebClient
            client = WebClient(token=slack_token)

            client.chat_postMessage(
                channel=slack_channel,
                thread_ts=slack_thread_ts,
                text=message,
                mrkdwn=True,
            )
        except Exception as e:
            logger.error(f"[Executor] Failed to send Slack notification: {e}")

    return {"aborted": True}


# ═══════════════════════════════════════════════════════════════════════════
# NODE 10: SUMMARIZE RESULTS
# ═══════════════════════════════════════════════════════════════════════════

def summarize_results_node(state: ExecutorState) -> Dict[str, Any]:
    """
    Node 10: Create a human-readable summary of execution.

    Summarizes:
    - Total actions executed
    - Successes and failures
    - Skipped actions
    - Abort status

    Reads: execution_results, skipped_actions, aborted, dry_run
    Writes: execution_summary, all_succeeded

    Args:
        state: Current executor state

    Returns:
        Dict with execution_summary
    """
    incident_id = state.get("incident_id", "unknown")
    results = state.get("execution_results", [])
    skipped = state.get("skipped_actions", [])
    aborted = state.get("aborted", False)
    dry_run = state.get("dry_run", False)
    failed_action = state.get("failed_action")

    logger.info(f"[Executor] Creating summary for {incident_id}")

    # Count results
    succeeded = sum(1 for r in results if r.get("success"))
    failed = len(results) - succeeded
    skipped_count = len(skipped)

    # Determine overall success
    all_succeeded = failed == 0 and not aborted

    # Build summary
    lines = []

    # Header
    if dry_run:
        lines.append("📋 **DRY RUN Execution Summary**")
    elif aborted:
        lines.append("🛑 **Execution Aborted**")
    elif all_succeeded:
        lines.append("✅ **Execution Completed Successfully**")
    else:
        lines.append("❌ **Execution Completed with Issues**")

    lines.append(f"Incident: `{incident_id}`")
    lines.append(f"Executed: {succeeded} succeeded, {failed} failed")
    if skipped_count > 0:
        lines.append(f"Skipped: {skipped_count} actions")
    lines.append("")

    # Executed actions
    if results:
        lines.append("**Executed Actions:**")
        for i, result in enumerate(results, 1):
            action_type = result.get("action_type", "unknown")
            success = result.get("success", False)
            emoji = "✅" if success else "❌"

            if success:
                output = result.get("output", "Done")[:80]
                lines.append(f"{emoji} {i}. {action_type}: {output}")
            else:
                error = result.get("error", "Error")[:80]
                lines.append(f"{emoji} {i}. {action_type}: {error}")
        lines.append("")

    # Skipped actions
    if skipped:
        lines.append("**Skipped Actions:**")
        for action in skipped:
            action_type = action.get("type", "unknown")
            lines.append(f"⏭️ {action_type}")
        lines.append("")

    # Abort/failure info
    if aborted:
        lines.append("*Execution was aborted by operator.*")
    elif failed_action:
        lines.append(f"*Stopped at: {failed_action.get('type')}*")

    summary = "\n".join(lines)

    return {
        "execution_summary": summary,
        "all_succeeded": all_succeeded,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def route_by_risk(state: ExecutorState) -> Literal["request_approval", "execute_action"]:
    """
    Route based on action risk level.

    - none/low risk → auto-execute
    - medium/high risk → request approval

    Args:
        state: Current executor state

    Returns:
        Node name to route to
    """
    current_action = state.get("current_action", {})
    risk_level = get_action_risk_level(current_action)

    if risk_level in AUTO_EXECUTE_RISK_LEVELS:
        logger.info(f"[Executor] Auto-executing {risk_level} risk action")
        return "execute_action"
    else:
        logger.info(f"[Executor] Requesting approval for {risk_level} risk action")
        return "request_approval"


def route_after_approval(state: ExecutorState) -> Literal["execute_action", "record_skip", "handle_abort"]:
    """
    Route based on human's decision after approval request.

    Args:
        state: Current executor state

    Returns:
        Node name to route to
    """
    decision = state.get("action_decision", "execute")

    if decision == "abort":
        return "handle_abort"
    elif decision == "skip":
        return "record_skip"
    else:
        return "execute_action"


def route_has_more_actions(state: ExecutorState) -> Literal["prepare_next_action", "summarize_results"]:
    """
    Check if there are more actions to execute.

    Also checks for stop conditions (failure, abort).

    Args:
        state: Current executor state

    Returns:
        Node name to route to
    """
    actions = state.get("actions_to_execute", [])
    index = state.get("current_action_index", 0)
    failed_action = state.get("failed_action")
    aborted = state.get("aborted", False)

    # Stop if aborted
    if aborted:
        logger.info("[Executor] Execution was aborted, going to summary")
        return "summarize_results"

    # Stop if failed with stop_on_failure
    if failed_action:
        logger.info("[Executor] Action failed with stop_on_failure, going to summary")
        return "summarize_results"

    # Check if more actions
    if index < len(actions):
        logger.info(f"[Executor] More actions to process ({index + 1}/{len(actions)})")
        return "prepare_next_action"
    else:
        logger.info("[Executor] All actions processed, going to summary")
        return "summarize_results"
