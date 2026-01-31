"""
Test Routes

FastAPI routes for testing each agent module with dummy data.
Access these via Swagger UI at /docs
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
import uuid
import time
import logging

from backend.routes_modules.test.schemas import (
    MonitorTestRequest,
    MonitorTestResponse,
    AnalyzerTestRequest,
    AnalyzerTestResponse,
    ApprovalTestRequest,
    ApprovalTestResponse,
    ExecutionTestRequest,
    ExecutionTestResponse,
    FullPipelineTestRequest,
    FullPipelineTestResponse,
)
from backend.routes_modules.test.dummy_data import (
    get_dummy_metrics,
    get_dummy_pod_status,
    get_dummy_events,
    get_dummy_logs,
    get_dummy_deployments,
    get_dummy_alert,
    get_dummy_patterns,
    get_dummy_recommended_actions,
    get_dummy_execution_result,
)
from backend.modules.approval.clients.slack import SlackClient
from backend.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test", tags=["Test Endpoints"])


# ═══════════════════════════════════════════════════════════════════════════════
# MONITOR MODULE TEST
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/monitor",
    response_model=MonitorTestResponse,
    summary="Test Monitor Module",
    description="""
    Test the Monitor module with dummy data.

    This simulates what the Monitor subgraph would collect:
    - Prometheus metrics (CPU, memory, error rate, latency)
    - Pod status from Kubernetes
    - Recent events
    - Application logs
    - Recent deployments

    **Note**: This returns simulated data, not real Kubernetes/Prometheus data.
    """
)
async def test_monitor(request: MonitorTestRequest) -> MonitorTestResponse:
    """Test the Monitor module with simulated data gathering."""

    metrics = get_dummy_metrics(request.service, request.namespace)
    pod_status = get_dummy_pod_status(request.service, request.namespace)
    events = get_dummy_events(request.service, request.namespace)
    logs = get_dummy_logs(request.service)
    deployments = get_dummy_deployments(request.service, request.namespace)

    # Generate health summary
    issues = []
    if metrics["cpu_usage"]["current"] > 80:
        issues.append(f"High CPU usage: {metrics['cpu_usage']['current']}%")
    if metrics["memory_usage"]["current"] > 85:
        issues.append(f"High memory usage: {metrics['memory_usage']['current']}%")
    if metrics["error_rate"]["current"] > metrics["error_rate"]["threshold"]:
        issues.append(f"Error rate above threshold: {metrics['error_rate']['current']}%")
    if pod_status["unhealthy_pods"] > 0:
        issues.append(f"{pod_status['unhealthy_pods']} unhealthy pods")

    health_summary = (
        f"Service {request.service} in {request.namespace}: "
        f"{len(issues)} issues detected. " + "; ".join(issues) if issues
        else f"Service {request.service} in {request.namespace}: All systems healthy"
    )

    return MonitorTestResponse(
        service=request.service,
        namespace=request.namespace,
        metrics=metrics,
        pod_status=pod_status,
        events=events,
        logs=logs,
        recent_deployments=deployments,
        health_summary=health_summary,
        errors=[]
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYZER MODULE TEST
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/analyzer",
    response_model=AnalyzerTestResponse,
    summary="Test Analyzer Module",
    description="""
    Test the Analyzer module with pattern detection.

    This simulates:
    - Pattern detection (memory issues, error spikes, crash loops)
    - Root cause analysis
    - Action recommendations

    Set `use_llm=True` to use actual LLM analysis (requires OPENAI_API_KEY).
    Otherwise, rule-based analysis is used.
    """
)
async def test_analyzer(request: AnalyzerTestRequest) -> AnalyzerTestResponse:
    """Test the Analyzer module with pattern detection."""

    alert = get_dummy_alert(request.alert_name, request.severity, request.service)
    patterns = get_dummy_patterns()
    recommended_actions = get_dummy_recommended_actions(patterns)

    # Determine root cause from patterns
    critical_patterns = [p for p in patterns if p["severity"] in ["critical", "high"]]
    if critical_patterns:
        main_pattern = max(critical_patterns, key=lambda x: x["confidence"])
        root_cause = main_pattern["description"]
        confidence = main_pattern["confidence"]
    else:
        root_cause = "Multiple minor issues contributing to service degradation"
        confidence = 0.6

    # Gather evidence
    evidence = []
    for p in patterns:
        evidence.extend(p["evidence"])

    # Determine if approval is required
    requires_approval = request.severity in ["high", "critical"] or any(
        a["risk"] in ["medium", "high"] for a in recommended_actions
    )

    analysis_reasoning = f"""
        Analysis based on {len(patterns)} detected patterns:
        {chr(10).join(f'- {p["type"]}: {p["description"]} (confidence: {p["confidence"]:.0%})' for p in patterns)}

        Root cause identified as: {root_cause}
        Confidence: {confidence:.0%}

        Recommended {len(recommended_actions)} actions, {'requiring approval' if requires_approval else 'auto-executable'}.
            """.strip()

    return AnalyzerTestResponse(
        root_cause=root_cause,
        confidence=confidence,
        evidence=evidence,
        analysis_reasoning=analysis_reasoning,
        recommended_actions=recommended_actions,
        requires_approval=requires_approval,
        patterns_detected=patterns
    )


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL MODULE TEST
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/approval",
    response_model=ApprovalTestResponse,
    summary="Test Approval Module - Sends REAL Slack Message",
    description="""
    Test the Approval module by sending a **REAL message to Slack**.

    This will:
    - Format a rich approval request with Block Kit
    - Send it to your configured Slack channel
    - Include Approve/Reject/Modify buttons

    **Requirements:**
    - `SLACK_BOT_TOKEN` must be set in `.env`
    - `SLACK_DEFAULT_CHANNEL` should be configured (or override with `slack_channel`)
    - Bot must be invited to the channel

    Set `send_to_slack=False` to only preview the message without sending.
    """
)
async def test_approval(request: ApprovalTestRequest) -> ApprovalTestResponse:
    """Test the Approval module by sending a real Slack message."""

    # Generate message preview
    actions_preview = "\n".join(
        f"  {i+1}. [{a.get('risk_level', 'unknown').upper()}] {a['type']} → {a['target']}"
        for i, a in enumerate(request.recommended_actions)
    )
    message_preview = f"""
