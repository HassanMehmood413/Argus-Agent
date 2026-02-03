import logging
from typing import Dict, List, Any, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


class SlackClient:
    """
    Slack client for sending approval requests.

    This client:
    - Sends formatted approval messages to Slack
    - Uses Block Kit for rich, interactive messages
    - Supports threading for context

    NOTE: Button interactions require a separate Slack app
    with interactivity enabled that sends webhooks to your API.
    """

    def __init__(self, token: str, default_channel: str = "#incidents"):
        """
        Initialize Slack client.

        Args:
            token: Slack Bot OAuth token (xoxb-...)
            default_channel: Default channel for approval messages
        """
        self.client = WebClient(token=token)
        self.default_channel = default_channel

    def format_approval_message(
        self,
        incident_id: str,
        severity: str,
        root_cause: str,
        confidence: float,
        evidence: List[str],
        recommended_actions: List[Dict[str, Any]],
        similar_incidents: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Format an approval request as Slack Block Kit blocks.

        WHY BLOCK KIT?
        - Rich formatting (colors, sections, buttons)
        - Interactive components (approve/reject buttons)
        - Better UX than plain text

        Args:
            incident_id: Unique identifier for the incident
            severity: Incident severity (low, medium, high, critical)
            root_cause: Identified root cause
            confidence: Confidence score (0-1)
            evidence: List of evidence points
            recommended_actions: Actions to approve
            similar_incidents: Past similar incidents for context

        Returns:
            List of Slack Block Kit blocks
        """
        # Severity color coding for visual urgency
        severity_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴"
        }
        emoji = severity_emoji.get(severity.lower(), "⚪")

        # Build the blocks
        blocks = [
            # Header
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Incident Approval Required",
                    "emoji": True
                }
            },
            # Incident ID and severity
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Incident ID:*\n`{incident_id}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Severity:*\n{severity.upper()}"
                    }
                ]
            },
            {"type": "divider"},
            # Root cause analysis
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔍 Root Cause Analysis*\n{root_cause}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Confidence: *{confidence*100:.0f}%*"
                    }
                ]
            },
        ]

        # Evidence section
        if evidence:
            evidence_text = "\n".join([f"• {e}" for e in evidence[:5]])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📋 Evidence*\n{evidence_text}"
                }
            })

        blocks.append({"type": "divider"})

        # Recommended actions
        if recommended_actions:
            actions_text = []
            for i, action in enumerate(recommended_actions, 1):
                action_type = action.get("type", "unknown")
                description = action.get("description", "No description")
                risk = action.get("risk_level", "unknown")
                risk_emoji = {"none": "🟢", "low": "🟡", "medium": "🟠", "high": "🔴"}.get(risk, "⚪")
                actions_text.append(
                    f"{i}. *{action_type}* {risk_emoji}\n   {description}"
                )

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🎯 Recommended Actions*\n" + "\n".join(actions_text)
                }
            })

        # Similar incidents (if any)
        if similar_incidents:
            similar_text = "\n".join([
                f"• `{inc.get('id', 'N/A')}` - {inc.get('title', 'Unknown')} (Similarity: {inc.get('similarity', 0)*100:.0f}%)"
                for inc in similar_incidents[:3]
            ])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📚 Similar Past Incidents*\n{similar_text}"
                }
            })

        blocks.append({"type": "divider"})

        # Action buttons
        # NOTE: The action_id values are used by the Slack app to route
        # the interaction to the correct handler
        blocks.append({
            "type": "actions",
            "block_id": f"approval_actions_{incident_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ Approve",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "approve_incident",
                    "value": incident_id
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ Reject",
                        "emoji": True
                    },
                    "style": "danger",
                    "action_id": "reject_incident",
                    "value": incident_id
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✏️ Modify Actions",
                        "emoji": True
                    },
                    "action_id": "modify_incident",
                    "value": incident_id
                }
            ]
        })

        return blocks

    async def send_approval_request(
        self,
        incident_id: str,
        severity: str,
        root_cause: str,
        confidence: float,
        evidence: List[str],
        recommended_actions: List[Dict[str, Any]],
        similar_incidents: Optional[List[Dict[str, Any]]] = None,
        channel: Optional[str] = None,
        thread_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an approval request to Slack.

        This posts a rich message with approve/reject buttons.

        Args:
            incident_id: Unique identifier for the incident
            severity: Incident severity
            root_cause: Identified root cause
            confidence: Confidence score (0-1)
            evidence: List of evidence points
            recommended_actions: Actions to approve
            similar_incidents: Past similar incidents
            channel: Slack channel (defaults to self.default_channel)
            thread_ts: Thread timestamp for replies (optional)

        Returns:
            Dict with 'ok', 'ts' (message timestamp), and 'channel'
        """
        channel = channel or self.default_channel

        # Format the message blocks
        blocks = self.format_approval_message(
            incident_id=incident_id,
            severity=severity,
            root_cause=root_cause,
            confidence=confidence,
            evidence=evidence,
            recommended_actions=recommended_actions,
            similar_incidents=similar_incidents,
        )

        # Fallback text for notifications
        fallback_text = (
            f"🚨 Approval Required for Incident {incident_id}\n"
            f"Severity: {severity.upper()}\n"
            f"Root Cause: {root_cause[:100]}..."
        )

        try:
            response = self.client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=fallback_text,  # Shown in notifications
                thread_ts=thread_ts,  # Reply in thread if specified
            )

            logger.info(
                f"[Slack] Approval request sent for {incident_id} "
                f"to {channel}, ts={response['ts']}"
            )

            return {
                "ok": True,
                "ts": response["ts"],
                "channel": response["channel"],
            }

        except SlackApiError as e:
            logger.error(f"[Slack] Error sending approval: {e.response['error']}")
            return {
                "ok": False,
                "error": str(e.response["error"]),
            }

    async def update_approval_message(
        self,
        channel: str,
        message_ts: str,
        decision: str,
        decided_by: str,
        decided_by_name: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update the approval message after a decision is made.

        This replaces the buttons with the decision outcome.

        WHY UPDATE?
        - Shows everyone the decision was made
        - Prevents duplicate approvals
        - Provides audit trail

        Args:
            channel: Slack channel ID
            message_ts: Original message timestamp
            decision: "approved" or "rejected"
            decided_by: User ID who made the decision
            decided_by_name: Human-readable name
            reason: Optional reason (especially for rejection)

        Returns:
            Dict with 'ok' and error info if failed
        """
        emoji = "✅" if decision == "approved" else "❌"
        status = "APPROVED" if decision == "approved" else "REJECTED"

        # Build updated blocks
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{emoji} *Incident {status}*\n\n"
                        f"*Decided by:* {decided_by_name or decided_by}\n"
                        f"*Time:* <!date^{int(__import__('time').time())}^{{date_short}} {{time}}|now>"
                    )
                }
            }
        ]

        if reason:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Reason:* {reason}"
                }
            })

        try:
            response = self.client.chat_update(
                channel=channel,
                ts=message_ts,
                blocks=blocks,
                text=f"Incident {status} by {decided_by_name or decided_by}",
            )

            return {"ok": True}

        except SlackApiError as e:
            logger.error(f"[Slack] Error updating message: {e.response['error']}")
            return {"ok": False, "error": str(e.response["error"])}
