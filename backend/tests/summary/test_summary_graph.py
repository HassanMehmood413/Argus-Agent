"""
Tests for the Summary Subgraph.

Tests each node individually and the full graph execution.
Uses mocked Slack and Jira clients since we don't want to send real messages during tests.

Run with: pytest tests/summary/ -v
"""

import pytest
from typing import Dict, Any
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

from backend.modules.summary.state import SummaryState
from backend.modules.summary.nodes import (
    generate_summary_node,
    post_to_slack_node,
    create_postmortem_node,
    _format_duration,
    _format_evidence,
    _format_actions_summary,
)
from backend.modules.summary.graph import build_summary_subgraph, summary_subgraph
from backend.modules.summary.clients.slack import SummarySlackClient
from backend.modules.summary.clients.jira import JiraClient


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestHelperFunctions:
    """
    Tests for helper formatting functions.
    """

    def test_format_duration_seconds(self):
        """Should format seconds correctly."""
        assert _format_duration(30) == "30 seconds"
        assert _format_duration(1) == "1 seconds"
        assert _format_duration(0) == "0 seconds"

    def test_format_duration_minutes(self):
        """Should format minutes correctly."""
        assert _format_duration(60) == "1 minute"
        assert _format_duration(120) == "2 minutes"
        assert _format_duration(300) == "5 minutes"

    def test_format_duration_hours(self):
        """Should format hours correctly."""
        assert _format_duration(3600) == "1 hour"
        assert _format_duration(7200) == "2 hours"
        assert _format_duration(5400) == "1 hour 30 minutes"

    def test_format_evidence_empty(self):
        """Should handle empty evidence list."""
        result = _format_evidence([])
        assert "No evidence" in result

    def test_format_evidence_with_items(self):
        """Should format evidence items with bullets."""
        evidence = ["Item 1", "Item 2", "Item 3"]
        result = _format_evidence(evidence)

        assert "• Item 1" in result
        assert "• Item 2" in result
        assert "• Item 3" in result

    def test_format_evidence_truncates_long_list(self):
        """Should truncate to 10 items max."""
        evidence = [f"Item {i}" for i in range(15)]
        result = _format_evidence(evidence)

        assert "• Item 0" in result
        assert "• Item 9" in result
        # Item 10+ should not be present
        assert "• Item 10" not in result

    def test_format_actions_summary_empty(self):
        """Should handle empty execution results."""
        result = _format_actions_summary([])
        assert "No actions" in result

    def test_format_actions_summary_success(self):
        """Should format successful actions with checkmarks."""
        results = [
            {
                "action": {"type": "restart_pods", "description": "Restart pods"},
                "success": True,
            }
        ]
        result = _format_actions_summary(results)

        assert "✅" in result
        assert "restart_pods" in result

    def test_format_actions_summary_failure(self):
        """Should format failed actions with X and error message."""
        results = [
            {
                "action": {"type": "scale_up", "description": "Scale up"},
                "success": False,
                "error": "Insufficient resources",
            }
        ]
        result = _format_actions_summary(results)

        assert "❌" in result
        assert "scale_up" in result
        assert "Insufficient resources" in result


# ============================================================================
# Node Tests: generate_summary_node
# ============================================================================


class TestGenerateSummaryNode:
    """
    Tests for the summary generation node.
    """

    def test_generates_summary_text(self, sample_summary_state):
        """Should generate comprehensive summary text."""
        result = generate_summary_node(sample_summary_state)

        assert "summary" in result
        summary = result["summary"]

        # Check key elements are present
        assert "INC-2024-TEST-001" in summary
        assert "RESOLVED" in summary
        assert "HIGH" in summary
        assert "Memory leak" in summary
        assert "john.doe" in summary

    def test_calculates_resolution_time(self, sample_summary_state):
        """Should calculate resolution time from created_at."""
        result = generate_summary_node(sample_summary_state)

        assert "resolution_time_seconds" in result
        assert result["resolution_time_seconds"] > 0
        # Should be approximately 15 minutes (900 seconds)
        assert 800 < result["resolution_time_seconds"] < 1000

    def test_handles_missing_created_at(self, minimal_summary_state):
        """Should handle missing or invalid created_at."""
        state = {**minimal_summary_state}
        del state["created_at"]

        result = generate_summary_node(state)

        assert "resolution_time_seconds" in result
        assert result["resolution_time_seconds"] == 0.0

    def test_shows_partially_resolved_for_failures(self, failed_execution_state):
        """Should show PARTIALLY RESOLVED when not all succeeded."""
        result = generate_summary_node(failed_execution_state)

        assert "PARTIALLY RESOLVED" in result["summary"]
        assert "⚠️" in result["summary"]

    def test_shows_resolved_for_success(self, sample_summary_state):
        """Should show RESOLVED when all succeeded."""
        result = generate_summary_node(sample_summary_state)

        assert "RESOLVED" in result["summary"]
        assert "✅" in result["summary"]

    def test_includes_evidence(self, sample_summary_state):
        """Should include evidence in summary."""
        result = generate_summary_node(sample_summary_state)

        assert "Memory usage at 95%" in result["summary"]
        assert "OOMKilled" in result["summary"]

    def test_includes_actions(self, sample_summary_state):
        """Should include executed actions in summary."""
        result = generate_summary_node(sample_summary_state)

        assert "rollback" in result["summary"]
        assert "restart_pods" in result["summary"]


