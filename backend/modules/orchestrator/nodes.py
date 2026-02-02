import logging
import uuid
from typing import Dict, Any, Literal
from datetime import datetime

from backend.modules.orchestrator.state import OrchestratorState
from backend.config.settings import settings
from backend.modules.monitors.graph import monitor_subgraph
from backend.modules.analyzes.graph import analyzer_subgraph
from backend.modules.approval.graph import approval_subgraph
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
    alert = state.get("alert", {})

    logger.info(f"[Orchestrator] Running Monitor subgraph for {incident_id}")

    # Map orchestrator state to monitor input
    monitor_input = {
        "service": alert.get("service", alert.get("labels", {}).get("service", "unknown")),
        "namespace": alert.get("namespace", alert.get("labels", {}).get("namespace", "default")),
        "alert_labels": alert.get("labels", {}),
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
    Node 4a: Run the Approval subgraph for human-in-the-loop.

    This node invokes the approval subgraph which will:
    1. Send a Slack message with approve/reject buttons
    2. Pause at interrupt() waiting for human decision
    3. Resume when the webhook receives the decision

    NOTE: This node will BLOCK until the human makes a decision!

    Reads: incident_id, severity, root_cause, confidence, evidence,
           recommended_actions, similar_incidents, slack_channel
    Writes: approved, approved_by, approval_time, rejection_reason,
            modified_actions, status

    Args:
        state: Current orchestrator state

    Returns:
        Dict with approval output fields
    """
    incident_id = state.get("incident_id", "unknown")

    logger.info(f"[Orchestrator] Running Approval subgraph for {incident_id}")
    logger.info(f"[Orchestrator] This will pause until human approves/rejects")

    # Map orchestrator state to approval input
    approval_input = {
        "incident_id": incident_id,
        "severity": state.get("severity", "medium"),
        "root_cause": state.get("root_cause", "Unknown"),
        "confidence": state.get("confidence", 0.0),
        "evidence": _extract_evidence(state),
        "recommended_actions": state.get("recommended_actions", []),
        "similar_incidents": state.get("similar_incidents", []),
        "slack_channel": state.get("slack_channel", settings.SLACK_DEFAULT_CHANNEL),
        "slack_thread_ts": state.get("slack_thread_ts"),
    }

    # Use incident_id as thread_id for checkpointing
    config = {"configurable": {"thread_id": incident_id}}

    try:
        # Invoke the approval subgraph
        # This will BLOCK at interrupt() until human decision
        result = await approval_subgraph.ainvoke(approval_input, config)

        approved = result.get("approved", False)
        logger.info(
            f"[Orchestrator] Approval completed for {incident_id}: "
            f"approved={approved}, by={result.get('approved_by', 'unknown')}"
        )

        return {
            "status": "approved" if approved else "rejected",
            "updated_at": datetime.utcnow().isoformat(),
            "approved": approved,
            "approved_by": result.get("approved_by"),
            "approval_time": result.get("approval_time"),
            "rejection_reason": result.get("rejection_reason"),
            "modified_actions": result.get("modified_actions"),
            "approval_requested_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"[Orchestrator] Approval failed for {incident_id}: {e}")
        return {
            "status": "failed",
            "error": f"Approval failed: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
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
    metrics = state.get("metrics", {})
    if metrics.get("cpu_usage_percent", 0) > 80:
        evidence.append(f"High CPU usage: {metrics.get('cpu_usage_percent')}%")
    if metrics.get("memory_usage_percent", 0) > 80:
        evidence.append(f"High memory usage: {metrics.get('memory_usage_percent')}%")
    if metrics.get("error_rate_percent", 0) > 5:
        evidence.append(f"High error rate: {metrics.get('error_rate_percent')}%")

    # From pod status
    pod_status = state.get("pod_status", {})
    if pod_status.get("failed", 0) > 0:
        evidence.append(f"{pod_status.get('failed')} failed pods")
    if pod_status.get("unhealthy_pods", 0) > 0:
        evidence.append(f"{pod_status.get('unhealthy_pods')} unhealthy pods")

    # From events
    events = state.get("events", [])
    oom_events = [e for e in events if "OOM" in str(e.get("reason", ""))]
    if oom_events:
        evidence.append(f"{len(oom_events)} OOMKilled events")

    # From recent deployments
    deployments = state.get("recent_deployments", [])
    if deployments:
        latest = deployments[0]
        evidence.append(f"Recent deployment: {latest.get('name', 'unknown')}")

    return evidence if evidence else ["No specific evidence extracted"]
