"""
Slack Webhook Handler

This module handles Slack interactive component callbacks (button clicks).

HOW SLACK WEBHOOKS WORK:
========================
1. User clicks Approve/Reject button in Slack
2. Slack sends POST request to this webhook endpoint
3. We verify the request is from Slack
4. We extract the decision and incident_id
5. We call Command(resume=decision) on the approval graph
6. The graph resumes from where it was interrupted

SLACK APP SETUP REQUIRED:
=========================
1. Create a Slack App at https://api.slack.com/apps
2. Enable "Interactivity & Shortcuts"
3. Set Request URL to: https://your-domain.com/api/agent/slack/interactions
4. Add Bot Token Scopes: chat:write, chat:update
5. Install the app to your workspace
6. Copy the Bot Token (xoxb-...) to your .env as SLACK_BOT_TOKEN
7. Copy the Signing Secret to your .env as SLACK_SIGNING_SECRET
"""

import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from langgraph.types import Command

from backend.config.settings import settings
from backend.modules.approval.graph import approval_subgraph
from backend.modules.execution.graph import executor_subgraph

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_slack_signature(
    body: bytes,
    timestamp: str,
    signature: str,
    signing_secret: str,
) -> bool:
    """
    Verify that the request came from Slack.

    WHY VERIFY?
    - Prevents attackers from faking approval/rejection
    - Ensures only Slack can trigger your webhooks
    - Required for production security

    HOW IT WORKS:
    1. Slack sends timestamp and signature in headers
    2. We create our own signature using the signing secret
    3. If they match, request is legitimate

    Args:
        body: Raw request body
        timestamp: X-Slack-Request-Timestamp header
        signature: X-Slack-Signature header
        signing_secret: Your app's signing secret

    Returns:
        True if signature is valid
    """
    # Check timestamp to prevent replay attacks
    # Reject requests older than 5 minutes
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    # Create the signature base string
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"

    # Create HMAC signature
    my_signature = (
        "v0="
        + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
    )

    # Compare signatures (timing-safe comparison)
    return hmac.compare_digest(my_signature, signature)


async def verify_slack_request(request: Request) -> bytes:
    """
    FastAPI dependency to verify Slack requests.

    Raises HTTPException if verification fails.

    Args:
        request: FastAPI request object

    Returns:
        Raw request body (needed for parsing)
    """
    body = await request.body()

    # Get Slack headers
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Get signing secret from settings
    signing_secret = getattr(settings, "SLACK_SIGNING_SECRET", None)

    # Skip verification in development if no secret configured
    if not signing_secret:
        logger.warning(
            "[Webhook] SLACK_SIGNING_SECRET not configured - "
            "skipping verification (NOT SAFE FOR PRODUCTION)"
        )
        return body

    # Verify the signature
    if not verify_slack_signature(body, timestamp, signature, signing_secret):
        logger.error("[Webhook] Invalid Slack signature")
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    return body


