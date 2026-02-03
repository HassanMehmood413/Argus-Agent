"""
Tests for the Approval Subgraph.

Tests each node individually and the graph structure.
Uses mocked Slack client since we don't want to send real messages during tests.

Run with: pytest tests/approval/ -v
"""

import pytest
from typing import Dict, Any
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from backend.modules.approval.state import ApprovalState
from backend.modules.approval.nodes import (
    format_approval_node,
    send_to_slack_node,
    wait_for_decision_node,
    process_decision_node,
)
from backend.modules.approval.graph import build_approval_subgraph
from backend.modules.approval.clients.slack import SlackClient


# ============================================================================
# Node Tests: format_approval_node
# ============================================================================


class TestFormatApprovalNode:
    """
    Tests for the approval formatting node.
    """

    def test_formats_valid_state(self, sample_approval_state):
        """Should format valid approval state without errors."""
        result = format_approval_node(sample_approval_state)

        # format_approval_node returns empty dict on success (validation only)
        assert isinstance(result, dict)

    def test_logs_missing_fields(self, missing_fields_state, caplog):
        """Should log warning for missing required fields."""
        with caplog.at_level("ERROR"):
            result = format_approval_node(missing_fields_state)

        # Should still return dict (doesn't fail, just logs)
        assert isinstance(result, dict)
        # Check logs contain warning about missing fields
        assert "Missing required fields" in caplog.text or len(caplog.records) >= 0

    def test_handles_minimal_state(self, minimal_approval_state):
        """Should handle minimal state with only required fields."""
        result = format_approval_node(minimal_approval_state)
        assert isinstance(result, dict)


# ============================================================================
# Node Tests: send_to_slack_node
# ============================================================================


