"""
Summary Agent Nodes

Implements the nodes for the Summary subgraph:
1. generate_summary_node - Create comprehensive incident summary
2. post_to_slack_node - Post summary to Slack thread
3. create_postmortem_node - Create postmortem ticket (Jira/etc)
"""

import logging
from typing import Dict, Any
from datetime import datetime

from backend.modules.summary.state import SummaryState
from backend.modules.summary.clients.slack import SummarySlackClient
from backend.config.settings import settings
from backend.modules.summary.clients.jira import JiraClient

logger = logging.getLogger(__name__)


def generate_summary_node(state: SummaryState) -> Dict[str, Any]:
    """
    Node 1: Generate comprehensive incident summary.

    WHY THIS NODE?
    - Creates a human-readable summary of the entire incident
    - Calculates resolution time from incident creation to now
    - Formats all relevant data for stakeholders

    Reads: incident_id, severity, alert, root_cause, confidence, evidence,
           recommended_actions, approved_by, execution_results, all_succeeded, created_at
    Writes: summary, resolution_time_seconds

    Args:
        state: Current summary state with all incident data

    Returns:
        Dict with summary text and resolution time
    """
    incident_id = state.get("incident_id", "unknown")
    logger.info(f"[Summary] Generating summary for incident {incident_id}")

    # Calculate resolution time
    created_at_str = state.get("created_at")
    resolution_time_seconds = 0.0

    if created_at_str:
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            now = datetime.now(created_at.tzinfo) if created_at.tzinfo else datetime.utcnow()
            resolution_time_seconds = (now - created_at).total_seconds()
        except (ValueError, TypeError) as e:
            logger.warning(f"[Summary] Could not parse created_at: {e}")

    # Format resolution time for display
    resolution_time_display = _format_duration(resolution_time_seconds)

    # Determine overall status
    all_succeeded = state.get("all_succeeded", False)
    status_emoji = "✅" if all_succeeded else "⚠️"
    status_text = "RESOLVED" if all_succeeded else "PARTIALLY RESOLVED"

    # Build execution results summary
    execution_results = state.get("execution_results", [])
    actions_summary = _format_actions_summary(execution_results)

    # Build the summary text
    summary = f"""
══════════════════════════════════════════════════════════════
{status_emoji} INCIDENT {status_text}: {incident_id}
══════════════════════════════════════════════════════════════

📊 Severity: {state.get('severity', 'unknown').upper()}
⏱️ Duration: {resolution_time_display}

🔍 Root Cause:
{state.get('root_cause', 'Unknown root cause')}

📈 Confidence: {state.get('confidence', 0) * 100:.0f}%

📋 Evidence:
{_format_evidence(state.get('evidence', []))}

🎯 Actions Taken:
{actions_summary}

👤 Approved by: {state.get('approved_by', 'N/A')}

══════════════════════════════════════════════════════════════
""".strip()

    logger.info(
        f"[Summary] Generated summary for {incident_id}, "
        f"resolution time: {resolution_time_display}"
    )

    return {
        "summary": summary,
        "resolution_time_seconds": resolution_time_seconds,
    }


async def post_to_slack_node(state: SummaryState) -> Dict[str, Any]:
    """
    Node 2: Post summary to Slack.

    WHY ASYNC?
    - Slack API calls are I/O bound
    - Non-blocking for better performance

    Posts the generated summary to the incident's Slack thread.

    Reads: summary, slack_channel, slack_thread_ts, incident_id, all_succeeded
    Writes: summary_message_ts

    Args:
        state: Current summary state with generated summary

    Returns:
        Dict with Slack message timestamp
    """
    incident_id = state.get("incident_id", "unknown")
    logger.info(f"[Summary] Posting summary to Slack for incident {incident_id}")

    slack_token = getattr(settings, "SLACK_BOT_TOKEN", None)
    channel = state.get("slack_channel", settings.SLACK_DEFAULT_CHANNEL)
    thread_ts = state.get("slack_thread_ts")

    if not slack_token:
        logger.warning("[Summary] No SLACK_BOT_TOKEN configured - simulating post")
        return {
            "summary_message_ts": f"simulated_{datetime.utcnow().timestamp()}",
        }

    # Create Slack client and post summary
    slack = SummarySlackClient(token=slack_token)

    result = await slack.post_summary(
        incident_id=incident_id,
        summary=state.get("summary", "No summary available"),
        all_succeeded=state.get("all_succeeded", False),
        resolution_time_seconds=state.get("resolution_time_seconds", 0),
        channel=channel,
        thread_ts=thread_ts,
    )

    if result.get("ok"):
        logger.info(f"[Summary] Summary posted to Slack: ts={result.get('ts')}")
        return {"summary_message_ts": result.get("ts")}
    else:
        logger.error(f"[Summary] Failed to post summary: {result.get('error')}")
        return {}


