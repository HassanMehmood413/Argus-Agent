"""
Jira Client for Postmortem Tickets

Integrates with Jira to create postmortem tickets after incidents.

SETUP REQUIRED:
1. Create a Jira API token: https://id.atlassian.com/manage-profile/security/api-tokens
2. Add to .env:
   - JIRA_URL=https://your-company.atlassian.net
   - JIRA_EMAIL=your-email@company.com
   - JIRA_API_TOKEN=your-api-token
   - JIRA_PROJECT_KEY=POST (or your project key)
   - JIRA_POSTMORTEM_ISSUE_TYPE=Task (or custom issue type like "Postmortem")
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


class JiraClient:
    """
    Jira client for creating postmortem tickets.

    Uses Jira REST API v3 for cloud instances.
    For Jira Server/Data Center, use API v2.
    """

    def __init__(
        self,
        url: str,
        email: str,
        api_token: str,
        project_key: str = "POST",
        issue_type: str = "Task",
    ):
        """
        Initialize Jira client.

        Args:
            url: Jira instance URL (e.g., https://company.atlassian.net)
            email: Jira user email
            api_token: Jira API token
            project_key: Project key for postmortem tickets
            issue_type: Issue type name (e.g., "Task", "Postmortem")
        """
        self.url = url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.project_key = project_key
        self.issue_type = issue_type

        # Create async HTTP client with auth
        self.client = httpx.AsyncClient(
            base_url=f"{self.url}/rest/api/3",
            auth=(email, api_token),
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

    async def create_postmortem_ticket(
        self,
        incident_id: str,
        severity: str,
        summary_text: str,
        root_cause: str,
        evidence: List[str],
        execution_results: List[Dict[str, Any]],
        resolution_time_seconds: float,
        slack_thread_url: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a postmortem ticket in Jira.

        Args:
            incident_id: Unique incident identifier
            severity: Incident severity (low, medium, high, critical)
            summary_text: Full incident summary
            root_cause: Identified root cause
            evidence: List of evidence points
            execution_results: Actions taken and their results
            resolution_time_seconds: Time to resolve
            slack_thread_url: Link to Slack incident thread
            labels: Additional labels for the ticket
            assignee: Jira account ID to assign (optional)

        Returns:
            Dict with 'ok', 'key' (ticket key), 'url' (ticket URL)
        """
        # Format resolution time
        resolution_time = self._format_duration(resolution_time_seconds)

        # Build description using Atlassian Document Format (ADF)
        description = self._build_description_adf(
            incident_id=incident_id,
            severity=severity,
            root_cause=root_cause,
            evidence=evidence,
            execution_results=execution_results,
            resolution_time=resolution_time,
            slack_thread_url=slack_thread_url,
        )

        # Priority mapping
        priority_map = {
            "critical": "Highest",
            "high": "High",
            "medium": "Medium",
            "low": "Low",
        }
        priority_name = priority_map.get(severity.lower(), "Medium")

        # Build issue payload
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": f"[Postmortem] {incident_id}: {root_cause[:80]}",
                "description": description,
                "issuetype": {"name": self.issue_type},
                "priority": {"name": priority_name},
                "labels": labels or ["postmortem", "incident", severity.lower()],
            }
        }

        # Add assignee if provided
        if assignee:
            payload["fields"]["assignee"] = {"accountId": assignee}

        try:
            response = await self.client.post("/issue", json=payload)
            response.raise_for_status()

            data = response.json()
            ticket_key = data["key"]
            ticket_url = f"{self.url}/browse/{ticket_key}"

            logger.info(f"[Jira] Created postmortem ticket: {ticket_key}")

            return {
                "ok": True,
                "key": ticket_key,
                "url": ticket_url,
                "id": data["id"],
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"[Jira] HTTP error creating ticket: {e.response.text}")
            return {
                "ok": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}",
            }
        except Exception as e:
            logger.error(f"[Jira] Error creating ticket: {e}")
            return {
                "ok": False,
                "error": str(e),
            }

    async def add_comment(
        self,
        ticket_key: str,
        comment: str,
    ) -> Dict[str, Any]:
        """
        Add a comment to an existing ticket.

        Args:
            ticket_key: Jira ticket key (e.g., "POST-123")
            comment: Comment text

        Returns:
            Dict with result info
        """
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment}],
                    }
                ],
            }
        }

        try:
            response = await self.client.post(
                f"/issue/{ticket_key}/comment", json=payload
            )
            response.raise_for_status()

            return {"ok": True, "comment_id": response.json()["id"]}

        except Exception as e:
            logger.error(f"[Jira] Error adding comment: {e}")
            return {"ok": False, "error": str(e)}

    async def link_to_slack(
        self,
        ticket_key: str,
        slack_url: str,
        title: str = "Slack Incident Thread",
    ) -> Dict[str, Any]:
        """
        Add a remote link to the Slack thread.

        Args:
            ticket_key: Jira ticket key
            slack_url: URL to Slack thread
            title: Link title

        Returns:
            Dict with result info
        """
        payload = {
            "object": {
                "url": slack_url,
                "title": title,
                "icon": {
                    "url16x16": "https://slack.com/favicon.ico",
                },
            }
        }

        try:
            response = await self.client.post(
                f"/issue/{ticket_key}/remotelink", json=payload
            )
            response.raise_for_status()

            return {"ok": True}

        except Exception as e:
            logger.error(f"[Jira] Error adding remote link: {e}")
            return {"ok": False, "error": str(e)}

    def _build_description_adf(
        self,
        incident_id: str,
        severity: str,
        root_cause: str,
        evidence: List[str],
        execution_results: List[Dict[str, Any]],
        resolution_time: str,
        slack_thread_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build Atlassian Document Format (ADF) description.

        ADF is required for Jira Cloud API v3.
        """
        content = []

        # Header panel
        content.append({
            "type": "panel",
            "attrs": {"panelType": "info"},
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": f"Incident ID: ", "marks": [{"type": "strong"}]},
                        {"type": "text", "text": incident_id},
                        {"type": "text", "text": " | "},
                        {"type": "text", "text": f"Severity: ", "marks": [{"type": "strong"}]},
                        {"type": "text", "text": severity.upper()},
                        {"type": "text", "text": " | "},
                        {"type": "text", "text": f"Resolution Time: ", "marks": [{"type": "strong"}]},
                        {"type": "text", "text": resolution_time},
                    ],
                }
            ],
        })

        # Root Cause section
        content.append({
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Root Cause"}],
        })
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": root_cause}],
        })

        # Evidence section
        content.append({
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Evidence"}],
        })
        if evidence:
            content.append({
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": e}]}
                        ],
                    }
                    for e in evidence[:10]
                ],
            })

        # Actions Taken section
        content.append({
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Actions Taken"}],
        })
        if execution_results:
            for result in execution_results:
                action = result.get("action", {})
                success = result.get("success", False)
                status = "✅" if success else "❌"
                action_type = action.get("type", "unknown")
                description = action.get("description", "No description")

                content.append({
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": f"{status} {action_type}: {description}"},
                    ],
                })

        # Slack link if provided
        if slack_thread_url:
            content.append({
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "References"}],
            })
            content.append({
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Slack Thread: "},
                    {
                        "type": "text",
                        "text": slack_thread_url,
                        "marks": [{"type": "link", "attrs": {"href": slack_thread_url}}],
                    },
                ],
            })

        # Postmortem checklist
        content.append({
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Postmortem Checklist"}],
        })
        checklist_items = [
            "Review incident timeline",
            "Validate root cause analysis",
            "Identify what went well",
            "Identify what could be improved",
            "Create action items to prevent recurrence",
            "Schedule postmortem meeting (if needed)",
            "Share learnings with team",
        ]
        content.append({
            "type": "taskList",
            "attrs": {"localId": "checklist"},
            "content": [
                {
                    "type": "taskItem",
                    "attrs": {"localId": f"task-{i}", "state": "TODO"},
                    "content": [
                        {"type": "text", "text": item}
                    ],
                }
                for i, item in enumerate(checklist_items)
            ],
        })

        return {
            "type": "doc",
            "version": 1,
            "content": content,
        }

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
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
                parts.append(f"{minutes} min")
            return " ".join(parts)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
