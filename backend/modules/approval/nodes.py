import logging
from typing import Dict, Any, Optional
from datetime import datetime

from langgraph.types import interrupt

from backend.modules.approval.state import ApprovalState
from backend.modules.approval.clients.slack import SlackClient
from backend.config.settings import settings

logger = logging.getLogger(__name__)


def format_approval_node(state: ApprovalState) -> Dict[str, Any]:
    """
    Node 1: Prepare approval request data.

    WHY THIS NODE?
    - Validates that all required data is present
    - Formats data consistently before sending to Slack
    - Can add additional context or transform data

    Reads: incident_id, severity, root_cause, confidence, evidence,
           recommended_actions, similar_incidents
    Writes: (validates and passes through)

    Args:
        state: Current approval state with incident data

    Returns:
        Empty dict (validation only) or error info
    """
    logger.info(f"[Approval] Formatting approval request for incident {state.get('incident_id')}")

    # Validate required fields
    required_fields = ["incident_id", "severity", "root_cause", "recommended_actions"]
    missing = [f for f in required_fields if not state.get(f)]

    if missing:
        logger.error(f"[Approval] Missing required fields: {missing}")
    # Log what we're about to send
    logger.info(
        f"[Approval] Incident: {state.get('incident_id')}, "
        f"Severity: {state.get('severity')}, "
        f"Confidence: {state.get('confidence', 0)*100:.0f}%, "
        f"Actions: {len(state.get('recommended_actions', []))}"
    )

    return {}



async def send_to_slack_node(state: ApprovalState) -> Dict[str, Any]:
    """
    Node 2: Send approval request to Slack.

    WHY ASYNC?
    - Slack API calls are I/O bound
    - Using async prevents blocking the event loop
    - Better performance when handling multiple incidents

    HOW SLACK BUTTONS WORK:
    1. We send a message with Block Kit buttons
    2. User clicks a button in Slack
    3. Slack sends a webhook to our API (not this graph!)
    4. Our API receives the decision and calls Command(resume=decision)

    Reads: All incident data from state
    Writes: slack_channel, approval_message_ts

    Args:
        state: Current approval state

    Returns:
        Dict with Slack message info (channel, ts)
    """
    logger.info(f"[Approval] Sending to Slack for incident {state.get('incident_id')}")

    # Get Slack token from settings/env
    slack_token = getattr(settings, "SLACK_BOT_TOKEN", None)
    if not slack_token:
        # In production, this would be a real token
        # For now, we'll simulate the Slack send
        logger.warning("[Approval] No SLACK_BOT_TOKEN configured - simulating send")
        return {
            "slack_channel": state.get("slack_channel", "#incidents"),
            "approval_message_ts": f"simulated_{datetime.utcnow().timestamp()}",
        }

    # Create Slack client
    slack = SlackClient(
        token=slack_token,
        default_channel=state.get("slack_channel", "#incidents"),
    )

    # Send the approval request
    result = await slack.send_approval_request(
        incident_id=state.get("incident_id", "unknown"),
        severity=state.get("severity", "unknown"),
        root_cause=state.get("root_cause", "Unknown root cause"),
        confidence=state.get("confidence", 0.0),
        evidence=state.get("evidence", []),
        recommended_actions=state.get("recommended_actions", []),
        similar_incidents=state.get("similar_incidents"),
        channel=state.get("slack_channel"),
        thread_ts=state.get("slack_thread_ts"),
    )

    if result.get("ok"):
        logger.info(f"[Approval] Slack message sent: ts={result.get('ts')}")
        return {
            "slack_channel": result.get("channel"),
            "approval_message_ts": result.get("ts"),
        }
    else:
        logger.error(f"[Approval] Slack send failed: {result.get('error')}")
        # Still return channel info even if failed
        return {
            "slack_channel": state.get("slack_channel", "#incidents"),
        }