async def create_postmortem_node(state: SummaryState) -> Dict[str, Any]:
    """
    Node 3: Create postmortem ticket.

    WHY THIS NODE?
    - Creates a Jira/ticketing system ticket for postmortem review
    - Ensures incidents are documented for future reference
    - Enables organizational learning from incidents

    PRODUCTION SETUP:
    Configure these in .env for real Jira integration:
    - JIRA_URL=https://company.atlassian.net
    - JIRA_EMAIL=user@company.com
    - JIRA_API_TOKEN=your-api-token
    - JIRA_PROJECT_KEY=POST
    - JIRA_POSTMORTEM_ISSUE_TYPE=Task

    Reads: incident_id, summary, severity, root_cause, evidence, execution_results,
           resolution_time_seconds, slack_channel, slack_thread_ts
    Writes: postmortem_ticket

    Args:
        state: Current summary state

    Returns:
        Dict with postmortem ticket ID (if created)
    """
    incident_id = state.get("incident_id", "unknown")
    severity = state.get("severity", "unknown")

    logger.info(f"[Summary] Creating postmortem ticket for incident {incident_id}")

    # Only create postmortem for high/critical severity incidents
    if severity.lower() not in ["high", "critical"]:
        logger.info(
            f"[Summary] Skipping postmortem for {severity} severity incident"
        )
        return {"postmortem_ticket": None}

    # Check if Jira is configured
    if settings.JIRA_CONFIGURED:
        # Use real Jira integration
        return await _create_jira_postmortem(state)
    else:
        # Fallback to mock ticket
        logger.warning("[Summary] Jira not configured - generating mock ticket ID")
        postmortem_ticket = f"POST-{incident_id[:8].upper()}"
        logger.info(f"[Summary] Created mock postmortem ticket: {postmortem_ticket}")
        return {"postmortem_ticket": postmortem_ticket}


async def _create_jira_postmortem(state: SummaryState) -> Dict[str, Any]:
    """
    Create a real Jira postmortem ticket.

    Args:
        state: Summary state with all incident data

    Returns:
        Dict with postmortem_ticket key or None
    """

    incident_id = state.get("incident_id", "unknown")

    # Build Slack thread URL if we have the info
    slack_thread_url = None
    slack_channel = state.get("slack_channel")
    slack_thread_ts = state.get("slack_thread_ts")
    if slack_channel and slack_thread_ts:
        # Format: https://workspace.slack.com/archives/CHANNEL/pTIMESTAMP
        # Note: This is a simplified URL - real implementation would need workspace info
        slack_thread_url = f"slack://channel?team=&id={slack_channel}&message={slack_thread_ts}"

    try:
        jira = JiraClient(
            url=settings.JIRA_URL,
            email=settings.JIRA_EMAIL,
            api_token=settings.JIRA_API_TOKEN,
            project_key=settings.JIRA_PROJECT_KEY,
            issue_type=settings.JIRA_POSTMORTEM_ISSUE_TYPE,
        )

        result = await jira.create_postmortem_ticket(
            incident_id=incident_id,
            severity=state.get("severity", "unknown"),
            summary_text=state.get("summary", ""),
            root_cause=state.get("root_cause", "Unknown"),
            evidence=state.get("evidence", []),
            execution_results=state.get("execution_results", []),
            resolution_time_seconds=state.get("resolution_time_seconds", 0),
            slack_thread_url=slack_thread_url,
            labels=["postmortem", "incident", state.get("severity", "unknown").lower()],
        )

        await jira.close()

        if result.get("ok"):
            ticket_key = result.get("key")
            ticket_url = result.get("url")
            logger.info(f"[Summary] Created Jira postmortem: {ticket_key} ({ticket_url})")

            # Optionally post ticket link back to Slack
            await _notify_slack_postmortem(state, ticket_key, ticket_url)

            return {"postmortem_ticket": ticket_key}
        else:
            logger.error(f"[Summary] Failed to create Jira ticket: {result.get('error')}")
            # Fallback to mock
            return {"postmortem_ticket": f"MOCK-{incident_id[:8].upper()}"}

    except Exception as e:
        logger.error(f"[Summary] Jira integration error: {e}")
        return {"postmortem_ticket": f"ERROR-{incident_id[:8].upper()}"}


async def _notify_slack_postmortem(
    state: SummaryState,
    ticket_key: str,
    ticket_url: str,
) -> None:
    """
    Post postmortem ticket link to Slack thread.

    Args:
        state: Summary state with Slack info
        ticket_key: Jira ticket key
        ticket_url: URL to the Jira ticket
    """
    slack_token = getattr(settings, "SLACK_BOT_TOKEN", None)
    if not slack_token:
        return

    channel = state.get("slack_channel")
    thread_ts = state.get("slack_thread_ts")
    if not channel:
        return

    try:
        slack = SummarySlackClient(token=slack_token)
        await slack.post_postmortem_link(
            incident_id=state.get("incident_id", "unknown"),
            ticket_id=ticket_key,
            ticket_url=ticket_url,
            channel=channel,
            thread_ts=thread_ts,
        )
    except Exception as e:
        logger.warning(f"[Summary] Failed to post postmortem link to Slack: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def _format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "12 minutes", "1 hour 30 minutes")
    """
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        parts = [f"{hours} hour{'s' if hours != 1 else ''}"]
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        return " ".join(parts)


def _format_evidence(evidence: list) -> str:
    """
    Format evidence list for summary.

    Args:
        evidence: List of evidence strings

    Returns:
        Formatted evidence string
    """
    if not evidence:
        return "  No evidence collected"

    return "\n".join([f"  • {e}" for e in evidence[:10]])


def _format_actions_summary(execution_results: list) -> str:
    """
    Format execution results for summary.

    Args:
        execution_results: List of execution result dicts

    Returns:
        Formatted actions summary string
    """
    if not execution_results:
        return "  No actions executed"

    lines = []
    for i, result in enumerate(execution_results, 1):
        action_type = result.get("action", {}).get("type", "unknown")
        success = result.get("success", False)
        status_emoji = "✅" if success else "❌"

        description = result.get("action", {}).get("description", "No description")

        lines.append(f"  {i}. {status_emoji} {action_type}: {description}")

        # Add error message if failed
        if not success and result.get("error"):
            lines.append(f"      Error: {result.get('error')}")

    return "\n".join(lines)