# ============================================================================
# Node Tests: post_to_slack_node
# ============================================================================


class TestPostToSlackNode:
    """
    Tests for the Slack posting node.
    """

    @pytest.mark.asyncio
    async def test_simulates_send_without_token(self, sample_summary_state):
        """Should simulate send when SLACK_BOT_TOKEN not configured."""
        with patch("backend.modules.summary.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None
            mock_settings.SLACK_DEFAULT_CHANNEL = "#incidents"

            result = await post_to_slack_node(sample_summary_state)

        assert "summary_message_ts" in result
        assert "simulated_" in result["summary_message_ts"]

    @pytest.mark.asyncio
    async def test_sends_to_slack_with_token(self, sample_summary_state):
        """Should send message to Slack when token is configured."""
        with patch("backend.modules.summary.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = "xoxb-test-token"
            mock_settings.SLACK_DEFAULT_CHANNEL = "#incidents"

            with patch("backend.modules.summary.nodes.SummarySlackClient") as MockClient:
                mock_instance = MagicMock()
                mock_instance.post_summary = AsyncMock(
                    return_value={"ok": True, "ts": "1234567890.123456"}
                )
                MockClient.return_value = mock_instance

                result = await post_to_slack_node(sample_summary_state)

        assert result.get("summary_message_ts") == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_handles_slack_error(self, sample_summary_state):
        """Should handle Slack API errors gracefully."""
        with patch("backend.modules.summary.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = "xoxb-test-token"
            mock_settings.SLACK_DEFAULT_CHANNEL = "#incidents"

            with patch("backend.modules.summary.nodes.SummarySlackClient") as MockClient:
                mock_instance = MagicMock()
                mock_instance.post_summary = AsyncMock(
                    return_value={"ok": False, "error": "channel_not_found"}
                )
                MockClient.return_value = mock_instance

                result = await post_to_slack_node(sample_summary_state)

        # Should return empty dict on error
        assert "summary_message_ts" not in result or result.get("summary_message_ts") is None


# ============================================================================
# Node Tests: create_postmortem_node
# ============================================================================


class TestCreatePostmortemNode:
    """
    Tests for the postmortem ticket creation node.
    """

    @pytest.mark.asyncio
    async def test_creates_postmortem_for_critical(self, critical_severity_state):
        """Should create postmortem for critical severity."""
        with patch("backend.modules.summary.nodes.settings") as mock_settings:
            mock_settings.JIRA_CONFIGURED = False

            result = await create_postmortem_node(critical_severity_state)

        assert "postmortem_ticket" in result
        assert result["postmortem_ticket"] is not None
        assert "POST-" in result["postmortem_ticket"]

    @pytest.mark.asyncio
    async def test_creates_postmortem_for_high(self, sample_summary_state):
        """Should create postmortem for high severity."""
        with patch("backend.modules.summary.nodes.settings") as mock_settings:
            mock_settings.JIRA_CONFIGURED = False

            result = await create_postmortem_node(sample_summary_state)

        assert result["postmortem_ticket"] is not None

    @pytest.mark.asyncio
    async def test_skips_postmortem_for_low(self, low_severity_state):
        """Should skip postmortem for low severity."""
        with patch("backend.modules.summary.nodes.settings") as mock_settings:
            mock_settings.JIRA_CONFIGURED = False

            result = await create_postmortem_node(low_severity_state)

        assert result["postmortem_ticket"] is None

    @pytest.mark.asyncio
    async def test_skips_postmortem_for_medium(self, sample_summary_state):
        """Should skip postmortem for medium severity."""
        state = {**sample_summary_state, "severity": "medium"}

        with patch("backend.modules.summary.nodes.settings") as mock_settings:
            mock_settings.JIRA_CONFIGURED = False

            result = await create_postmortem_node(state)

        assert result["postmortem_ticket"] is None

    @pytest.mark.asyncio
    async def test_uses_jira_when_configured(self, critical_severity_state, mock_jira_client):
        """Should use real Jira client when configured."""
        with patch("backend.modules.summary.nodes.settings") as mock_settings:
            mock_settings.JIRA_CONFIGURED = True
            mock_settings.JIRA_URL = "https://test.atlassian.net"
            mock_settings.JIRA_EMAIL = "test@test.com"
            mock_settings.JIRA_API_TOKEN = "test-token"
            mock_settings.JIRA_PROJECT_KEY = "POST"
            mock_settings.JIRA_POSTMORTEM_ISSUE_TYPE = "Task"
            mock_settings.SLACK_BOT_TOKEN = None

            with patch("backend.modules.summary.nodes.JiraClient") as MockJiraClient:
                MockJiraClient.return_value = mock_jira_client

                result = await create_postmortem_node(critical_severity_state)

        assert result["postmortem_ticket"] == "POST-123"

    @pytest.mark.asyncio
    async def test_handles_jira_error(self, critical_severity_state, mock_jira_client_error):
        """Should handle Jira API errors and fallback to mock."""
        with patch("backend.modules.summary.nodes.settings") as mock_settings:
            mock_settings.JIRA_CONFIGURED = True
            mock_settings.JIRA_URL = "https://test.atlassian.net"
            mock_settings.JIRA_EMAIL = "test@test.com"
            mock_settings.JIRA_API_TOKEN = "test-token"
            mock_settings.JIRA_PROJECT_KEY = "POST"
            mock_settings.JIRA_POSTMORTEM_ISSUE_TYPE = "Task"
            mock_settings.SLACK_BOT_TOKEN = None

            with patch("backend.modules.summary.nodes.JiraClient") as MockJiraClient:
                MockJiraClient.return_value = mock_jira_client_error

                result = await create_postmortem_node(critical_severity_state)

        # Should fallback to mock ticket
        assert "MOCK-" in result["postmortem_ticket"]


# ============================================================================
# Slack Client Tests
# ============================================================================


class TestSummarySlackClient:
    """
    Tests for the Summary Slack client.
    """

    def test_format_summary_blocks_structure(self):
        """Should create properly structured Block Kit message."""
        client = SummarySlackClient(token="xoxb-test", default_channel="#test")

        blocks = client.format_summary_blocks(
            incident_id="INC-001",
            summary="Test summary content",
            all_succeeded=True,
            resolution_time_seconds=600,
        )

        assert isinstance(blocks, list)
        assert len(blocks) > 0

        # Check for required block types
        block_types = [b["type"] for b in blocks]
        assert "header" in block_types
        assert "section" in block_types

    def test_format_summary_resolved_status(self):
        """Should show RESOLVED for successful incidents."""
        client = SummarySlackClient(token="xoxb-test")

        blocks = client.format_summary_blocks(
            incident_id="INC-001",
            summary="Test",
            all_succeeded=True,
            resolution_time_seconds=300,
        )

        header = next(b for b in blocks if b["type"] == "header")
        assert "RESOLVED" in header["text"]["text"]

    def test_format_summary_partial_status(self):
        """Should show PARTIALLY RESOLVED for failed incidents."""
        client = SummarySlackClient(token="xoxb-test")

        blocks = client.format_summary_blocks(
            incident_id="INC-001",
            summary="Test",
            all_succeeded=False,
            resolution_time_seconds=300,
        )

        header = next(b for b in blocks if b["type"] == "header")
        assert "PARTIALLY RESOLVED" in header["text"]["text"]

    def test_truncate_long_summary(self):
        """Should truncate very long summary text."""
        client = SummarySlackClient(token="xoxb-test")

        long_text = "x" * 5000
        truncated = client._truncate_for_slack(long_text, max_length=2900)

        assert len(truncated) <= 2900
        assert truncated.endswith("...")


# ============================================================================
# Jira Client Tests
# ============================================================================


class TestJiraClient:
    """
    Tests for the Jira client.
    """

    def test_format_duration(self):
        """Should format duration correctly."""
        client = JiraClient(
            url="https://test.atlassian.net",
            email="test@test.com",
            api_token="token",
        )

        assert client._format_duration(30) == "30 seconds"
        assert client._format_duration(120) == "2 minutes"
        assert client._format_duration(3600) == "1 hour"

    def test_build_description_adf_structure(self):
        """Should build valid ADF document structure."""
        client = JiraClient(
            url="https://test.atlassian.net",
            email="test@test.com",
            api_token="token",
        )

        adf = client._build_description_adf(
            incident_id="INC-001",
            severity="high",
            root_cause="Test root cause",
            evidence=["Evidence 1", "Evidence 2"],
            execution_results=[],
            resolution_time="15 minutes",
        )

        assert adf["type"] == "doc"
        assert adf["version"] == 1
        assert "content" in adf
        assert len(adf["content"]) > 0

    def test_build_description_includes_checklist(self):
        """Should include postmortem checklist in ADF."""
        client = JiraClient(
            url="https://test.atlassian.net",
            email="test@test.com",
            api_token="token",
        )

        adf = client._build_description_adf(
            incident_id="INC-001",
            severity="critical",
            root_cause="Test",
            evidence=[],
            execution_results=[],
            resolution_time="1 hour",
        )

        # Find taskList block
        task_lists = [c for c in adf["content"] if c.get("type") == "taskList"]
        assert len(task_lists) > 0


# ============================================================================
# Graph Structure Tests
# ============================================================================


class TestSummaryGraphStructure:
    """
    Tests for the summary graph structure.
    """

    def test_graph_builds_without_error(self):
        """Should build graph without errors."""
        graph = build_summary_subgraph()
        assert graph is not None

    def test_graph_has_required_nodes(self):
        """Should have all required nodes defined."""
        graph = build_summary_subgraph()

        node_names = list(graph.nodes.keys())

        expected_nodes = [
            "generate_summary",
            "post_to_slack",
            "create_postmortem",
        ]

        for node in expected_nodes:
            assert node in node_names, f"Missing node: {node}"

    def test_compiled_subgraph_exists(self):
        """Should have compiled subgraph available."""
        assert summary_subgraph is not None


# ============================================================================
# Integration Tests
# ============================================================================


class TestSummaryIntegration:
    """
    Integration tests for the complete summary workflow.
    """

    @pytest.mark.asyncio
    async def test_full_summary_flow_success(self, sample_summary_state):
        """Test complete summary flow with successful incident."""
        with patch("backend.modules.summary.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None
            mock_settings.SLACK_DEFAULT_CHANNEL = "#incidents"
            mock_settings.JIRA_CONFIGURED = False

            # Run through all nodes manually
            summary_result = generate_summary_node(sample_summary_state)
            state = {**sample_summary_state, **summary_result}

            slack_result = await post_to_slack_node(state)
            state = {**state, **slack_result}

            postmortem_result = await create_postmortem_node(state)
            state = {**state, **postmortem_result}

        # Verify final state
        assert state["summary"] is not None
        assert "RESOLVED" in state["summary"]
        assert state["resolution_time_seconds"] > 0
        assert state["postmortem_ticket"] is not None  # High severity

    @pytest.mark.asyncio
    async def test_full_summary_flow_failure(self, failed_execution_state):
        """Test complete summary flow with failed incident."""
        with patch("backend.modules.summary.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None
            mock_settings.SLACK_DEFAULT_CHANNEL = "#incidents"
            mock_settings.JIRA_CONFIGURED = False

            summary_result = generate_summary_node(failed_execution_state)
            state = {**failed_execution_state, **summary_result}

            slack_result = await post_to_slack_node(state)
            state = {**state, **slack_result}

            postmortem_result = await create_postmortem_node(state)
            state = {**state, **postmortem_result}

        # Verify final state
        assert "PARTIALLY RESOLVED" in state["summary"]
        assert state["postmortem_ticket"] is not None  # Critical severity

    @pytest.mark.asyncio
    async def test_full_summary_flow_low_severity(self, low_severity_state):
        """Test complete summary flow with low severity (no postmortem)."""
        with patch("backend.modules.summary.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None
            mock_settings.SLACK_DEFAULT_CHANNEL = "#incidents"
            mock_settings.JIRA_CONFIGURED = False

            summary_result = generate_summary_node(low_severity_state)
            state = {**low_severity_state, **summary_result}

            slack_result = await post_to_slack_node(state)
            state = {**state, **slack_result}

            postmortem_result = await create_postmortem_node(state)
            state = {**state, **postmortem_result}

        # Verify no postmortem for low severity
        assert state["postmortem_ticket"] is None


# ============================================================================
# State Preservation Tests
# ============================================================================


class TestStatePreservation:
    """
    Tests to ensure input state is preserved through the graph.
    """

    def test_input_state_preserved_in_summary(self, sample_summary_state):
        """Should preserve all input fields in summary result."""
        result = generate_summary_node(sample_summary_state)

        # Result should only add new fields, not modify input
        assert "summary" in result
        assert "resolution_time_seconds" in result

        # Input fields should still be accessible
        full_state = {**sample_summary_state, **result}
        assert full_state["incident_id"] == sample_summary_state["incident_id"]
        assert full_state["severity"] == sample_summary_state["severity"]
        assert full_state["root_cause"] == sample_summary_state["root_cause"]
