import logging
import uuid
from typing import Dict, Any, Literal
from datetime import datetime

from backend.modules.orchestrator.state import OrchestratorState
from backend.config.settings import settings
from backend.modules.monitors.graph import monitor_subgraph
from backend.modules.analyzes.graph import analyzer_subgraph
from backend.modules.execution.graph import executor_subgraph
from backend.modules.summary.graph import summary_subgraph


logger = logging.getLogger(__name__)



def receive_alert_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Node 1: Initialize incident from incoming alert.

    This is the entry point for the orchestrator.
    It creates the incident ID, sets initial status, and extracts alert data.

    Reads: alert, severity (from input)
    Writes: incident_id, status, created_at, updated_at, slack_channel

    Args:
        state: Initial state with alert data

    Returns:
        Dict with initialized incident fields
    """
    # Generate incident ID if not provided
    incident_id = state.get("incident_id") or _generate_incident_id()

    alert = state.get("alert", {})
    severity = state.get("severity") or alert.get("severity", "medium")

    logger.info(f"[Orchestrator] Received alert for incident {incident_id}")
    logger.info(f"[Orchestrator] Alert: {alert.get('alertname', 'unknown')}, Severity: {severity}")

    now = datetime.utcnow().isoformat()

    return {
        "incident_id": incident_id,
        "status": "monitoring",
        "created_at": now,
        "updated_at": now,
        "severity": severity,
        "iteration_count": 0,
        "slack_channel": state.get("slack_channel") or settings.SLACK_DEFAULT_CHANNEL,
        "messages_sent": [],
    }


async def run_monitor_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Node 2: Run the Monitor subgraph to collect metrics, logs, and status.

    Invokes the Monitor subgraph and maps its output back to orchestrator state.

    Reads: alert (for service/namespace)
    Writes: metrics, logs, pod_status, events, recent_deployments, status

    Args:
        state: Current orchestrator state

    Returns:
        Dict with monitor output fields
    """

    incident_id = state.get("incident_id", "unknown")
    alert = state.get("alert") or {}
    labels = alert.get("labels") or {}

    logger.info(f"[Orchestrator] Running Monitor subgraph for {incident_id}")

    # Map orchestrator state to monitor input
    monitor_input = {
        "service": alert.get("service") or labels.get("service", "unknown"),
        "namespace": alert.get("namespace") or labels.get("namespace", "default"),
        "alert_labels": labels,
        "time_range": "15m",
    }

    logger.info(f"[Orchestrator] Monitor input: service={monitor_input['service']}, namespace={monitor_input['namespace']}")

    try:
        # Invoke the monitor subgraph
        result = await monitor_subgraph.ainvoke(monitor_input)

        logger.info(f"[Orchestrator] Monitor completed for {incident_id}")

        return {
            "status": "analyzing",
            "updated_at": datetime.utcnow().isoformat(),
            "metrics": result.get("metrics", {}),
            "logs": result.get("logs", []),
            "pod_status": result.get("pod_status", {}),
            "events": result.get("events", []),
            "recent_deployments": result.get("recent_deployments", []),
        }

    except Exception as e:
        logger.error(f"[Orchestrator] Monitor failed for {incident_id}: {e}")
        return {
            "status": "failed",
            "error": f"Monitor failed: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


async def run_analyzer_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Node 3: Run the Analyzer subgraph to identify root cause and recommend actions.

    Invokes the Analyzer subgraph with monitor data.

    Reads: alert, severity, metrics, logs, pod_status, events, recent_deployments
    Writes: root_cause, confidence, analysis_reasoning, similar_incidents,
            recommended_actions, needs_approval, status

    Args:
        state: Current orchestrator state with monitor data

    Returns:
        Dict with analyzer output fields
    """
    incident_id = state.get("incident_id", "unknown")

    logger.info(f"[Orchestrator] Running Analyzer subgraph for {incident_id}")

    # Map orchestrator state to analyzer input
    analyzer_input = {
        "alert": state.get("alert", {}),
        "severity": state.get("severity", "medium"),
        "metrics": state.get("metrics", {}),
        "logs": state.get("logs", []),
        "pod_status": state.get("pod_status", {}),
        "events": state.get("events", []),
        "recent_deployments": state.get("recent_deployments", []),
        "health_summary": state.get("health_summary", ""),
    }

    try:
        # Invoke the analyzer subgraph
        result = await analyzer_subgraph.ainvoke(analyzer_input)

        logger.info(
            f"[Orchestrator] Analyzer completed for {incident_id}: "
            f"root_cause={result.get('root_cause', 'unknown')[:50]}..., "
            f"confidence={result.get('confidence', 0):.2f}"
        )

        # Determine if approval is needed
        needs_approval = result.get("requires_approval", True)

        return {
            "status": "pending_approval" if needs_approval else "approved",
            "updated_at": datetime.utcnow().isoformat(),
            "root_cause": result.get("root_cause", "Unable to determine root cause"),
            "confidence": result.get("confidence", 0.0),
            "analysis_reasoning": result.get("analysis_reasoning", ""),
            "similar_incidents": result.get("similar_incidents", []),
            "recommended_actions": result.get("recommended_actions", []),
            "needs_approval": needs_approval,
        }

    except Exception as e:
        logger.error(f"[Orchestrator] Analyzer failed for {incident_id}: {e}")
        return {
            "status": "failed",
            "error": f"Analyzer failed: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


async def run_approval_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Node 4a: Request human approval via Slack and wait for decision.

    This node:
    1. Sends a Slack message with approve/reject buttons
    2. Calls interrupt() to pause the orchestrator graph
    3. Resumes when the API receives the decision via Command(resume=...)

    The interrupt happens in THIS node (not a subgraph) so the parent
    orchestrator graph properly pauses and can be resumed.

    Reads: incident_id, severity, root_cause, confidence, evidence,
           recommended_actions, similar_incidents, slack_channel
    Writes: approved, approved_by, approval_time, rejection_reason,
            modified_actions, status

    Args:
        state: Current orchestrator state

    Returns:
        Dict with approval output fields
    """
    from langgraph.types import interrupt
    from backend.modules.approval.clients.slack import SlackClient

    incident_id = state.get("incident_id", "unknown")

    print("=" * 60)
    print(f"[APPROVAL NODE] Entered run_approval_node for {incident_id}")
    print("=" * 60)
    logger.info(f"[Orchestrator] Running Approval for {incident_id}")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 1: Send approval request to Slack
    # ═══════════════════════════════════════════════════════════════════════
    # NOTE: When the graph resumes after interrupt(), this node re-executes.
    # We check approval_requested_at in state to prevent duplicate messages.
    slack_token = getattr(settings, "SLACK_BOT_TOKEN", None)
    slack_channel = state.get("slack_channel", settings.SLACK_DEFAULT_CHANNEL)
    approval_message_ts = None
    slack_channel_id = None

    # Check if we've already sent the Slack message (from a previous run before interrupt)
    already_requested = state.get("approval_requested_at") is not None

    if slack_token and not already_requested:
        slack = SlackClient(
            token=slack_token,
            default_channel=slack_channel,
        )
        result = await slack.send_approval_request(
            incident_id=incident_id,
            severity=state.get("severity", "unknown"),
            root_cause=state.get("root_cause", "Unknown root cause"),
            confidence=state.get("confidence", 0.0),
            evidence=_extract_evidence(state),
            recommended_actions=state.get("recommended_actions", []),
            similar_incidents=state.get("similar_incidents"),
            channel=slack_channel,
            thread_ts=state.get("slack_thread_ts"),
        )
        if result.get("ok"):
            approval_message_ts = result.get("ts")
            slack_channel_id = result.get("channel")
            logger.info(f"[Orchestrator] Slack approval request sent: channel={slack_channel_id}, ts={approval_message_ts}")
        else:
            logger.error(f"[Orchestrator] Slack send failed: {result.get('error')}")
    elif already_requested:
        logger.info(f"[Orchestrator] Approval already requested, skipping duplicate Slack message")
    elif not slack_token:
        logger.warning("[Orchestrator] No SLACK_BOT_TOKEN configured - approval request simulated")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2: INTERRUPT - Wait for human decision
    # ═══════════════════════════════════════════════════════════════════════
    # This pauses the ENTIRE orchestrator graph until Command(resume=...) is called
    print("=" * 60)
    print(f"[APPROVAL NODE] About to call interrupt() for {incident_id}")
    print("[APPROVAL NODE] Graph will PAUSE here until Slack approval received")
    print("=" * 60)
    logger.info(f"[Orchestrator] Waiting for human decision on incident {incident_id}")

    decision = interrupt({
        "type": "approval_required",
        "incident_id": incident_id,
        "slack_channel": slack_channel,
        "slack_message_ts": approval_message_ts,
        "pending_actions": state.get("recommended_actions", []),
        "expected_response": {
            "approved": "bool - True to approve, False to reject",
            "approved_by": "str - User ID who made the decision",
            "approved_by_name": "str (optional) - Human-readable name",
            "rejection_reason": "str (optional) - Why rejected",
            "modified_actions": "list (optional) - Modified action list",
            "approval_notes": "str (optional) - Any notes from approver",
        },
        "resume_with": "Command(resume={'approved': True/False, 'approved_by': '...', ...})",
    })

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3: Process the decision (after resume)
    # ═══════════════════════════════════════════════════════════════════════
    print("=" * 60)
    print(f"[APPROVAL NODE] Resumed from interrupt for {incident_id}!")
    print(f"[APPROVAL NODE] Decision received: {decision}")
    print("=" * 60)
    logger.info(f"[Orchestrator] Decision received for {incident_id}: {decision}")

    approved = decision.get("approved", False)
    approved_by = decision.get("approved_by", "unknown")
    approved_by_name = decision.get("approved_by_name")
    rejection_reason = decision.get("rejection_reason")
    modified_actions = decision.get("modified_actions")

    # Get channel/message info from the decision (passed from Slack webhook)
    decision_channel_id = decision.get("slack_channel_id")
    decision_message_ts = decision.get("slack_message_ts")

    # Log the decision
    if approved:
        logger.info(f"[Orchestrator] ✅ Incident {incident_id} APPROVED by {approved_by_name or approved_by}")
    else:
        logger.info(f"[Orchestrator] ❌ Incident {incident_id} REJECTED by {approved_by_name or approved_by}")
        if rejection_reason:
            logger.info(f"[Orchestrator] Rejection reason: {rejection_reason}")

    # Update Slack message to show decision (if configured)
    # Prefer channel/ts from decision (from webhook), fallback to local vars
    update_channel = decision_channel_id or slack_channel_id or slack_channel
    update_message_ts = decision_message_ts or approval_message_ts
    if slack_token and update_channel and update_message_ts:
        try:
            slack = SlackClient(token=slack_token)
            await slack.update_approval_message(
                channel=update_channel,
                message_ts=update_message_ts,
                decision="approved" if approved else "rejected",
                decided_by=approved_by,
                decided_by_name=approved_by_name,
                reason=rejection_reason,
            )
            logger.info(f"[Orchestrator] Updated Slack message for {incident_id}")
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to update Slack message: {e}")

    return {
        "status": "approved" if approved else "rejected",
        "updated_at": datetime.utcnow().isoformat(),
        "approved": approved,
        "approved_by": approved_by,
        "approved_by_name": approved_by_name,
        "approval_time": datetime.utcnow().isoformat(),
        "rejection_reason": rejection_reason,
        "modified_actions": modified_actions,
        "approval_notes": decision.get("approval_notes"),
        "approval_requested_at": datetime.utcnow().isoformat(),
    }


def skip_approval_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Node 4b: Skip approval when auto-approve conditions are met.

    This is called when:
    - High confidence (> threshold)
    - Low severity
    - All actions are low-risk

    Reads: (nothing additional)
    Writes: approved, approved_by, status

    Args:
        state: Current orchestrator state

    Returns:
        Dict with auto-approval fields
    """
    incident_id = state.get("incident_id", "unknown")

    logger.info(f"[Orchestrator] Auto-approving incident {incident_id}")
    logger.info(
        f"[Orchestrator] Reason: confidence={state.get('confidence', 0):.2f}, "
        f"severity={state.get('severity')}, all actions low-risk"
    )

    return {
        "status": "approved",
        "updated_at": datetime.utcnow().isoformat(),
        "approved": True,
        "approved_by": "auto-approve",
        "approval_time": datetime.utcnow().isoformat(),
        "needs_approval": False,
    }


async def handle_rejection_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Node 5b: Handle rejected incidents.

    When an incident is rejected, we:
    1. Log the rejection
    2. Optionally notify via Slack
    3. Mark as escalated for manual handling

    Reads: incident_id, rejection_reason, approved_by
    Writes: status

    Args:
        state: Current orchestrator state

    Returns:
        Dict with rejection handling fields
    """
    incident_id = state.get("incident_id", "unknown")
    rejection_reason = state.get("rejection_reason", "No reason provided")
    rejected_by = state.get("approved_by", "unknown")

    logger.info(f"[Orchestrator] Incident {incident_id} was REJECTED by {rejected_by}")
    logger.info(f"[Orchestrator] Rejection reason: {rejection_reason}")

    # TODO: Optionally send Slack notification about rejection
    # TODO: Create a ticket for manual review

    return {
        "status": "escalated",
        "updated_at": datetime.utcnow().isoformat(),
    }


async def run_executor_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Node 5a: Run the Executor subgraph to execute approved actions.

    Invokes the Executor subgraph with approved actions.

    Reads: incident_id, approved, approved_by, recommended_actions,
           modified_actions, slack_channel, slack_thread_ts
    Writes: execution_results, all_succeeded, execution_started_at,
            execution_completed_at, status

    Args:
        state: Current orchestrator state with approval

    Returns:
        Dict with execution output fields
    """

    incident_id = state.get("incident_id", "unknown")

    logger.info(f"[Orchestrator] Running Executor subgraph for {incident_id}")

    # Use modified actions if provided, otherwise use recommended actions
    actions = state.get("modified_actions") or state.get("recommended_actions", [])

    # Map orchestrator state to executor input
    executor_input = {
        "incident_id": incident_id,
        "approved": state.get("approved", False),
        "approved_by": state.get("approved_by", "unknown"),
        "actions_to_execute": actions,
        "dry_run": settings.EXECUTION_DRY_RUN,
        "stop_on_failure": settings.EXECUTION_STOP_ON_FAILURE,
        "timeout_seconds": settings.EXECUTION_TIMEOUT_SECONDS,
        "slack_channel": state.get("slack_channel", settings.SLACK_DEFAULT_CHANNEL),
        "slack_thread_ts": state.get("slack_thread_ts"),
    }

    # Use incident_id as thread_id for checkpointing
    config = {"configurable": {"thread_id": incident_id}}

    execution_started = datetime.utcnow().isoformat()

    try:
        # Invoke the executor subgraph
        result = await executor_subgraph.ainvoke(executor_input, config)

        all_succeeded = result.get("all_succeeded", False)
        logger.info(
            f"[Orchestrator] Executor completed for {incident_id}: "
            f"all_succeeded={all_succeeded}"
        )

        return {
            "status": "resolved" if all_succeeded else "failed",
            "updated_at": datetime.utcnow().isoformat(),
            "execution_started_at": execution_started,
            "execution_completed_at": datetime.utcnow().isoformat(),
            "execution_results": result.get("execution_results", []),
            "all_succeeded": all_succeeded,
        }

    except Exception as e:
        logger.error(f"[Orchestrator] Executor failed for {incident_id}: {e}")
        return {
            "status": "failed",
            "error": f"Executor failed: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
            "execution_started_at": execution_started,
            "all_succeeded": False,
        }


async def run_summary_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Node 6: Run the Summary subgraph to generate incident summary.

    Invokes the Summary subgraph to create summary and postmortem.

    Reads: All relevant fields from state
    Writes: summary, resolution_time_seconds, postmortem_created, status

    Args:
        state: Current orchestrator state

    Returns:
        Dict with summary output fields
    """

    incident_id = state.get("incident_id", "unknown")

    logger.info(f"[Orchestrator] Running Summary subgraph for {incident_id}")

    # Map orchestrator state to summary input
    summary_input = {
        "incident_id": incident_id,
        "severity": state.get("severity", "unknown"),
        "alert": state.get("alert", {}),
        "root_cause": state.get("root_cause", "Unknown"),
        "confidence": state.get("confidence", 0.0),
        "evidence": _extract_evidence(state),
        "recommended_actions": state.get("recommended_actions", []),
        "approved_by": state.get("approved_by"),
        "execution_results": state.get("execution_results", []),
        "all_succeeded": state.get("all_succeeded", False),
        "created_at": state.get("created_at"),
        "slack_channel": state.get("slack_channel", settings.SLACK_DEFAULT_CHANNEL),
        "slack_thread_ts": state.get("slack_thread_ts"),
    }

    try:
        # Invoke the summary subgraph
        result = await summary_subgraph.ainvoke(summary_input)

        logger.info(f"[Orchestrator] Summary completed for {incident_id}")

        # Determine final status
        final_status = state.get("status", "resolved")
        if final_status not in ["failed", "escalated"]:
            final_status = "resolved" if state.get("all_succeeded", False) else "failed"

        return {
            "status": final_status,
            "updated_at": datetime.utcnow().isoformat(),
            "summary": result.get("summary", ""),
            "resolution_time_seconds": result.get("resolution_time_seconds", 0.0),
            "postmortem_created": bool(result.get("postmortem_ticket")),
        }

    except Exception as e:
        logger.error(f"[Orchestrator] Summary failed for {incident_id}: {e}")
        # Don't fail the whole incident just because summary failed
        return {
            "updated_at": datetime.utcnow().isoformat(),
            "summary": f"Summary generation failed: {str(e)}",
            "postmortem_created": False,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def route_after_analyzer(state: OrchestratorState) -> Literal["run_approval", "skip_approval"]:
    """
    Determine whether to require human approval or auto-approve.

    Auto-approve conditions:
    - needs_approval is explicitly False from analyzer
    - OR all of:
      - High confidence (> threshold)
      - Low/medium severity
      - All actions are in auto-approve risk levels

    Args:
        state: Current orchestrator state

    Returns:
        Next node name: "run_approval" or "skip_approval"
    """
    incident_id = state.get("incident_id", "unknown")

    # If analyzer explicitly said no approval needed
    if state.get("needs_approval") is False:
        logger.info(f"[Orchestrator] {incident_id}: Analyzer said no approval needed")
        return "skip_approval"

    # Check auto-approve conditions
    confidence = state.get("confidence", 0.0)
    severity = state.get("severity", "high")
    actions = state.get("recommended_actions", [])

    confidence_ok = confidence >= settings.CONFIDENCE_THRESHOLD
    severity_ok = severity in ["low", "medium"]
    actions_ok = all(
        a.get("risk_level", "high") in settings.AUTO_APPROVE_RISK_LEVELS
        for a in actions
    ) if actions else False

    if confidence_ok and severity_ok and actions_ok:
        logger.info(
            f"[Orchestrator] {incident_id}: Auto-approving "
            f"(confidence={confidence:.2f}, severity={severity}, all actions low-risk)"
        )
        return "skip_approval"

    logger.info(
        f"[Orchestrator] {incident_id}: Requiring approval "
        f"(confidence={confidence:.2f}, severity={severity})"
    )
    return "run_approval"


def route_after_approval(state: OrchestratorState) -> Literal["run_executor", "handle_rejection"]:
    """
    Determine whether to execute or handle rejection based on approval decision.

    Args:
        state: Current orchestrator state with approval decision

    Returns:
        Next node name: "run_executor" or "handle_rejection"
    """
    incident_id = state.get("incident_id", "unknown")
    approved = state.get("approved", False)

    if approved:
        logger.info(f"[Orchestrator] {incident_id}: Approved, proceeding to execution")
        return "run_executor"
    else:
        logger.info(f"[Orchestrator] {incident_id}: Rejected, handling rejection")
        return "handle_rejection"


def route_after_execution(state: OrchestratorState) -> Literal["run_summary", "__end__"]:
    """
    Determine whether to generate summary or end.

    Args:
        state: Current orchestrator state

    Returns:
        Next node name: "run_summary" or "__end__"
    """
    # Always run summary for completed executions
    status = state.get("status", "")

    if status in ["resolved", "failed"]:
        return "run_summary"

    # For escalated incidents, skip summary
    return "__end__"



def _generate_incident_id() -> str:
    """Generate a unique incident ID."""
    date_str = datetime.utcnow().strftime("%Y%m%d")
    unique_id = uuid.uuid4().hex[:6].upper()
    return f"INC-{date_str}-{unique_id}"


def _extract_evidence(state: OrchestratorState) -> list:
    """Extract evidence points from state for display."""
    evidence = []

    # From metrics
    metrics = state.get("metrics") or {}
    cpu_usage = metrics.get("cpu_usage_percent") or 0
    memory_usage = metrics.get("memory_usage_percent") or 0
    error_rate = metrics.get("error_rate_percent") or 0

    if cpu_usage > 80:
        evidence.append(f"High CPU usage: {cpu_usage}%")
    if memory_usage > 80:
        evidence.append(f"High memory usage: {memory_usage}%")
    if error_rate > 5:
        evidence.append(f"High error rate: {error_rate}%")

    # From pod status
    pod_status = state.get("pod_status") or {}
    failed_pods = pod_status.get("failed") or 0
    unhealthy_pods = pod_status.get("unhealthy_pods") or 0

    if failed_pods > 0:
        evidence.append(f"{failed_pods} failed pods")
    if unhealthy_pods > 0:
        evidence.append(f"{unhealthy_pods} unhealthy pods")

    # From events
    events = state.get("events") or []
    oom_events = [e for e in events if "OOM" in str((e.get("reason") if e else "") or "")]
    if oom_events:
        evidence.append(f"{len(oom_events)} OOMKilled events")

    # From recent deployments
    deployments = state.get("recent_deployments") or []
    if deployments and deployments[0]:
        latest = deployments[0]
        evidence.append(f"Recent deployment: {latest.get('name', 'unknown')}")

    return evidence if evidence else ["No specific evidence extracted"]