def wait_for_decision_node(state: ApprovalState) -> Dict[str, Any]:
    """
    Node 3: Pause execution and wait for human decision.

    THIS IS THE KEY NODE - IT USES interrupt()!

    HOW interrupt() WORKS:
    =====================
    1. When this node runs, interrupt() is called
    2. The graph STOPS here and returns to the caller
    3. The payload we pass to interrupt() is accessible via __interrupt__
    4. The state is CHECKPOINTED (saved to database)
    5. Later, someone calls: graph.invoke(Command(resume=decision), config)
    6. The graph RESUMES from this point
    7. The 'decision' value becomes the RETURN VALUE of interrupt()

    WHY NOT JUST POLL SLACK?
    - Polling is inefficient and wastes resources
    - interrupt() is designed exactly for this use case
    - State is persisted, surviving server restarts
    - Clean separation: graph logic vs webhook handling

    THE INTERRUPT PAYLOAD:
    We pass useful info so the caller (API/webhook handler) knows:
    - What incident this is for
    - What the expected response format is

    Reads: incident_id, recommended_actions, slack_channel, approval_message_ts
    Writes: approved, approved_by, approved_by_name, approval_time,
            rejection_reason, modified_actions, approval_notes

    Args:
        state: Current approval state

    Returns:
        Dict with decision outcome
    """
    incident_id = state.get("incident_id", "unknown")

    logger.info(f"[Approval] Waiting for human decision on incident {incident_id}")

    #
    decision = interrupt({
        # Info about what we're waiting for
        "type": "approval_required",
        "incident_id": incident_id,

        # Context for the handler/UI
        "slack_channel": state.get("slack_channel"),
        "slack_message_ts": state.get("approval_message_ts"),

        # What actions are pending approval
        "pending_actions": state.get("recommended_actions", []),

        # Expected response format
        "expected_response": {
            "approved": "bool - True to approve, False to reject",
            "approved_by": "str - User ID who made the decision",
            "approved_by_name": "str (optional) - Human-readable name",
            "rejection_reason": "str (optional) - Why rejected",
            "modified_actions": "list (optional) - Modified action list",
            "approval_notes": "str (optional) - Any notes from approver",
        },

        # Instructions for the resume call
        "resume_with": "Command(resume={'approved': True/False, 'approved_by': '...', ...})",
    })

    logger.info(f"[Approval] Decision received for {incident_id}: {decision}")

    # Extract decision details
    approved = decision.get("approved", False)
    approved_by = decision.get("approved_by", "unknown")
    approved_by_name = decision.get("approved_by_name")
    rejection_reason = decision.get("rejection_reason")
    modified_actions = decision.get("modified_actions")
    approval_notes = decision.get("approval_notes")

    # Return the decision data to update state
    return {
        "approved": approved,
        "approved_by": approved_by,
        "approved_by_name": approved_by_name,
        "approval_time": datetime.utcnow().isoformat(),
        "rejection_reason": rejection_reason,
        "modified_actions": modified_actions,
        "approval_notes": approval_notes,
    }


async def process_decision_node(state: ApprovalState) -> Dict[str, Any]:
    """
    Node 4: Process the approval decision.

    WHY THIS NODE?
    - Update the Slack message to show the decision
    - Log the decision for audit trail
    - Prepare final state for orchestrator

    This node runs AFTER the interrupt resumes, so we have:
    - approved: True/False
    - approved_by: Who made the decision
    - Any modifications or rejection reasons

    Reads: approved, approved_by, approved_by_name, rejection_reason,
           slack_channel, approval_message_ts
    Writes: (updates Slack message, logs decision)

    Args:
        state: Approval state with decision

    Returns:
        Empty dict (side effects only)
    """
    incident_id = state.get("incident_id", "unknown")
    approved = state.get("approved", False)
    approved_by = state.get("approved_by", "unknown")
    approved_by_name = state.get("approved_by_name")
    rejection_reason = state.get("rejection_reason")

    # Log the decision
    if approved:
        logger.info(
            f"[Approval] ✅ Incident {incident_id} APPROVED by "
            f"{approved_by_name or approved_by}"
        )
        if state.get("modified_actions"):
            logger.info(
                f"[Approval] Actions were modified: "
                f"{len(state.get('modified_actions', []))} actions"
            )
    else:
        logger.info(
            f"[Approval] ❌ Incident {incident_id} REJECTED by "
            f"{approved_by_name or approved_by}"
        )
        if rejection_reason:
            logger.info(f"[Approval] Rejection reason: {rejection_reason}")

    # Update Slack message to show decision (if configured)
    slack_token = getattr(settings, "SLACK_BOT_TOKEN", None)
    channel = state.get("slack_channel")
    message_ts = state.get("approval_message_ts")

    if slack_token and channel and message_ts:
        slack = SlackClient(token=slack_token)
        await slack.update_approval_message(
            channel=channel,
            message_ts=message_ts,
            decision="approved" if approved else "rejected",
            decided_by=approved_by,
            decided_by_name=approved_by_name,
            reason=rejection_reason,
        )
    return {}
