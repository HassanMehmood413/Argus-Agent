import hashlib
import hmac
import time
import logging

from fastapi import HTTPException, Request
from backend.config.settings import settings
from langgraph.types import Command
from backend.modules.orchestrator.graph import orchestrator_graph
from backend.modules.execution.graph import executor_subgraph
from backend.modules.orchestrator import process_incident

logger = logging.getLogger(__name__)



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
    print("=" * 60)
    print("[SLACK WEBHOOK] Button click received!")
    print("=" * 60)

    # Extract action details
    actions = payload.get("actions", [])
    if not actions:
        logger.warning("[Webhook] No actions in payload")
        print("[SLACK WEBHOOK] WARNING: No actions in payload")
        return {"ok": True}

    action = actions[0]
    action_id = action.get("action_id")
    incident_id = action.get("value")

    # Extract user info
    user = payload.get("user", {})
    user_id = user.get("id", "unknown")
    user_name = user.get("name") or user.get("username", "Unknown")

    # Extract channel and message info from Slack payload
    # This is needed to update the original approval message
    container = payload.get("container", {})
    slack_channel_id = container.get("channel_id") or payload.get("channel", {}).get("id")
    slack_message_ts = container.get("message_ts")

    print(f"[SLACK WEBHOOK] Action ID: {action_id}")
    print(f"[SLACK WEBHOOK] Incident ID: {incident_id}")
    print(f"[SLACK WEBHOOK] User: {user_name} ({user_id})")
    print(f"[SLACK WEBHOOK] Channel ID: {slack_channel_id}")
    print(f"[SLACK WEBHOOK] Message TS: {slack_message_ts}")

    logger.info(
        f"[Webhook] Button click: action={action_id}, "
        f"incident={incident_id}, user={user_name}, channel={slack_channel_id}"
    )

    # ═══════════════════════════════════════════════════════════════════════
    # APPROVAL MODULE BUTTONS
    # ═══════════════════════════════════════════════════════════════════════
    if action_id == "approve_incident":
        decision = {
            "approved": True,
            "approved_by": user_id,
            "approved_by_name": user_name,
            "slack_channel_id": slack_channel_id,
            "slack_message_ts": slack_message_ts,
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
            "slack_channel_id": slack_channel_id,
            "slack_message_ts": slack_message_ts,
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
            "slack_channel_id": slack_channel_id,
            "slack_message_ts": slack_message_ts,
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
    Resume the orchestrator graph with the human's approval decision.

    THIS IS THE KEY FUNCTION!

    It calls graph.invoke(Command(resume=decision)) which:
    1. Loads the checkpointed state for this incident
    2. Resumes execution from the interrupt() call in run_approval_node
    3. The decision becomes the return value of interrupt()
    4. The orchestrator continues to execution or rejection handling
    5. State is saved with the final outcome

    Args:
        incident_id: The incident ID (used as thread_id)
        decision: The decision dict with approved, approved_by, etc.
    """
    print("=" * 60)
    print(f"[RESUME] Resuming orchestrator for incident: {incident_id}")
    print(f"[RESUME] Decision: approved={decision.get('approved')}")
    print(f"[RESUME] Approved by: {decision.get('approved_by_name', decision.get('approved_by'))}")
    print("=" * 60)

    logger.info(
        f"[Webhook] Resuming orchestrator graph for {incident_id} "
        f"with decision: approved={decision.get('approved')}"
    )

    # The config must have the same thread_id as when the graph was started
    config = {"configurable": {"thread_id": incident_id}}

    print(f"[RESUME] Using config: {config}")
    logger.info(f"[Webhook] Using config: {config}")

    # Create the resume command
    # This is what "wakes up" the paused graph
    resume_command = Command(resume=decision)

    print(f"[RESUME] Created Command(resume={decision})")
    logger.info(f"[Webhook] Created Command(resume={decision})")

    try:
        # Check if there's a checkpointed state for this thread_id
        checkpointer = orchestrator_graph.checkpointer
        if checkpointer:
            try:
                state = await orchestrator_graph.aget_state(config)
                if state and state.values:
                    logger.info(f"[Webhook] Found checkpointed state for {incident_id}")
                    logger.info(f"[Webhook] State keys: {list(state.values.keys())}")
                    logger.info(f"[Webhook] Next nodes: {state.next}")
                else:
                    logger.warning(f"[Webhook] NO checkpointed state found for {incident_id}!")
                    logger.warning("[Webhook] This means the graph was never started with this thread_id")
            except Exception as e:
                logger.warning(f"[Webhook] Could not check state: {e}")

        # Resume the ORCHESTRATOR graph (not approval subgraph)
        # The interrupt() is now in run_approval_node within the orchestrator
        print(f"[RESUME] Calling orchestrator_graph.ainvoke(resume_command, config)...")
        result = await orchestrator_graph.ainvoke(resume_command, config)

        print("=" * 60)
        print(f"[RESUME] SUCCESS! Orchestrator resumed for {incident_id}")
        print(f"[RESUME] Final status: {result.get('status')}")
        print(f"[RESUME] Approved: {result.get('approved')}")
        print(f"[RESUME] Approved by: {result.get('approved_by')}")
        print("=" * 60)

        logger.info(
            f"[Webhook] Orchestrator resumed successfully for {incident_id}. "
            f"Final status: {result.get('status')}, approved: {result.get('approved')}"
        )

    except Exception as e:
        print("=" * 60)
        print(f"[RESUME] ERROR resuming orchestrator for {incident_id}")
        print(f"[RESUME] Error: {e}")
        print("=" * 60)
        logger.error(f"[Webhook] Error resuming orchestrator for {incident_id}: {e}")
        import traceback
        logger.error(f"[Webhook] Traceback: {traceback.format_exc()}")
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




# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASK
# ═══════════════════════════════════════════════════════════════════════════════

async def _process_incident_background(
    alert: dict,
    severity: str,
    incident_id: str,
    slack_channel: str = None,
) -> None:
    """Background task to process incident."""

    logger.info(f"[API Background] Starting processing for {incident_id}")

    try:
        result = await process_incident(
            alert=alert,
            severity=severity,
            incident_id=incident_id,
            slack_channel=slack_channel,
        )

        logger.info(
            f"[API Background] Completed processing for {incident_id}: "
            f"status={result.get('status')}"
        )

    except Exception as e:
        logger.error(f"[API Background] Error processing {incident_id}: {e}")
        import traceback
        logger.error(f"[API Background] Traceback: {traceback.format_exc()}")
