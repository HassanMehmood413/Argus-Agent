"""
Summary Agent Clients

Provides external service integrations for the Summary agent.
"""

from backend.modules.summary.clients.slack import SummarySlackClient
from backend.modules.summary.clients.jira import JiraClient

__all__ = ["SummarySlackClient", "JiraClient"]