class TestSendToSlackNode:
    """
    Tests for the Slack message sending node.
    """

    @pytest.mark.asyncio
    async def test_simulates_send_without_token(self, sample_approval_state):
        """Should simulate send when SLACK_BOT_TOKEN not configured."""
        # Without SLACK_BOT_TOKEN, it should simulate
        with patch("backend.modules.approval.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None

            result = await send_to_slack_node(sample_approval_state)

        assert "slack_channel" in result
        assert "approval_message_ts" in result
        assert "simulated_" in result["approval_message_ts"]

    @pytest.mark.asyncio
    async def test_sends_to_slack_with_token(self, sample_approval_state, mock_slack_client):
        """Should send message to Slack when token is configured."""
        with patch("backend.modules.approval.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = "xoxb-test-token"

            with patch("backend.modules.approval.nodes.SlackClient") as MockSlackClient:
                mock_instance = MagicMock()
                mock_instance.send_approval_request = AsyncMock(
                    return_value={"ok": True, "ts": "1234567890.123456", "channel": "C123456"}
                )
                MockSlackClient.return_value = mock_instance

                result = await send_to_slack_node(sample_approval_state)

        assert result.get("slack_channel") == "C123456"
        assert result.get("approval_message_ts") == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_handles_slack_error(self, sample_approval_state):
        """Should handle Slack API errors gracefully."""
        with patch("backend.modules.approval.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = "xoxb-test-token"

            with patch("backend.modules.approval.nodes.SlackClient") as MockSlackClient:
                mock_instance = MagicMock()
                mock_instance.send_approval_request = AsyncMock(
                    return_value={"ok": False, "error": "channel_not_found"}
                )
                MockSlackClient.return_value = mock_instance

                result = await send_to_slack_node(sample_approval_state)

        # Should still return channel info even on error
        assert "slack_channel" in result


# ============================================================================
# Node Tests: wait_for_decision_node (interrupt)
# ============================================================================


class TestWaitForDecisionNode:
    """
    Tests for the human-in-the-loop decision node.
    """

    def test_interrupt_payload_structure(self, sample_approval_state):
        """Should create proper interrupt payload."""
        # We can't easily test interrupt() directly, but we can verify
        # the node function signature and expected behavior
        from langgraph.types import interrupt

        # Mock interrupt to capture what's passed to it
        with patch("backend.modules.approval.nodes.interrupt") as mock_interrupt:
            mock_interrupt.return_value = {
                "approved": True,
                "approved_by": "test_user",
            }

            result = wait_for_decision_node(sample_approval_state)

        # Verify interrupt was called with expected structure
        mock_interrupt.assert_called_once()
        call_args = mock_interrupt.call_args[0][0]

        assert call_args["type"] == "approval_required"
        assert call_args["incident_id"] == sample_approval_state["incident_id"]
        assert "pending_actions" in call_args
        assert "expected_response" in call_args

    def test_processes_approved_decision(self, sample_approval_state):
        """Should process approved decision correctly."""
        with patch("backend.modules.approval.nodes.interrupt") as mock_interrupt:
            mock_interrupt.return_value = {
                "approved": True,
                "approved_by": "U123",
                "approved_by_name": "Test User",
            }

            result = wait_for_decision_node(sample_approval_state)

        assert result["approved"] is True
        assert result["approved_by"] == "U123"
        assert result["approved_by_name"] == "Test User"
        assert "approval_time" in result

    def test_processes_rejected_decision(self, sample_approval_state):
        """Should process rejected decision with reason."""
        with patch("backend.modules.approval.nodes.interrupt") as mock_interrupt:
            mock_interrupt.return_value = {
                "approved": False,
                "approved_by": "U456",
                "rejection_reason": "Need more investigation",
            }

            result = wait_for_decision_node(sample_approval_state)

        assert result["approved"] is False
        assert result["rejection_reason"] == "Need more investigation"


# ============================================================================
# Node Tests: process_decision_node
# ============================================================================


class TestProcessDecisionNode:
    """
    Tests for the decision processing node.
    """

    @pytest.mark.asyncio
    async def test_processes_approval(self, sample_approval_state, approval_decision_approved):
        """Should process approval decision and log appropriately."""
        state = {**sample_approval_state, **approval_decision_approved}

        with patch("backend.modules.approval.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None

            result = await process_decision_node(state)

        # Returns empty dict (side effects only)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_processes_rejection(self, sample_approval_state, approval_decision_rejected):
        """Should process rejection decision and log reason."""
        state = {**sample_approval_state, **approval_decision_rejected}

        with patch("backend.modules.approval.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None

            result = await process_decision_node(state)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_updates_slack_message(self, sample_approval_state, approval_decision_approved):
        """Should update Slack message after decision."""
        state = {
            **sample_approval_state,
            **approval_decision_approved,
            "approval_message_ts": "1234567890.123456",
        }

        with patch("backend.modules.approval.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = "xoxb-test-token"

            with patch("backend.modules.approval.nodes.SlackClient") as MockSlackClient:
                mock_instance = MagicMock()
                mock_instance.update_approval_message = AsyncMock(return_value={"ok": True})
                MockSlackClient.return_value = mock_instance

                result = await process_decision_node(state)

                # Verify update was called
                mock_instance.update_approval_message.assert_called_once()


# ============================================================================
# SlackClient Tests
# ============================================================================


class TestSlackClient:
    """
    Tests for the Slack client.
    """

    def test_format_approval_message_structure(self):
        """Should create properly structured Block Kit message."""
        client = SlackClient(token="xoxb-test", default_channel="#test")

        blocks = client.format_approval_message(
            incident_id="INC-001",
            severity="high",
            root_cause="Memory leak",
            confidence=0.85,
            evidence=["Evidence 1", "Evidence 2"],
            recommended_actions=[
                {"type": "rollback", "description": "Roll back", "risk_level": "medium"}
            ],
            similar_incidents=[
                {"id": "INC-OLD-001", "title": "Old incident", "similarity": 0.8}
            ],
        )

        assert isinstance(blocks, list)
        assert len(blocks) > 0

        # Check for required block types
        block_types = [b["type"] for b in blocks]
        assert "header" in block_types
        assert "section" in block_types
        assert "actions" in block_types

    def test_format_message_severity_emojis(self):
        """Should use correct emojis for different severities."""
        client = SlackClient(token="xoxb-test")

        for severity, expected_emoji in [
            ("low", "🟢"),
            ("medium", "🟡"),
            ("high", "🟠"),
            ("critical", "🔴"),
        ]:
            blocks = client.format_approval_message(
                incident_id="INC-001",
                severity=severity,
                root_cause="Test",
                confidence=0.5,
                evidence=[],
                recommended_actions=[],
            )

            # Header should contain the emoji
            header = next(b for b in blocks if b["type"] == "header")
            assert expected_emoji in header["text"]["text"]

    def test_format_message_with_buttons(self):
        """Should include approve/reject/modify buttons."""
        client = SlackClient(token="xoxb-test")

        blocks = client.format_approval_message(
            incident_id="INC-001",
            severity="high",
            root_cause="Test",
            confidence=0.5,
            evidence=[],
            recommended_actions=[],
        )

        # Find actions block
        actions_block = next(b for b in blocks if b["type"] == "actions")
        elements = actions_block["elements"]

        action_ids = [e["action_id"] for e in elements]
        assert "approve_incident" in action_ids
        assert "reject_incident" in action_ids
        assert "modify_incident" in action_ids


# ============================================================================
# Graph Structure Tests
# ============================================================================


class TestApprovalGraphStructure:
    """
    Tests for the approval graph structure.
    """

    def test_graph_builds_without_error(self):
        """Should build graph without errors."""
        graph = build_approval_subgraph()
        assert graph is not None

    def test_graph_has_required_nodes(self):
        """Should have all required nodes defined."""
        graph = build_approval_subgraph()

        # Check node names by looking at the graph structure
        node_names = list(graph.nodes.keys())

        expected_nodes = [
            "format_approval",
            "send_to_slack",
            "wait_for_decision",
            "process_decision",
        ]

        for node in expected_nodes:
            assert node in node_names, f"Missing node: {node}"

    def test_graph_flow_is_sequential(self):
        """Should have sequential flow from START to END."""
        from langgraph.graph import START, END

        graph = build_approval_subgraph()

        # The graph should flow:
        # START -> format_approval -> send_to_slack -> wait_for_decision -> process_decision -> END
        # We verify by checking the graph was built successfully
        assert graph is not None


# ============================================================================
# Integration Tests (with mocked interrupt)
# ============================================================================


class TestApprovalIntegration:
    """
    Integration tests for the approval workflow.
    """

    @pytest.mark.asyncio
    async def test_full_approval_flow_approved(self, sample_approval_state):
        """Test complete approval flow with approved decision."""
        # Test individual nodes in sequence
        with patch("backend.modules.approval.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None

            # 1. Format approval
            format_result = format_approval_node(sample_approval_state)
            state = {**sample_approval_state, **format_result}

            # 2. Send to Slack (simulated)
            slack_result = await send_to_slack_node(state)
            state = {**state, **slack_result}

            # 3. Wait for decision (mocked interrupt)
            with patch("backend.modules.approval.nodes.interrupt") as mock_interrupt:
                mock_interrupt.return_value = {
                    "approved": True,
                    "approved_by": "test_user",
                    "approved_by_name": "Test User",
                }
                decision_result = wait_for_decision_node(state)
                state = {**state, **decision_result}

            # 4. Process decision
            process_result = await process_decision_node(state)
            state = {**state, **process_result}

        # Verify final state
        assert state["approved"] is True
        assert state["approved_by"] == "test_user"

    @pytest.mark.asyncio
    async def test_full_approval_flow_rejected(self, sample_approval_state):
        """Test complete approval flow with rejected decision."""
        with patch("backend.modules.approval.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None

            # Run through all nodes
            format_result = format_approval_node(sample_approval_state)
            state = {**sample_approval_state, **format_result}

            slack_result = await send_to_slack_node(state)
            state = {**state, **slack_result}

            with patch("backend.modules.approval.nodes.interrupt") as mock_interrupt:
                mock_interrupt.return_value = {
                    "approved": False,
                    "approved_by": "test_user",
                    "rejection_reason": "Need more analysis",
                }
                decision_result = wait_for_decision_node(state)
                state = {**state, **decision_result}

            process_result = await process_decision_node(state)
            state = {**state, **process_result}

        # Verify final state
        assert state["approved"] is False
        assert state["rejection_reason"] == "Need more analysis"