@router.post("/slack/interactions")
async def handle_slack_interaction(
    body: bytes = Depends(verify_slack_request),
):
    """
    Handle Slack interactive component callbacks.

    This is called when a user clicks Approve/Reject/Modify buttons.

    THE FLOW:
    1. User clicks button in Slack
    2. Slack sends POST here with action details
    3. We extract incident_id and decision
    4. We call Command(resume=decision) on the graph
    5. Graph resumes and completes
    6. We return 200 OK to Slack

    WHY RETURN 200 IMMEDIATELY?
    - Slack expects response within 3 seconds
    - Graph execution might take longer
    - We acknowledge first, then process async

    Request Body (form-encoded):
        payload: JSON string with interaction details

    Returns:
        200 OK (Slack requires this)
    """
    # Parse the payload
    # Slack sends payload as form-encoded, not JSON
    try:
        # Decode body and parse form data
        body_str = body.decode("utf-8")

        # Handle URL-encoded payload
        if body_str.startswith("payload="):
            import urllib.parse
            payload_str = urllib.parse.unquote(body_str.replace("payload=", ""))
            payload = json.loads(payload_str)
        else:
            payload = json.loads(body_str)

    except Exception as e:
        logger.error(f"[Webhook] Failed to parse payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    logger.info(f"[Webhook] Received interaction: {payload.get('type')}")

    # Handle different interaction types
    interaction_type = payload.get("type")

    if interaction_type == "block_actions":
        return await handle_button_click(payload)
    elif interaction_type == "view_submission":
        return await handle_modal_submission(payload)
    else:
        logger.warning(f"[Webhook] Unknown interaction type: {interaction_type}")
        return {"ok": True}


async def handle_button_click(payload: dict) -> dict:
    """
    Handle button click interactions.

    This handles both:
    1. Approval module buttons (approve/reject incident)
    2. Execution module buttons (execute/skip/abort action)

    Args:
        payload: Slack interaction payload

    Returns:
        Response dict
    """
    # Extract action details
    actions = payload.get("actions", [])
    if not actions:
        logger.warning("[Webhook] No actions in payload")
        return {"ok": True}

    action = actions[0]
    action_id = action.get("action_id")
    incident_id = action.get("value")

    # Extract user info
    user = payload.get("user", {})
    user_id = user.get("id", "unknown")
    user_name = user.get("name") or user.get("username", "Unknown")

    logger.info(
        f"[Webhook] Button click: action={action_id}, "
        f"incident={incident_id}, user={user_name}"
    )

    # ═══════════════════════════════════════════════════════════════════════
    # APPROVAL MODULE BUTTONS
    # ═══════════════════════════════════════════════════════════════════════
    if action_id == "approve_incident":
        decision = {
            "approved": True,
            "approved_by": user_id,
            "approved_by_name": user_name,
        }
        try:
            await resume_approval_graph(incident_id, decision)
        except Exception as e:
            logger.error(f"[Webhook] Failed to resume approval graph: {e}")
        return {"ok": True}

    elif action_id == "reject_incident":
        decision = {
            "approved": False,
            "approved_by": user_id,
            "approved_by_name": user_name,
            "rejection_reason": "Rejected via Slack button",
        }
        try:
            await resume_approval_graph(incident_id, decision)
        except Exception as e:
            logger.error(f"[Webhook] Failed to resume approval graph: {e}")
        return {"ok": True}

    elif action_id == "modify_incident":
        decision = {
            "approved": True,
            "approved_by": user_id,
            "approved_by_name": user_name,
            "approval_notes": "Actions may need modification",
        }
        try:
            await resume_approval_graph(incident_id, decision)
        except Exception as e:
            logger.error(f"[Webhook] Failed to resume approval graph: {e}")
        return {"ok": True}

    # ═══════════════════════════════════════════════════════════════════════
    # EXECUTION MODULE BUTTONS (Human-in-the-loop for risky actions)
    # ═══════════════════════════════════════════════════════════════════════
    elif action_id == "execute_action":
        # Human approved executing the risky action
        try:
            await resume_execution_graph(incident_id, "execute")
        except Exception as e:
            logger.error(f"[Webhook] Failed to resume execution graph: {e}")
        return {"ok": True}

    elif action_id == "skip_action":
        # Human chose to skip this action
        try:
            await resume_execution_graph(incident_id, "skip")
        except Exception as e:
            logger.error(f"[Webhook] Failed to resume execution graph: {e}")
        return {"ok": True}

    elif action_id == "abort_execution":
        # Human chose to abort all execution
        try:
            await resume_execution_graph(incident_id, "abort")
        except Exception as e:
            logger.error(f"[Webhook] Failed to resume execution graph: {e}")
        return {"ok": True}

    else:
        logger.warning(f"[Webhook] Unknown action_id: {action_id}")
        return {"ok": True}


async def handle_modal_submission(payload: dict) -> dict:
    """
    Handle modal submission interactions.

    This would be called when user submits a rejection reason modal.

    Args:
        payload: Slack interaction payload

    Returns:
        Response dict
    """
    # TODO: Implement modal handling for rejection reason
    # and action modification
    logger.info("[Webhook] Modal submission received")
    return {"ok": True}


async def resume_approval_graph(incident_id: str, decision: dict) -> None:
    """
    Resume the approval graph with the human's decision.

    THIS IS THE KEY FUNCTION!

    It calls graph.invoke(Command(resume=decision)) which:
    1. Loads the checkpointed state for this incident
    2. Resumes execution from the interrupt() call
    3. The decision becomes the return value of interrupt()
    4. The graph continues to process_decision_node
    5. State is saved with the final outcome

    Args:
        incident_id: The incident ID (used as thread_id)
        decision: The decision dict with approved, approved_by, etc.
    """
    logger.info(
        f"[Webhook] Resuming approval graph for {incident_id} "
        f"with decision: approved={decision.get('approved')}"
    )

    # The config must have the same thread_id as when the graph was started
    config = {"configurable": {"thread_id": incident_id}}

    # Create the resume command
    # This is what "wakes up" the paused graph
    resume_command = Command(resume=decision)

    try:
        result = await approval_subgraph.ainvoke(resume_command, config)

        logger.info(
            f"[Webhook] Graph resumed successfully for {incident_id}. "
            f"Final approved state: {result.get('approved')}"
        )

    except Exception as e:
        logger.error(f"[Webhook] Error resuming graph for {incident_id}: {e}")
        raise


async def resume_execution_graph(incident_id: str, decision: str) -> None:
    """
    Resume the execution graph with the human's decision.

    This is called when a human clicks Execute/Skip/Abort on a risky action.

    The decision is a simple string:
    - "execute": Proceed with the risky action
    - "skip": Skip this action, continue with next
    - "abort": Stop all execution

    Args:
        incident_id: The incident ID (used as thread_id)
        decision: One of "execute", "skip", "abort"
    """
    logger.info(
        f"[Webhook] Resuming execution graph for {incident_id} "
        f"with decision: {decision}"
    )

    # The config must have the same thread_id as when the graph was started
    config = {"configurable": {"thread_id": incident_id}}

    # Create the resume command with the decision string
    resume_command = Command(resume=decision)

    try:
        result = await executor_subgraph.ainvoke(resume_command, config)

        logger.info(
            f"[Webhook] Execution graph resumed for {incident_id}. "
            f"All succeeded: {result.get('all_succeeded')}"
        )

    except Exception as e:
        logger.error(f"[Webhook] Error resuming execution graph for {incident_id}: {e}")
        raise


@router.get("/slack/health")
async def slack_webhook_health():
    """
    Health check for Slack webhook endpoint.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "endpoint": "/agent/slack/interactions",
        "signing_secret_configured": bool(
            getattr(settings, "SLACK_SIGNING_SECRET", None)
        ),
    }
