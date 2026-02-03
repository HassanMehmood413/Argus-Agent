"""
Pytest fixtures for Orchestrator agent tests.

These fixtures provide test data and mocked subgraphs for testing
the Orchestrator without requiring real external services.
"""

import pytest
from typing import Dict, Any
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.fixture
def sample_alert() -> Dict[str, Any]:
    """Sample alert data for testing."""
    return {
        "alertname": "HighMemoryUsage",
        "service": "api-gateway",
        "namespace": "production",
        "severity": "high",
        "labels": {
            "service": "api-gateway",
            "namespace": "production",
            "pod": "api-gateway-abc123",
        },
        "annotations": {
            "description": "Memory usage above 90%",
            "runbook": "https://runbook.example.com/memory",
        },
    }


@pytest.fixture
def sample_orchestrator_input(sample_alert) -> Dict[str, Any]:
    """Sample input state for orchestrator."""
    return {
        "alert": sample_alert,
        "severity": "high",
        "slack_channel": "#incidents-test",
    }


@pytest.fixture
def mock_monitor_result() -> Dict[str, Any]:
    """Mock result from Monitor subgraph."""
    return {
        "metrics": {
            "cpu_usage_percent": 75.5,
            "memory_usage_percent": 92.3,
            "error_rate_percent": 2.5,
            "latency_p99_seconds": 0.8,
        },
        "logs": [
            {"level": "ERROR", "message": "Out of memory error", "timestamp": "2024-01-15T10:30:00Z"},
            {"level": "WARN", "message": "High memory pressure", "timestamp": "2024-01-15T10:29:00Z"},
        ],
        "pod_status": {
            "total": 5,
            "running": 3,
            "failed": 2,
            "unhealthy_pods": 2,
            "pods": [
                {"name": "api-gateway-abc123", "status": "Running", "restarts": 5},
                {"name": "api-gateway-def456", "status": "CrashLoopBackOff", "restarts": 12},
            ],
        },
        "events": [
            {"reason": "OOMKilled", "message": "Container killed due to OOM", "count": 3},
        ],
        "recent_deployments": [
            {"name": "api-gateway", "image": "api-gateway:v2.3.1", "revision": 42},
        ],
        "health_summary": "Service api-gateway: 2 issues detected. High memory usage: 92.3%; 2 failed pods",
    }


@pytest.fixture
def mock_analyzer_result() -> Dict[str, Any]:
    """Mock result from Analyzer subgraph."""
    return {
        "root_cause": "Memory leak in api-gateway v2.3.1 due to unclosed database connections",
        "confidence": 0.85,
        "analysis_reasoning": "High memory usage combined with OOM kills suggests memory leak",
        "patterns": [
            {"type": "high_memory", "severity": "critical", "confidence": 0.9},
            {"type": "oom_killed", "severity": "critical", "confidence": 0.95},
        ],
        "similar_incidents": [
            {"id": "INC-2024-001", "similarity": 0.85, "resolution": "Rolled back deployment"},
        ],
        "recommended_actions": [
            {
                "type": "rollback",
                "target": "deployment/api-gateway",
                "description": "Roll back to v2.3.0",
                "risk_level": "medium",
            },
            {
                "type": "restart_pods",
                "target": "deployment/api-gateway",
                "description": "Restart unhealthy pods",
                "risk_level": "low",
            },
        ],
        "requires_approval": True,
    }


@pytest.fixture
def mock_approval_result_approved() -> Dict[str, Any]:
    """Mock result from Approval subgraph (approved)."""
    return {
        "approved": True,
        "approved_by": "U123456",
        "approved_by_name": "John Doe",
        "approval_time": datetime.utcnow().isoformat(),
        "rejection_reason": None,
        "modified_actions": None,
    }


@pytest.fixture
def mock_approval_result_rejected() -> Dict[str, Any]:
    """Mock result from Approval subgraph (rejected)."""
    return {
        "approved": False,
        "approved_by": "U654321",
        "approved_by_name": "Jane Smith",
        "approval_time": datetime.utcnow().isoformat(),
        "rejection_reason": "Need more investigation before taking action",
        "modified_actions": None,
    }


@pytest.fixture
def mock_executor_result_success() -> Dict[str, Any]:
    """Mock result from Executor subgraph (success)."""
    return {
        "execution_results": [
            {
                "action": {"type": "rollback", "description": "Roll back to v2.3.0"},
                "success": True,
                "output": "Rolled back to revision 41",
            },
            {
                "action": {"type": "restart_pods", "description": "Restart unhealthy pods"},
                "success": True,
                "output": "3 pods restarted",
            },
        ],
        "skipped_actions": [],
        "all_succeeded": True,
        "execution_summary": "Successfully executed 2/2 actions",
    }


@pytest.fixture
def mock_executor_result_failure() -> Dict[str, Any]:
    """Mock result from Executor subgraph (failure)."""
    return {
        "execution_results": [
            {
                "action": {"type": "rollback", "description": "Roll back to v2.3.0"},
                "success": False,
                "error": "Rollback failed: no previous revision",
            },
        ],
        "skipped_actions": [
            {"action": {"type": "restart_pods"}, "reason": "Skipped due to previous failure"},
        ],
        "all_succeeded": False,
        "execution_summary": "Executed 1/2 actions. 0 succeeded, 1 failed, 1 skipped.",
    }


@pytest.fixture
def mock_summary_result() -> Dict[str, Any]:
    """Mock result from Summary subgraph."""
    return {
        "summary": "Incident INC-TEST-001 RESOLVED. Root cause: Memory leak. Actions: rollback, restart.",
        "resolution_time_seconds": 720.0,
        "summary_message_ts": "1234567890.123456",
        "postmortem_ticket": "POST-12345",
    }


@pytest.fixture
def mock_all_subgraphs(
    mock_monitor_result,
    mock_analyzer_result,
    mock_approval_result_approved,
    mock_executor_result_success,
    mock_summary_result,
):
    """Mock all subgraphs for full pipeline testing."""
    with patch("backend.modules.orchestrator.nodes.monitor_subgraph") as mock_monitor, \
         patch("backend.modules.orchestrator.nodes.analyzer_subgraph") as mock_analyzer, \
         patch("backend.modules.orchestrator.nodes.approval_subgraph") as mock_approval, \
         patch("backend.modules.execution.graph.executor_subgraph") as mock_executor, \
         patch("backend.modules.summary.graph.summary_subgraph") as mock_summary:

        mock_monitor.ainvoke = AsyncMock(return_value=mock_monitor_result)
        mock_analyzer.ainvoke = AsyncMock(return_value=mock_analyzer_result)
        mock_approval.ainvoke = AsyncMock(return_value=mock_approval_result_approved)
        mock_executor.ainvoke = AsyncMock(return_value=mock_executor_result_success)
        mock_summary.ainvoke = AsyncMock(return_value=mock_summary_result)

        yield {
            "monitor": mock_monitor,
            "analyzer": mock_analyzer,
            "approval": mock_approval,
            "executor": mock_executor,
            "summary": mock_summary,
        }