🚨 Incident Alert: {request.incident_id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Severity: {request.severity.upper()}
Root Cause: {request.root_cause}
Confidence: {request.confidence:.0%}

Evidence:
{chr(10).join(f'  • {e}' for e in request.evidence)}

Recommended Actions:
{actions_preview}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """.strip()

    # Check if we should actually send to Slack
    if not request.send_to_slack:
        return ApprovalTestResponse(
            incident_id=request.incident_id,
            slack_sent=False,
            slack_error="send_to_slack=False (preview only)",
            message_preview=message_preview
        )

    # Check for Slack token
    if not settings.SLACK_BOT_TOKEN:
        return ApprovalTestResponse(
            incident_id=request.incident_id,
            slack_sent=False,
            slack_error="SLACK_BOT_TOKEN not configured in .env",
            message_preview=message_preview
        )

    # Determine channel
    channel = request.slack_channel or settings.SLACK_DEFAULT_CHANNEL

    # Create Slack client and send
    try:
        slack_client = SlackClient(
            token=settings.SLACK_BOT_TOKEN,
            default_channel=channel
        )

        result = await slack_client.send_approval_request(
            incident_id=request.incident_id,
            severity=request.severity,
            root_cause=request.root_cause,
            confidence=request.confidence,
            evidence=request.evidence,
            recommended_actions=request.recommended_actions,
            similar_incidents=None,
            channel=channel
        )

        if result.get("ok"):
            logger.info(f"✅ Slack message sent to {channel}, ts={result.get('ts')}")
            return ApprovalTestResponse(
                incident_id=request.incident_id,
                slack_sent=True,
                slack_channel=result.get("channel"),
                slack_message_ts=result.get("ts"),
                message_preview=message_preview
            )
        else:
            return ApprovalTestResponse(
                incident_id=request.incident_id,
                slack_sent=False,
                slack_channel=channel,
                slack_error=result.get("error", "Unknown error"),
                message_preview=message_preview
            )

    except Exception as e:
        logger.error(f"❌ Failed to send Slack message: {e}")
        return ApprovalTestResponse(
            incident_id=request.incident_id,
            slack_sent=False,
            slack_channel=channel,
            slack_error=str(e),
            message_preview=message_preview
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION MODULE TEST
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/execution",
    response_model=ExecutionTestResponse,
    summary="Test Execution Module",
    description="""
    Test the Execution module with action simulation.

    This simulates:
    - Validating actions
    - Executing each action sequentially
    - Recording results
    - Generating execution summary

    Set `dry_run=True` (default) to simulate without making real changes.

    **Note**: Does not execute real Kubernetes commands.
    """
)
async def test_execution(request: ExecutionTestRequest) -> ExecutionTestResponse:
    """Test the Execution module with simulated action execution."""

    execution_results = []
    skipped_actions = []
    failed_action = None
    all_succeeded = True

    for action in request.actions:
        result = get_dummy_execution_result(action, request.dry_run)

        if result["success"]:
            execution_results.append(result)
        else:
            execution_results.append(result)
            failed_action = result
            all_succeeded = False

            if request.stop_on_failure:
                # Skip remaining actions
                remaining_idx = request.actions.index(action) + 1
                skipped_actions = [
                    {"action": a, "reason": "Skipped due to previous failure"}
                    for a in request.actions[remaining_idx:]
                ]
                break

    # Generate summary
    total = len(request.actions)
    executed = len(execution_results)
    skipped = len(skipped_actions)
    succeeded = len([r for r in execution_results if r["success"]])
    failed = len([r for r in execution_results if not r["success"]])

    if request.dry_run:
        execution_summary = f"[DRY RUN] Simulated {executed}/{total} actions. All would succeed."
    elif all_succeeded:
        execution_summary = f"Successfully executed {succeeded}/{total} actions."
    else:
        execution_summary = f"Executed {executed}/{total} actions. {succeeded} succeeded, {failed} failed, {skipped} skipped."

    return ExecutionTestResponse(
        incident_id=request.incident_id,
        dry_run=request.dry_run,
        execution_results=execution_results,
        skipped_actions=skipped_actions,
        all_succeeded=all_succeeded,
        failed_action=failed_action,
        execution_summary=execution_summary
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FULL PIPELINE TEST
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/full-pipeline",
    response_model=FullPipelineTestResponse,
    summary="Test Full Incident Pipeline",
    description="""
    Test the complete incident handling pipeline:

    1. **Monitor** - Collect metrics, logs, events
    2. **Analyzer** - Detect patterns, identify root cause
    3. **Approval** - Send to Slack (if configured) or simulate
    4. **Execution** - Execute recommended actions (simulated)

    Set `send_to_slack=True` to send real Slack message.
    """
)
async def test_full_pipeline(request: FullPipelineTestRequest) -> FullPipelineTestResponse:
    """Test the complete incident pipeline with all modules."""

    start_time = time.time()
    incident_id = f"INC-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    stages_completed = []

    # Stage 1: Monitor
    monitor_request = MonitorTestRequest(
        service=request.service,
        namespace=request.namespace,
        time_range="15m"
    )
    monitor_result = await test_monitor(monitor_request)
    stages_completed.append("monitor")

    # Stage 2: Analyzer
    analyzer_request = AnalyzerTestRequest(
        alert_name=request.alert_name,
        severity=request.severity,
        service=request.service,
        use_llm=False
    )
    analyzer_result = await test_analyzer(analyzer_request)
    stages_completed.append("analyzer")

    # Stage 3: Approval (send to Slack or preview)
    approval_request = ApprovalTestRequest(
        incident_id=incident_id,
        severity=request.severity,
        root_cause=analyzer_result.root_cause,
        confidence=analyzer_result.confidence,
        recommended_actions=analyzer_result.recommended_actions,
        evidence=analyzer_result.evidence,
        send_to_slack=False  # Don't send in full pipeline by default
    )
    approval_result = await test_approval(approval_request)
    stages_completed.append("approval")

    # Stage 4: Execution (always execute in pipeline if auto_approve)
    if request.auto_approve:
        execution_request = ExecutionTestRequest(
            incident_id=incident_id,
            actions=analyzer_result.recommended_actions,
            dry_run=request.dry_run,
            stop_on_failure=True
        )
        execution_result = await test_execution(execution_request)
        stages_completed.append("execution")
    else:
        execution_result = ExecutionTestResponse(
            incident_id=incident_id,
            dry_run=request.dry_run,
            execution_results=[],
            skipped_actions=analyzer_result.recommended_actions,
            all_succeeded=False,
            execution_summary="Execution skipped - auto_approve=False"
        )

    total_duration_ms = (time.time() - start_time) * 1000

    return FullPipelineTestResponse(
        incident_id=incident_id,
        stages_completed=stages_completed,
        monitor_summary=monitor_result.health_summary,
        analyzer_result={
            "root_cause": analyzer_result.root_cause,
            "confidence": analyzer_result.confidence,
            "patterns_count": len(analyzer_result.patterns_detected),
            "actions_count": len(analyzer_result.recommended_actions),
            "requires_approval": analyzer_result.requires_approval
        },
        approval_result={
            "slack_sent": approval_result.slack_sent,
            "slack_channel": approval_result.slack_channel,
            "message_preview": approval_result.message_preview[:200] + "..."
        },
        execution_result={
            "dry_run": execution_result.dry_run,
            "all_succeeded": execution_result.all_succeeded,
            "executed_count": len(execution_result.execution_results),
            "skipped_count": len(execution_result.skipped_actions),
            "summary": execution_result.execution_summary
        },
        total_duration_ms=round(total_duration_ms, 2)
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SIMPLE SLACK TEST
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/slack/simple",
    summary="Send Simple Test Message to Slack",
    description="""
    Send a simple test message to verify Slack integration is working.

    This sends a basic message to your configured Slack channel.
    Use this to quickly verify your SLACK_BOT_TOKEN and channel are correct.
    """
)
async def test_slack_simple(
    message: str = "🧪 Test message from DevOps Agent API",
    channel: str = None
):
    """Send a simple test message to Slack."""

    if not settings.SLACK_BOT_TOKEN:
        return {
            "success": False,
            "error": "SLACK_BOT_TOKEN not configured in .env",
            "hint": "Add SLACK_BOT_TOKEN=xoxb-your-token to your .env file"
        }

    target_channel = channel or settings.SLACK_DEFAULT_CHANNEL

    try:
        from slack_sdk import WebClient
        client = WebClient(token=settings.SLACK_BOT_TOKEN)

        response = client.chat_postMessage(
            channel=target_channel,
            text=message,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*DevOps Agent Test*\n{message}"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Sent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        }
                    ]
                }
            ]
        )

        return {
            "success": True,
            "channel": response["channel"],
            "message_ts": response["ts"],
            "message": message
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "channel": target_channel
        }


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/health",
    summary="Test Routes Health Check",
    description="Verify test routes are working"
)
async def test_health():
    """Simple health check for test routes."""

    slack_configured = bool(settings.SLACK_BOT_TOKEN)

    return {
        "status": "healthy",
        "module": "test_routes",
        "timestamp": datetime.utcnow().isoformat(),
        "config": {
            "slack_configured": slack_configured,
            "slack_channel": settings.SLACK_DEFAULT_CHANNEL if slack_configured else None,
        },
        "available_endpoints": [
            "/test/monitor - Test monitoring data collection",
            "/test/analyzer - Test pattern detection & analysis",
            "/test/approval - Send approval request to Slack",
            "/test/execution - Test action execution",
            "/test/full-pipeline - Test complete flow",
            "/test/slack/simple - Quick Slack connectivity test"
        ]
    }
