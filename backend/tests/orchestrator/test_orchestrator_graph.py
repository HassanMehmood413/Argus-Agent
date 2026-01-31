"""
Tests for the Orchestrator Graph.

Tests the orchestrator nodes, routing logic, and graph structure.
Uses mocked subgraphs to avoid requiring real external services.

Run with: pytest tests/orchestrator/ -v
"""

import pytest
from typing import Dict, Any
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from backend.modules.orchestrator.state import OrchestratorState
from backend.modules.orchestrator.nodes import (
    receive_alert_node,
    skip_approval_node,
    handle_rejection_node,
    route_after_analyzer,
    route_after_approval,
    route_after_execution,
    _generate_incident_id,
    _extract_evidence,
)
from backend.modules.orchestrator.graph import (
    build_orchestrator_graph,
    orchestrator_graph,
)


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_generate_incident_id_format(self):
        """Should generate ID in correct format."""
        incident_id = _generate_incident_id()

        assert incident_id.startswith("INC-")
        parts = incident_id.split("-")
        assert len(parts) == 3
        # Second part should be date (8 digits)
        assert len(parts[1]) == 8
        assert parts[1].isdigit()
        # Third part should be hex (6 chars)
        assert len(parts[2]) == 6

    def test_generate_incident_id_unique(self):
        """Should generate unique IDs."""
        ids = [_generate_incident_id() for _ in range(10)]
        assert len(set(ids)) == 10  # All unique

    def test_extract_evidence_from_metrics(self):
        """Should extract evidence from high metrics."""
        state = {
            "metrics": {
                "cpu_usage_percent": 95.0,
                "memory_usage_percent": 88.0,
                "error_rate_percent": 12.0,
            },
            "pod_status": {},
            "events": [],
            "recent_deployments": [],
        }

        evidence = _extract_evidence(state)

        assert any("CPU" in e for e in evidence)
        assert any("memory" in e for e in evidence)
        assert any("error" in e for e in evidence)

    def test_extract_evidence_from_pod_status(self):
        """Should extract evidence from failed pods."""
        state = {
            "metrics": {},
            "pod_status": {"failed": 3, "unhealthy_pods": 2},
            "events": [],
            "recent_deployments": [],
        }

        evidence = _extract_evidence(state)

        assert any("failed" in e.lower() for e in evidence)

    def test_extract_evidence_from_events(self):
        """Should extract evidence from OOM events."""
        state = {
            "metrics": {},
            "pod_status": {},
            "events": [
                {"reason": "OOMKilled", "message": "Container killed"},
                {"reason": "OOMKilled", "message": "Another OOM"},
            ],
            "recent_deployments": [],
        }

        evidence = _extract_evidence(state)

        assert any("OOM" in e for e in evidence)

    def test_extract_evidence_empty_state(self):
        """Should return default message for empty state."""
        state = {
            "metrics": {},
            "pod_status": {},
            "events": [],
            "recent_deployments": [],
        }

        evidence = _extract_evidence(state)

        assert len(evidence) > 0
        assert "No specific evidence" in evidence[0]


# ============================================================================
# Node Tests: receive_alert_node
# ============================================================================


class TestReceiveAlertNode:
    """Tests for the receive_alert_node."""

    def test_initializes_incident_id(self, sample_alert):
        """Should generate incident ID if not provided."""
        state = {"alert": sample_alert, "severity": "high"}

        result = receive_alert_node(state)

        assert "incident_id" in result
        assert result["incident_id"].startswith("INC-")

    def test_preserves_provided_incident_id(self, sample_alert):
        """Should preserve incident ID if provided."""
        state = {
            "alert": sample_alert,
            "severity": "high",
            "incident_id": "INC-CUSTOM-001"
        }

        result = receive_alert_node(state)

        assert result["incident_id"] == "INC-CUSTOM-001"

    def test_sets_initial_status(self, sample_alert):
        """Should set status to 'monitoring'."""
        state = {"alert": sample_alert, "severity": "high"}

        result = receive_alert_node(state)

        assert result["status"] == "monitoring"

    def test_sets_timestamps(self, sample_alert):
        """Should set created_at and updated_at."""
        state = {"alert": sample_alert, "severity": "high"}

        result = receive_alert_node(state)

        assert "created_at" in result
        assert "updated_at" in result

    def test_extracts_severity_from_alert(self):
        """Should extract severity from alert if not provided."""
        state = {
            "alert": {"alertname": "Test", "severity": "critical"},
        }

        result = receive_alert_node(state)

        assert result["severity"] == "critical"


