"""
Pytest fixtures for Execution agent tests.

These fixtures provide test data and setup for testing the Executor subgraph
with mocked Kubernetes executor (no real K8s cluster required).
"""

import pytest
from typing import Dict, Any, List
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def sample_incident_id() -> str:
    """Sample incident ID for testing."""
    return "INC-2024-EXEC-001"


@pytest.fixture
def sample_actions_low_risk() -> List[Dict[str, Any]]:
    """
    Sample actions with low risk level (auto-execute).
    """
    return [
        {
            "action_id": "1",
            "type": "check_dependency",
            "target": "deployment/api-gateway",
            "target_namespace": "production",
            "reason": "Verify database connectivity",
            "risk_level": "none",
            "parameters": {"dependency_name": "postgres"},
            "expected_outcome": "Database connectivity confirmed",
            "rollback_plan": "N/A",
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
    ]


@pytest.fixture
def sample_actions_mixed_risk() -> List[Dict[str, Any]]:
    """
    Sample actions with mixed risk levels (some require approval).
    """
    return [
        {
            "action_id": "1",
            "type": "restart_pods",
            "target": "deployment/api-gateway",
            "target_namespace": "production",
            "reason": "Clear memory state",
            "risk_level": "low",
            "parameters": {"rolling": True},
            "expected_outcome": "Pods restarted",
            "rollback_plan": "N/A",
        },
        {
            "action_id": "2",
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
            "action_id": "3",
            "type": "scale_down",
            "target": "deployment/api-gateway",
            "target_namespace": "production",
            "reason": "Reduce load",
            "risk_level": "high",
            "parameters": {"target_replicas": 1},
            "expected_outcome": "Reduced replicas",
            "rollback_plan": "Scale back up",
        },
    ]


@pytest.fixture
def sample_actions_high_risk() -> List[Dict[str, Any]]:
    """
    Sample actions with high risk level (all require approval).
    """
    return [
        {
            "action_id": "1",
            "type": "rollback",
            "target": "deployment/api-gateway",
            "target_namespace": "production",
            "reason": "Roll back deployment",
            "risk_level": "medium",
            "parameters": {"to_revision": 41},
            "expected_outcome": "Service rolled back",
            "rollback_plan": "Re-deploy",
        },
        {
            "action_id": "2",
            "type": "scale_down",
            "target": "deployment/api-gateway",
            "target_namespace": "production",
            "reason": "Emergency scale down",
            "risk_level": "high",
            "parameters": {"target_replicas": 0},
            "expected_outcome": "Service scaled to zero",
            "rollback_plan": "Scale back up",
        },
    ]


@pytest.fixture
def executor_state_approved(sample_incident_id, sample_actions_low_risk) -> Dict[str, Any]:
    """
    Complete executor state with approved actions.
    """
    return {
        "incident_id": sample_incident_id,
        "approved": True,
        "approved_by": "test_user",
        "actions_to_execute": sample_actions_low_risk,
        "dry_run": False,
        "stop_on_failure": True,
        "timeout_seconds": 300,
        "slack_channel": "#incidents-test",
        "slack_thread_ts": None,
        "current_action_index": 0,
        "current_action": None,
        "execution_results": [],
        "skipped_actions": [],
        "aborted": False,
    }


@pytest.fixture
def executor_state_not_approved(sample_incident_id, sample_actions_low_risk) -> Dict[str, Any]:
    """
    Executor state with non-approved actions.
    """
    return {
        "incident_id": sample_incident_id,
        "approved": False,
        "actions_to_execute": sample_actions_low_risk,
    }


@pytest.fixture
def executor_state_dry_run(sample_incident_id, sample_actions_mixed_risk) -> Dict[str, Any]:
    """
    Executor state for dry run mode.
    """
    return {
        "incident_id": sample_incident_id,
        "approved": True,
        "approved_by": "test_user",
        "actions_to_execute": sample_actions_mixed_risk,
        "dry_run": True,
        "stop_on_failure": False,
        "timeout_seconds": 300,
        "slack_channel": "#incidents-test",
        "current_action_index": 0,
        "execution_results": [],
        "skipped_actions": [],
        "aborted": False,
    }


@pytest.fixture
def mock_kubernetes_executor():
    """
    Mock Kubernetes executor for testing without real cluster.
    """
    mock = MagicMock()

    # Mock successful execution
    mock.rollback = AsyncMock(
        return_value={
            "success": True,
            "output": "Rollback to revision 41 completed",
            "revision": 41,
        }
    )
    mock.restart_pods = AsyncMock(
        return_value={
            "success": True,
            "output": "Rolling restart initiated",
            "pods_restarted": 3,
        }
    )
    mock.scale = AsyncMock(
        return_value={
            "success": True,
            "output": "Scaled to 5 replicas",
            "new_replicas": 5,
        }
    )
    mock.check_dependency = AsyncMock(
        return_value={
            "success": True,
            "output": "Dependency healthy",
            "status": "healthy",
        }
    )

    return mock


@pytest.fixture
def mock_kubernetes_executor_failure():
    """
    Mock Kubernetes executor that returns failures.
    """
    mock = MagicMock()

    mock.rollback = AsyncMock(
        return_value={
            "success": False,
            "error": "Rollback failed: revision not found",
        }
    )
    mock.restart_pods = AsyncMock(
        return_value={
            "success": False,
            "error": "Failed to restart pods: permission denied",
        }
    )

    return mock


@pytest.fixture
def execution_result_success() -> Dict[str, Any]:
    """
    Sample successful execution result.
    """
    return {
        "success": True,
        "action_id": "1",
        "action_type": "restart_pods",
        "output": "Rolling restart completed",
        "started_at": "2024-01-15T10:30:00Z",
        "completed_at": "2024-01-15T10:30:15Z",
        "duration_seconds": 15,
    }


@pytest.fixture
def execution_result_failure() -> Dict[str, Any]:
    """
    Sample failed execution result.
    """
    return {
        "success": False,
        "action_id": "2",
        "action_type": "rollback",
        "error": "Rollback failed: revision 41 not found",
        "started_at": "2024-01-15T10:31:00Z",
        "completed_at": "2024-01-15T10:31:05Z",
    }
