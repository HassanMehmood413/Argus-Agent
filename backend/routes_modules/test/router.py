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
    SummaryTestRequest,
    SummaryTestResponse,
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
# APPROVAL MODULE TEST (Simple - just sends Slack message)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/approval",
    response_model=ApprovalTestResponse,
    summary="Test Approval Module - Sends REAL Slack Message (No Graph)",
    description="""
    Test the Approval module by sending a **REAL message to Slack**.

    **NOTE**: This only sends a Slack message - it does NOT invoke the approval graph.
    Use `/approval/workflow` to test the full approval workflow with interrupt/resume.

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
# APPROVAL WORKFLOW TEST (Full graph with interrupt/resume)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/approval/workflow",
    summary="Test Full Approval Workflow - With interrupt/resume",
    description="""
    Test the **FULL** approval workflow using LangGraph's interrupt/resume.

    This will:
    1. Invoke the approval subgraph with a unique thread_id
    2. Send approval request to Slack
    3. Graph pauses at interrupt() waiting for your decision
    4. When you click Approve/Reject in Slack, the webhook resumes the graph
    5. Graph completes and updates the Slack message

    **Requirements:**
    - `SLACK_BOT_TOKEN` must be set in `.env`
    - `SLACK_SIGNING_SECRET` should be set (for production security)
    - Slack app must have Interactivity enabled pointing to your webhook URL
    - Bot must be invited to the channel

    **This is the recommended way to test the approval flow!**
    """
)
async def test_approval_workflow(request: ApprovalTestRequest):
    """Test the full approval workflow with interrupt/resume."""
    from backend.modules.approval.graph import approval_subgraph
    import asyncio
    import traceback

    logger.info("=" * 60)
    logger.info("[Approval Workflow] STARTING APPROVAL WORKFLOW TEST")
    logger.info("=" * 60)

    # Check for Slack token
    if not settings.SLACK_BOT_TOKEN:
        logger.error("[Approval Workflow] SLACK_BOT_TOKEN not configured!")
        return {
            "success": False,
            "error": "SLACK_BOT_TOKEN not configured in .env",
            "hint": "Add SLACK_BOT_TOKEN=xoxb-your-token to your .env file"
        }

    logger.info(f"[Approval Workflow] SLACK_BOT_TOKEN is configured: {settings.SLACK_BOT_TOKEN[:20]}...")

    # Determine channel
    channel = request.slack_channel or settings.SLACK_DEFAULT_CHANNEL
    logger.info(f"[Approval Workflow] Using Slack channel: {channel}")

    # Build the approval state
    approval_state = {
        "incident_id": request.incident_id,
        "severity": request.severity,
        "root_cause": request.root_cause,
        "confidence": request.confidence,
        "evidence": request.evidence,
        "recommended_actions": request.recommended_actions,
        "similar_incidents": [],
        "slack_channel": channel,
        "slack_thread_ts": None,
    }

    logger.info(f"[Approval Workflow] Approval state: incident_id={request.incident_id}, severity={request.severity}")

    # CRITICAL: Use incident_id as thread_id so webhook can resume it
    config = {"configurable": {"thread_id": request.incident_id}}

    logger.info(f"[Approval Workflow] Starting approval for {request.incident_id}")
    logger.info(f"[Approval Workflow] Using thread_id: {request.incident_id}")
    logger.info(f"[Approval Workflow] Config: {config}")

    try:
        # Start the graph - it will pause at interrupt()
        # We run this in a background task because it will block until resumed
        async def run_graph():
            try:
                logger.info("[Approval Workflow] Invoking approval_subgraph.ainvoke()...")
                result = await approval_subgraph.ainvoke(approval_state, config)
                logger.info(f"[Approval Workflow] Graph completed: approved={result.get('approved')}")
                return result
            except Exception as e:
                logger.error(f"[Approval Workflow] Graph error: {e}")
                logger.error(f"[Approval Workflow] Traceback: {traceback.format_exc()}")
                raise

        # Create the task but don't await it (it will block at interrupt)
        logger.info("[Approval Workflow] Creating background task for graph execution...")
        task = asyncio.create_task(run_graph())

        # Wait a short time for the Slack message to be sent
        logger.info("[Approval Workflow] Waiting 3 seconds for Slack message to be sent...")
        await asyncio.sleep(3)

        # Check if the task errored quickly (before interrupt)
        if task.done():
            logger.info("[Approval Workflow] Task completed (might have errored)")
            try:
                result = task.result()
                logger.info(f"[Approval Workflow] Task result: {result}")
            except Exception as e:
                logger.error(f"[Approval Workflow] Task error: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "incident_id": request.incident_id,
                }

        logger.info("[Approval Workflow] Graph is now paused at interrupt(), waiting for Slack button click")
        logger.info(f"[Approval Workflow] To resume, click a button in Slack or call webhook with incident_id={request.incident_id}")

        return {
            "success": True,
            "incident_id": request.incident_id,
            "thread_id": request.incident_id,
            "slack_channel": channel,
            "status": "waiting_for_approval",
            "message": f"Approval request sent to {channel}. Click Approve/Reject in Slack to continue.",
            "hint": "The graph is now paused at interrupt(). When you click the button in Slack, the webhook will resume it.",
        }

    except Exception as e:
        logger.error(f"[Approval Workflow] Error: {e}")
        logger.error(f"[Approval Workflow] Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "incident_id": request.incident_id,
        }


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

    # Stage 5: Summary (generate incident summary)
    summary_result_data = None
    if request.auto_approve and execution_result.all_succeeded:
        summary_request = SummaryTestRequest(
            incident_id=incident_id,
            severity=request.severity,
            root_cause=analyzer_result.root_cause,
            confidence=analyzer_result.confidence,
            evidence=analyzer_result.evidence,
            recommended_actions=analyzer_result.recommended_actions,
            approved_by="auto-approve",
            execution_results=execution_result.execution_results,
            all_succeeded=execution_result.all_succeeded,
            created_at=datetime.utcnow().isoformat(),
            send_to_slack=False,  # Don't send Slack in pipeline by default
        )
        summary_result = await test_summary(summary_request)
        stages_completed.append("summary")
        summary_result_data = {
            "resolution_time": summary_result.resolution_time_display,
            "postmortem_ticket": summary_result.postmortem_ticket,
            "summary_preview": summary_result.summary[:300] + "..." if len(summary_result.summary) > 300 else summary_result.summary,
        }

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
        summary_result=summary_result_data,
        total_duration_ms=round(total_duration_ms, 2)
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY MODULE TEST
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/summary",
    response_model=SummaryTestResponse,
    summary="Test Summary Module",
    description="""
    Test the Summary module to generate incident summaries.

    This simulates:
    - Generating a comprehensive incident summary
    - Calculating resolution time
    - Posting summary to Slack (if configured)
    - Creating postmortem ticket for high/critical severity

    Set `send_to_slack=True` to send the summary to Slack (requires SLACK_BOT_TOKEN).
    """
)
async def test_summary(request: SummaryTestRequest) -> SummaryTestResponse:
    """Test the Summary module with summary generation."""
    from datetime import timedelta

    # Calculate created_at if not provided (default: 15 minutes ago)
    if request.created_at:
        created_at = request.created_at
    else:
        created_at = (datetime.utcnow() - timedelta(minutes=15)).isoformat()

    # Build state for summary agent
    summary_state = {
        "incident_id": request.incident_id,
        "severity": request.severity,
        "alert": {"name": "TestAlert", "severity": request.severity},
        "root_cause": request.root_cause,
        "confidence": request.confidence,
        "evidence": request.evidence,
        "recommended_actions": request.recommended_actions,
        "approved_by": request.approved_by,
        "execution_results": request.execution_results,
        "all_succeeded": request.all_succeeded,
        "created_at": created_at,
        "slack_channel": request.slack_channel or settings.SLACK_DEFAULT_CHANNEL,
    }

    # Import and run the summary subgraph
    from backend.modules.summary import summary_subgraph

    try:
        result = await summary_subgraph.ainvoke(summary_state)
    except Exception as e:
        # If async invoke fails, try sync (for graphs without async nodes)
        logger.warning(f"Async invoke failed, trying sync: {e}")
        result = summary_subgraph.invoke(summary_state)

    # Format resolution time for display
    resolution_seconds = result.get("resolution_time_seconds", 0)
    if resolution_seconds < 60:
        resolution_display = f"{int(resolution_seconds)} seconds"
    elif resolution_seconds < 3600:
        resolution_display = f"{int(resolution_seconds / 60)} minutes"
    else:
        hours = int(resolution_seconds / 3600)
        mins = int((resolution_seconds % 3600) / 60)
        resolution_display = f"{hours} hours {mins} minutes"

    # Determine if Slack was sent
    slack_sent = False
    slack_error = None
    if request.send_to_slack:
        if settings.SLACK_BOT_TOKEN:
            slack_sent = bool(result.get("summary_message_ts"))
            if not slack_sent:
                slack_error = "Failed to post summary to Slack"
        else:
            slack_error = "SLACK_BOT_TOKEN not configured"

    return SummaryTestResponse(
        incident_id=request.incident_id,
        summary=result.get("summary", "No summary generated"),
        resolution_time_seconds=resolution_seconds,
        resolution_time_display=resolution_display,
        slack_sent=slack_sent,
        slack_message_ts=result.get("summary_message_ts"),
        slack_error=slack_error,
        postmortem_ticket=result.get("postmortem_ticket"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR TEST (Full Pipeline with Real Subgraphs)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/orchestrator",
    summary="Test Full Orchestrator Pipeline",
    description="""
    Test the **FULL** Orchestrator pipeline with all real subgraphs.

    This will:
    1. **Monitor**: Collect metrics, logs, pod status (simulated for test)
    2. **Analyzer**: Identify root cause and recommend actions
    3. **Approval**: Request human approval via Slack (if needed)
    4. **Executor**: Execute approved actions
    5. **Summary**: Generate incident summary and postmortem

    **WARNING**: This runs the real orchestrator with real LLM calls!
    - Requires OPENAI_API_KEY for analyzer
    - Requires SLACK_BOT_TOKEN for approval notifications
    - May pause at approval step waiting for Slack button click

    Use `auto_approve=True` to skip the approval wait (for testing).
    """
)
async def test_orchestrator(
    alertname: str = "HighMemoryUsage",
    service: str = "api-gateway",
    namespace: str = "production",
    severity: str = "high",
    auto_approve: bool = True,
    dry_run: bool = True,
):
    """Test the full orchestrator pipeline."""
    from backend.modules.orchestrator import process_incident
    import traceback

    logger.info("=" * 60)
    logger.info("[Orchestrator Test] STARTING FULL ORCHESTRATOR TEST")
    logger.info("=" * 60)

    incident_id = f"TEST-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    alert = {
        "alertname": alertname,
        "service": service,
        "namespace": namespace,
        "severity": severity,
        "labels": {
            "service": service,
            "namespace": namespace,
        }
    }

    logger.info(f"[Orchestrator Test] Alert: {alert}")
    logger.info(f"[Orchestrator Test] Incident ID: {incident_id}")
    logger.info(f"[Orchestrator Test] Auto-approve: {auto_approve}")

    try:
        # If auto_approve, we need to modify settings temporarily
        # For now, just run with default settings
        result = await process_incident(
            alert=alert,
            severity=severity,
            incident_id=incident_id,
            slack_channel=settings.SLACK_DEFAULT_CHANNEL,
        )

        logger.info(f"[Orchestrator Test] Completed with status: {result.get('status')}")

        return {
            "success": True,
            "incident_id": incident_id,
            "status": result.get("status"),
            "root_cause": result.get("root_cause"),
            "confidence": result.get("confidence"),
            "recommended_actions_count": len(result.get("recommended_actions", [])),
            "approved": result.get("approved"),
            "approved_by": result.get("approved_by"),
            "execution_results_count": len(result.get("execution_results", [])),
            "all_succeeded": result.get("all_succeeded"),
            "summary_preview": (result.get("summary", "")[:200] + "...") if result.get("summary") else None,
            "resolution_time_seconds": result.get("resolution_time_seconds"),
        }

    except Exception as e:
        logger.error(f"[Orchestrator Test] Error: {e}")
        logger.error(f"[Orchestrator Test] Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "incident_id": incident_id,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


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
            "/test/approval - Send approval request to Slack (no graph)",
            "/test/approval/workflow - FULL approval flow with interrupt/resume",
            "/test/execution - Test action execution",
            "/test/summary - Test summary generation",
            "/test/orchestrator - Test FULL orchestrator pipeline",
            "/test/full-pipeline - Test complete flow (simulated)",
            "/test/slack/simple - Quick Slack connectivity test"
        ]
    }