# ============================================================================
# Node Tests: skip_approval_node
# ============================================================================


class TestSkipApprovalNode:
    """Tests for the skip_approval_node."""

    def test_sets_auto_approved(self):
        """Should set approved to True with auto-approve."""
        state = {"incident_id": "INC-001"}

        result = skip_approval_node(state)

        assert result["approved"] is True
        assert result["approved_by"] == "auto-approve"
        assert result["status"] == "approved"

    def test_sets_approval_time(self):
        """Should set approval_time."""
        state = {"incident_id": "INC-001"}

        result = skip_approval_node(state)

        assert "approval_time" in result


# ============================================================================
# Node Tests: handle_rejection_node
# ============================================================================


class TestHandleRejectionNode:
    """Tests for the handle_rejection_node."""

    @pytest.mark.asyncio
    async def test_sets_escalated_status(self):
        """Should set status to escalated."""
        state = {
            "incident_id": "INC-001",
            "approved_by": "user123",
            "rejection_reason": "Need more info",
        }

        result = await handle_rejection_node(state)

        assert result["status"] == "escalated"


# ============================================================================
# Routing Function Tests
# ============================================================================


class TestRouteAfterAnalyzer:
    """Tests for route_after_analyzer function."""

    def test_requires_approval_for_high_severity(self):
        """Should require approval for high severity incidents."""
        state = {
            "incident_id": "INC-001",
            "severity": "high",
            "confidence": 0.9,
            "needs_approval": True,
            "recommended_actions": [
                {"risk_level": "medium"},
            ],
        }

        result = route_after_analyzer(state)

        assert result == "run_approval"

    def test_skips_approval_for_low_risk(self):
        """Should skip approval for low-risk, high-confidence, low-severity."""
        state = {
            "incident_id": "INC-001",
            "severity": "low",
            "confidence": 0.9,
            "needs_approval": False,
            "recommended_actions": [
                {"risk_level": "low"},
                {"risk_level": "none"},
            ],
        }

        result = route_after_analyzer(state)

        assert result == "skip_approval"

    def test_requires_approval_for_critical_severity(self):
        """Should always require approval for critical severity."""
        state = {
            "incident_id": "INC-001",
            "severity": "critical",
            "confidence": 0.99,
            "needs_approval": True,
            "recommended_actions": [
                {"risk_level": "low"},
            ],
        }

        result = route_after_analyzer(state)

        assert result == "run_approval"

    def test_requires_approval_for_low_confidence(self):
        """Should require approval when confidence is low."""
        state = {
            "incident_id": "INC-001",
            "severity": "low",
            "confidence": 0.5,  # Below threshold
            "needs_approval": True,
            "recommended_actions": [
                {"risk_level": "low"},
            ],
        }

        result = route_after_analyzer(state)

        assert result == "run_approval"


class TestRouteAfterApproval:
    """Tests for route_after_approval function."""

    def test_routes_to_executor_when_approved(self):
        """Should route to executor when approved."""
        state = {
            "incident_id": "INC-001",
            "approved": True,
        }

        result = route_after_approval(state)

        assert result == "run_executor"

    def test_routes_to_rejection_when_rejected(self):
        """Should route to handle_rejection when rejected."""
        state = {
            "incident_id": "INC-001",
            "approved": False,
        }

        result = route_after_approval(state)

        assert result == "handle_rejection"


class TestRouteAfterExecution:
    """Tests for route_after_execution function."""

    def test_routes_to_summary_for_resolved(self):
        """Should route to summary for resolved incidents."""
        state = {"status": "resolved"}

        result = route_after_execution(state)

        assert result == "run_summary"

    def test_routes_to_summary_for_failed(self):
        """Should route to summary for failed incidents."""
        state = {"status": "failed"}

        result = route_after_execution(state)

        assert result == "run_summary"

    def test_routes_to_end_for_escalated(self):
        """Should route to end for escalated incidents."""
        state = {"status": "escalated"}

        result = route_after_execution(state)

        assert result == "__end__"


# ============================================================================
# Graph Structure Tests
# ============================================================================


