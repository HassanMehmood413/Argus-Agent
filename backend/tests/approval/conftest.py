"""
Pytest fixtures for Approval agent tests.

These fixtures provide test data and setup for testing the Approval subgraph
with mocked Slack client (no real Slack required).
"""

import pytest
from typing import Dict, Any, List
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def sample_incident_id() -> str:
    """Sample incident ID for testing."""
    return "INC-2024-TEST-001"


@pytest.fixture
def sample_approval_state() -> Dict[str, Any]:
    """
    Complete approval state for testing.
    """
    return {
        "incident_id": "INC-2024-TEST-001",
        "severity": "high",
        "root_cause": "Memory leak in version 2.3.1 due to unclosed database connections",
        "confidence": 0.85,
        "evidence": [
            "Memory usage at 95%",
            "OOMKilled events detected",
            "Recent deployment v2.3.1",
        ],
        "recommended_actions": [
            {
                "action_id": "1",
                "type": "rollback",
                "target": "deployment/api-gateway",
                "target_namespace": "production",
                "reason": "Roll back to previous stable version",
                "risk_level": "medium",
                "parameters": {"to_revision": 41},
                "expected_outcome": "Service restored to stable state",
                "rollback_plan": "Re-deploy if rollback fails",
            },
            {
                "action_id": "2",
                "type": "restart_pods",
                "target": "deployment/api-gateway",
                "target_namespace": "production",
                "reason": "Clear memory state",
                "risk_level": "low",
                "parameters": {"rolling": True},
                "expected_outcome": "Pods restarted with fresh memory",
                "rollback_plan": "N/A",
            },
        ],
        "similar_incidents": [
            {
                "id": "INC-2024-001",
                "title": "API Gateway OOM Crash",
                "similarity": 0.85,
                "root_cause": "Memory leak due to unclosed connections",
                "resolution": "Rolled back deployment",
            }
        ],
        "slack_channel": "#incidents-test",
        "slack_thread_ts": None,
    }


@pytest.fixture
def minimal_approval_state() -> Dict[str, Any]:
    """
    Minimal approval state with only required fields.
    """
    return {
        "incident_id": "INC-2024-MIN-001",
        "severity": "low",
        "root_cause": "Unknown issue",
        "recommended_actions": [
            {
                "action_id": "1",
                "type": "investigate",
                "target": "service/unknown",
                "risk_level": "none",
            }
        ],
    }


@pytest.fixture
def missing_fields_state() -> Dict[str, Any]:
    """
    Approval state with missing required fields for validation testing.
    """
    return {
        "incident_id": "INC-2024-MISSING",
        # Missing: severity, root_cause, recommended_actions
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
    mock_client.chat_update = MagicMock(return_value={"ok": True})
    return mock_client


@pytest.fixture
def approval_decision_approved() -> Dict[str, Any]:
    """
    Sample approval decision (approved).
    """
    return {
        "approved": True,
        "approved_by": "U1234567890",
        "approved_by_name": "John Doe",
        "rejection_reason": None,
        "modified_actions": None,
        "approval_notes": "LGTM, proceed with rollback",
    }


@pytest.fixture
def approval_decision_rejected() -> Dict[str, Any]:
    """
    Sample approval decision (rejected).
    """
    return {
        "approved": False,
        "approved_by": "U0987654321",
        "approved_by_name": "Jane Smith",
        "rejection_reason": "Need to investigate more before taking action",
        "modified_actions": None,
        "approval_notes": None,
    }


@pytest.fixture
def approval_decision_modified() -> Dict[str, Any]:
    """
    Sample approval decision with modified actions.
    """
    return {
        "approved": True,
        "approved_by": "U1234567890",
        "approved_by_name": "John Doe",
        "rejection_reason": None,
        "modified_actions": [
            {
                "action_id": "1",
                "type": "restart_pods",
                "target": "deployment/api-gateway",
                "target_namespace": "production",
                "reason": "Try restart first before rollback",
                "risk_level": "low",
            }
        ],
        "approval_notes": "Modified to try restart first",
    }
