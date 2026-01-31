"""
Pytest fixtures for Summary agent tests.

These fixtures provide test data and setup for testing the Summary subgraph
with mocked Slack and Jira clients.
"""

import pytest
from typing import Dict, Any, List
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def sample_incident_id() -> str:
    """Sample incident ID for testing."""
    return "INC-2024-TEST-001"


@pytest.fixture
def sample_summary_state() -> Dict[str, Any]:
    """
    Complete summary state for testing with all required fields.
    """
    created_at = (datetime.utcnow() - timedelta(minutes=15)).isoformat()

    return {
        "incident_id": "INC-2024-TEST-001",
        "severity": "high",
        "alert": {
            "alertname": "HighMemoryUsage",
            "service": "api-gateway",
            "namespace": "production",
        },
        "root_cause": "Memory leak in version 2.3.1 due to unclosed database connections",
        "confidence": 0.85,
        "evidence": [
            "Memory usage at 95%",
            "OOMKilled events detected",
            "Recent deployment v2.3.1",
            "Pod restarts: 5 in last 10 minutes",
        ],
        "recommended_actions": [
            {
                "type": "rollback",
                "target": "deployment/api-gateway",
                "description": "Roll back to previous stable version v2.3.0",
                "risk_level": "medium",
            },
            {
                "type": "restart_pods",
                "target": "deployment/api-gateway",
                "description": "Restart pods to clear memory state",
                "risk_level": "low",
            },
        ],
        "approved_by": "john.doe",
        "execution_results": [
            {
                "action": {
                    "type": "rollback",
                    "target": "deployment/api-gateway",
                    "description": "Roll back to previous stable version v2.3.0",
                },
                "success": True,
                "output": "Rolled back to revision 41",
                "duration_seconds": 12.5,
            },
            {
                "action": {
                    "type": "restart_pods",
                    "target": "deployment/api-gateway",
                    "description": "Restart pods to clear memory state",
                },
                "success": True,
                "output": "3 pods restarted successfully",
                "duration_seconds": 8.2,
            },
        ],
        "all_succeeded": True,
        "created_at": created_at,
        "slack_channel": "#incidents-test",
        "slack_thread_ts": "1234567890.123456",
    }


@pytest.fixture
def minimal_summary_state() -> Dict[str, Any]:
    """
    Minimal summary state with only required fields.
    """
    return {
        "incident_id": "INC-2024-MIN-001",
        "severity": "low",
        "root_cause": "Unknown issue",
        "confidence": 0.5,
        "evidence": [],
        "recommended_actions": [],
        "approved_by": "auto",
        "execution_results": [],
        "all_succeeded": True,
        "created_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def failed_execution_state() -> Dict[str, Any]:
    """
    Summary state where execution partially failed.
    """
    created_at = (datetime.utcnow() - timedelta(minutes=30)).isoformat()

    return {
        "incident_id": "INC-2024-FAIL-001",
        "severity": "critical",
        "alert": {"alertname": "PodCrashLoop", "service": "payment-service"},
        "root_cause": "Database connection pool exhausted",
        "confidence": 0.75,
        "evidence": [
            "Connection timeout errors",
            "Database CPU at 100%",
        ],
        "recommended_actions": [
            {"type": "restart_pods", "description": "Restart pods"},
            {"type": "scale_up", "description": "Scale up replicas"},
        ],
        "approved_by": "jane.smith",
        "execution_results": [
            {
                "action": {"type": "restart_pods", "description": "Restart pods"},
                "success": True,
                "output": "Pods restarted",
            },
            {
                "action": {"type": "scale_up", "description": "Scale up replicas"},
                "success": False,
                "error": "Insufficient cluster resources",
            },
        ],
        "all_succeeded": False,
        "created_at": created_at,
        "slack_channel": "#incidents",
    }


@pytest.fixture
def critical_severity_state() -> Dict[str, Any]:
    """
    Summary state with critical severity (should create postmortem).
    """
    return {
        "incident_id": "INC-2024-CRIT-001",
        "severity": "critical",
        "alert": {"alertname": "ServiceDown", "service": "checkout"},
        "root_cause": "Complete service outage due to network partition",
        "confidence": 0.95,
        "evidence": ["All pods unreachable", "Network ACL misconfigured"],
        "recommended_actions": [
            {"type": "update_network", "description": "Fix network ACL"},
        ],
        "approved_by": "oncall-team",
        "execution_results": [
            {
                "action": {"type": "update_network", "description": "Fix network ACL"},
                "success": True,
                "output": "Network ACL updated",
            },
        ],
        "all_succeeded": True,
        "created_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        "slack_channel": "#critical-incidents",
        "slack_thread_ts": "9876543210.654321",
    }


@pytest.fixture
def low_severity_state() -> Dict[str, Any]:
    """
    Summary state with low severity (should NOT create postmortem).
    """
    return {
        "incident_id": "INC-2024-LOW-001",
        "severity": "low",
        "alert": {"alertname": "HighLatency", "service": "logging"},
        "root_cause": "Temporary network congestion",
        "confidence": 0.6,
        "evidence": ["Latency spike for 2 minutes"],
        "recommended_actions": [],
        "approved_by": "auto",
        "execution_results": [],
        "all_succeeded": True,
        "created_at": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
    }


@pytest.fixture
def mock_slack_client():
    """
    Mock Slack client for testing without real Slack API.
    """
    mock_client = MagicMock()
    mock_client.chat_postMessage = MagicMock(
        return_value={
            "ok": True,
            "ts": "1234567890.123456",
            "channel": "C123456",
        }
    )
    return mock_client


@pytest.fixture
def mock_jira_client():
    """
    Mock Jira client for testing without real Jira API.
    """
    mock_client = MagicMock()
    mock_client.create_postmortem_ticket = AsyncMock(
        return_value={
            "ok": True,
            "key": "POST-123",
            "url": "https://company.atlassian.net/browse/POST-123",
            "id": "12345",
        }
    )
    mock_client.close = AsyncMock()
    return mock_client


@pytest.fixture
def mock_jira_client_error():
    """
    Mock Jira client that returns an error.
    """
    mock_client = MagicMock()
    mock_client.create_postmortem_ticket = AsyncMock(
        return_value={
            "ok": False,
            "error": "Project not found",
        }
    )
    mock_client.close = AsyncMock()
    return mock_client