class TestOrchestratorGraphStructure:
    """Tests for the orchestrator graph structure."""

    def test_graph_builds_without_error(self):
        """Should build graph without errors."""
        graph = build_orchestrator_graph()
        assert graph is not None

    def test_graph_has_all_nodes(self):
        """Should have all required nodes."""
        graph = build_orchestrator_graph()

        expected_nodes = [
            "receive_alert",
            "run_monitor",
            "run_analyzer",
            "run_approval",
            "skip_approval",
            "handle_rejection",
            "run_executor",
            "run_summary",
        ]

        node_names = list(graph.nodes.keys())

        for node in expected_nodes:
            assert node in node_names, f"Missing node: {node}"

    def test_compiled_graph_exists(self):
        """Should have compiled graph available."""
        assert orchestrator_graph is not None

    def test_graph_has_checkpointer(self):
        """Should have checkpointer configured."""
        assert orchestrator_graph.checkpointer is not None


# ============================================================================
# Integration Tests (with mocked subgraphs)
# ============================================================================


class TestOrchestratorIntegration:
    """Integration tests with mocked subgraphs."""

    @pytest.mark.asyncio
    async def test_receive_alert_to_monitor(self, sample_alert, mock_monitor_result):
        """Test flow from receive_alert to run_monitor."""
        with patch("backend.modules.orchestrator.nodes.monitor_subgraph") as mock_monitor:
            mock_monitor.ainvoke = AsyncMock(return_value=mock_monitor_result)

            # Test receive_alert
            state = {"alert": sample_alert, "severity": "high"}
            alert_result = receive_alert_node(state)

            assert alert_result["status"] == "monitoring"
            assert "incident_id" in alert_result

    @pytest.mark.asyncio
    async def test_auto_approve_flow(
        self,
        sample_alert,
        mock_monitor_result,
        mock_analyzer_result,
    ):
        """Test auto-approve flow when conditions are met."""
        # Modify analyzer result for auto-approve
        mock_analyzer_result["requires_approval"] = False
        mock_analyzer_result["confidence"] = 0.95

        state = {
            "alert": sample_alert,
            "severity": "low",
            "confidence": 0.95,
            "needs_approval": False,
            "recommended_actions": [
                {"risk_level": "low"},
            ],
        }

        # Check routing
        route = route_after_analyzer(state)
        assert route == "skip_approval"

        # Check skip_approval result
        skip_result = skip_approval_node(state)
        assert skip_result["approved"] is True
        assert skip_result["approved_by"] == "auto-approve"

    @pytest.mark.asyncio
    async def test_approval_flow(
        self,
        sample_alert,
        mock_analyzer_result,
        mock_approval_result_approved,
    ):
        """Test approval flow when approval is required."""
        state = {
            "alert": sample_alert,
            "severity": "high",
            "confidence": 0.85,
            "needs_approval": True,
            "recommended_actions": [
                {"risk_level": "medium"},
            ],
        }

        # Check routing requires approval
        route = route_after_analyzer(state)
        assert route == "run_approval"

    @pytest.mark.asyncio
    async def test_rejection_flow(self, mock_approval_result_rejected):
        """Test rejection flow."""
        state = {
            "incident_id": "INC-001",
            "approved": False,
            "approved_by": "user123",
            "rejection_reason": "Need more info",
        }

        # Check routing
        route = route_after_approval(state)
        assert route == "handle_rejection"

        # Check rejection handling
        result = await handle_rejection_node(state)
        assert result["status"] == "escalated"


# ============================================================================
# State Preservation Tests
# ============================================================================


class TestStatePreservation:
    """Tests for state preservation through the graph."""

    def test_receive_alert_preserves_input(self, sample_alert):
        """Should preserve original alert in state."""
        state = {"alert": sample_alert, "severity": "high"}

        result = receive_alert_node(state)

        # Original alert should be accessible
        full_state = {**state, **result}
        assert full_state["alert"] == sample_alert
        assert full_state["severity"] == "high"

    def test_skip_approval_preserves_actions(self):
        """Should preserve recommended_actions through skip_approval."""
        state = {
            "incident_id": "INC-001",
            "recommended_actions": [{"type": "restart"}],
        }

        result = skip_approval_node(state)

        # Actions should still be accessible
        full_state = {**state, **result}
        assert full_state["recommended_actions"] == [{"type": "restart"}]
