"""
Tests for the Executor Subgraph.

Tests each node individually and the graph structure.
Uses mocked Kubernetes executor since we don't want to run real K8s commands during tests.

Run with: pytest tests/execution/ -v
"""

import pytest
from typing import Dict, Any
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from backend.modules.execution.state import ExecutorState
from backend.modules.execution.nodes import (
    validate_actions_node,
    prepare_next_action_node,
    request_approval_node,
    execute_action_node,
    notify_slack_node,
    record_result_node,
    record_skip_node,
    notify_skip_node,
    handle_abort_node,
    summarize_results_node,
    route_by_risk,
    route_after_approval,
    route_has_more_actions,
    requires_approval,
    get_action_risk_level,
    AUTO_EXECUTE_RISK_LEVELS,
    REQUIRE_APPROVAL_RISK_LEVELS,
)
from backend.modules.execution.graph import build_executor_subgraph


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestHelperFunctions:
    """
    Tests for helper functions.
    """

    def test_get_action_risk_level_default(self):
        """Should return medium as default risk level."""
        action = {"type": "restart_pods"}
        assert get_action_risk_level(action) == "medium"

    def test_get_action_risk_level_explicit(self):
        """Should return explicit risk level."""
        action = {"type": "restart_pods", "risk_level": "low"}
        assert get_action_risk_level(action) == "low"

    def test_requires_approval_low_risk(self):
        """Low risk actions should not require approval."""
        action = {"type": "restart_pods", "risk_level": "low"}
        assert requires_approval(action) is False

    def test_requires_approval_none_risk(self):
        """None risk actions should not require approval."""
        action = {"type": "check_dependency", "risk_level": "none"}
        assert requires_approval(action) is False

    def test_requires_approval_medium_risk(self):
        """Medium risk actions should require approval."""
        action = {"type": "rollback", "risk_level": "medium"}
        assert requires_approval(action) is True

    def test_requires_approval_high_risk(self):
        """High risk actions should require approval."""
        action = {"type": "scale_down", "risk_level": "high"}
        assert requires_approval(action) is True


# ============================================================================
# Node Tests: validate_actions_node
# ============================================================================


class TestValidateActionsNode:
    """
    Tests for the action validation node.
    """

    def test_validates_approved_actions(self, executor_state_approved):
        """Should validate approved actions and initialize state."""
        result = validate_actions_node(executor_state_approved)

        assert result["current_action_index"] == 0
        assert result["execution_results"] == []
        assert result["skipped_actions"] == []
        assert result["aborted"] is False

    def test_blocks_unapproved_actions(self, executor_state_not_approved):
        """Should block execution when actions not approved."""
        result = validate_actions_node(executor_state_not_approved)

        assert result["aborted"] is True
        assert "not approved" in result["execution_summary"].lower()

    def test_handles_empty_actions(self, executor_state_approved):
        """Should handle empty actions list."""
        state = {**executor_state_approved, "actions_to_execute": []}

        result = validate_actions_node(state)

        assert result["all_succeeded"] is True
        assert "No actions to execute" in result["execution_summary"]

    def test_filters_invalid_actions(self, executor_state_approved):
        """Should filter actions without type."""
        state = {
            **executor_state_approved,
            "actions_to_execute": [
                {"action_id": "1", "type": "restart_pods", "risk_level": "low"},
                {"action_id": "2"},  # Missing type
                {"type": "rollback", "risk_level": "medium"},  # Missing action_id (auto-assigned)
            ],
        }

        result = validate_actions_node(state)

        # Should have 2 valid actions (one filtered, one auto-assigned ID)
        assert len(result["actions_to_execute"]) == 2


# ============================================================================
# Node Tests: prepare_next_action_node
# ============================================================================


class TestPrepareNextActionNode:
    """
    Tests for the action preparation node.
    """

    def test_prepares_first_action(self, executor_state_approved):
        """Should prepare the first action."""
        state = {**executor_state_approved, "current_action_index": 0}

        result = prepare_next_action_node(state)

        assert result["current_action"] is not None
        assert result["current_action"]["action_id"] == "1"
        assert result["action_decision"] is None
        assert result["awaiting_approval"] is False

    def test_prepares_second_action(self, executor_state_approved):
        """Should prepare the second action."""
        state = {**executor_state_approved, "current_action_index": 1}

        result = prepare_next_action_node(state)

        assert result["current_action"]["action_id"] == "2"

    def test_handles_no_more_actions(self, executor_state_approved):
        """Should handle when all actions are processed."""
        state = {
            **executor_state_approved,
            "current_action_index": len(executor_state_approved["actions_to_execute"]),
        }

        result = prepare_next_action_node(state)

        assert result["current_action"] is None


# ============================================================================
# Node Tests: request_approval_node (interrupt)
# ============================================================================


class TestRequestApprovalNode:
    """
    Tests for the human-in-the-loop approval node.
    """

    def test_interrupt_payload_structure(self, executor_state_approved, sample_actions_mixed_risk):
        """Should create proper interrupt payload."""
        state = {
            **executor_state_approved,
            "actions_to_execute": sample_actions_mixed_risk,
            "current_action_index": 1,
            "current_action": sample_actions_mixed_risk[1],  # medium risk rollback
        }

        with patch("backend.modules.execution.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None

            with patch("backend.modules.execution.nodes.interrupt") as mock_interrupt:
                mock_interrupt.return_value = "execute"

                result = request_approval_node(state)

        # Verify interrupt was called with expected structure
        mock_interrupt.assert_called_once()
        call_args = mock_interrupt.call_args[0][0]

        assert call_args["type"] == "execution_approval"
        assert call_args["incident_id"] == state["incident_id"]
        assert call_args["action_index"] == 1
        assert "action" in call_args
        assert "options" in call_args

    def test_processes_execute_decision(self, executor_state_approved, sample_actions_mixed_risk):
        """Should process execute decision."""
        state = {
            **executor_state_approved,
            "actions_to_execute": sample_actions_mixed_risk,
            "current_action_index": 1,
            "current_action": sample_actions_mixed_risk[1],
        }

        with patch("backend.modules.execution.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None

            with patch("backend.modules.execution.nodes.interrupt") as mock_interrupt:
                mock_interrupt.return_value = "execute"

                result = request_approval_node(state)

        assert result["action_decision"] == "execute"

    def test_processes_skip_decision(self, executor_state_approved, sample_actions_mixed_risk):
        """Should process skip decision."""
        state = {
            **executor_state_approved,
            "actions_to_execute": sample_actions_mixed_risk,
            "current_action_index": 1,
            "current_action": sample_actions_mixed_risk[1],
        }

        with patch("backend.modules.execution.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None

            with patch("backend.modules.execution.nodes.interrupt") as mock_interrupt:
                mock_interrupt.return_value = "skip"

                result = request_approval_node(state)

        assert result["action_decision"] == "skip"

    def test_processes_abort_decision(self, executor_state_approved, sample_actions_mixed_risk):
        """Should process abort decision."""
        state = {
            **executor_state_approved,
            "actions_to_execute": sample_actions_mixed_risk,
            "current_action_index": 1,
            "current_action": sample_actions_mixed_risk[1],
        }

        with patch("backend.modules.execution.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None

            with patch("backend.modules.execution.nodes.interrupt") as mock_interrupt:
                mock_interrupt.return_value = "abort"

                result = request_approval_node(state)

        assert result["action_decision"] == "abort"


# ============================================================================
# Node Tests: execute_action_node
# ============================================================================


class TestExecuteActionNode:
    """
    Tests for the action execution node.
    """

    @pytest.mark.asyncio
    async def test_executes_action_successfully(
        self, executor_state_approved, mock_kubernetes_executor
    ):
        """Should execute action and return result."""
        state = {
            **executor_state_approved,
            "current_action": executor_state_approved["actions_to_execute"][0],
        }

        with patch("backend.modules.execution.nodes.get_executor") as mock_get_executor:
            mock_get_executor.return_value = mock_kubernetes_executor

            with patch("backend.modules.execution.nodes.execute_action") as mock_execute:
                mock_execute.return_value = {
                    "success": True,
                    "output": "Action completed",
                    "action_id": "1",
                    "action_type": "check_dependency",
                }

                result = await execute_action_node(state)

        assert "last_execution_result" in result
        assert result["last_execution_result"]["success"] is True

    @pytest.mark.asyncio
    async def test_handles_execution_failure(
        self, executor_state_approved, mock_kubernetes_executor_failure
    ):
        """Should handle execution failure gracefully."""
        state = {
            **executor_state_approved,
            "current_action": executor_state_approved["actions_to_execute"][0],
        }

        with patch("backend.modules.execution.nodes.get_executor") as mock_get_executor:
            mock_get_executor.return_value = mock_kubernetes_executor_failure

            with patch("backend.modules.execution.nodes.execute_action") as mock_execute:
                mock_execute.return_value = {
                    "success": False,
                    "error": "Execution failed",
                    "action_id": "1",
                    "action_type": "check_dependency",
                }

                result = await execute_action_node(state)

        assert result["last_execution_result"]["success"] is False

    @pytest.mark.asyncio
    async def test_handles_exception(self, executor_state_approved):
        """Should handle exceptions during execution."""
        state = {
            **executor_state_approved,
            "current_action": executor_state_approved["actions_to_execute"][0],
        }

        with patch("backend.modules.execution.nodes.get_executor") as mock_get_executor:
            with patch("backend.modules.execution.nodes.execute_action") as mock_execute:
                mock_execute.side_effect = Exception("Connection failed")

                result = await execute_action_node(state)

        assert result["last_execution_result"]["success"] is False
        assert "Connection failed" in result["last_execution_result"]["error"]


# ============================================================================
# Node Tests: record_result_node
# ============================================================================


class TestRecordResultNode:
    """
    Tests for the result recording node.
    """

    def test_records_success(self, executor_state_approved, execution_result_success):
        """Should record successful execution result."""
        state = {
            **executor_state_approved,
            "current_action": executor_state_approved["actions_to_execute"][0],
            "last_execution_result": execution_result_success,
            "execution_results": [],
        }

        result = record_result_node(state)

        assert len(result["execution_results"]) == 1
        assert result["execution_results"][0]["success"] is True
        assert result["current_action_index"] == 1
        assert result["failed_action"] is None

    def test_records_failure_with_stop(self, executor_state_approved, execution_result_failure):
        """Should record failure and set failed_action when stop_on_failure=True."""
        state = {
            **executor_state_approved,
            "current_action": executor_state_approved["actions_to_execute"][0],
            "last_execution_result": execution_result_failure,
            "execution_results": [],
            "stop_on_failure": True,
        }

        result = record_result_node(state)

        assert len(result["execution_results"]) == 1
        assert result["execution_results"][0]["success"] is False
        assert result["failed_action"] is not None

    def test_records_failure_without_stop(self, executor_state_approved, execution_result_failure):
        """Should record failure without setting failed_action when stop_on_failure=False."""
        state = {
            **executor_state_approved,
            "current_action": executor_state_approved["actions_to_execute"][0],
            "last_execution_result": execution_result_failure,
            "execution_results": [],
            "stop_on_failure": False,
        }

        with patch("backend.modules.execution.nodes.settings") as mock_settings:
            mock_settings.EXECUTION_STOP_ON_FAILURE = False

            result = record_result_node(state)

        assert result["failed_action"] is None


# ============================================================================
# Node Tests: record_skip_node
# ============================================================================


class TestRecordSkipNode:
    """
    Tests for the skip recording node.
    """

    def test_records_skip(self, executor_state_approved):
        """Should record skipped action."""
        state = {
            **executor_state_approved,
            "current_action": executor_state_approved["actions_to_execute"][0],
            "skipped_actions": [],
        }

        result = record_skip_node(state)

        assert len(result["skipped_actions"]) == 1
        assert "skipped_at" in result["skipped_actions"][0]
        assert result["current_action_index"] == 1


# ============================================================================
# Node Tests: handle_abort_node
# ============================================================================


class TestHandleAbortNode:
    """
    Tests for the abort handling node.
    """

    @pytest.mark.asyncio
    async def test_sets_aborted_flag(self, executor_state_approved):
        """Should set aborted flag."""
        state = {
            **executor_state_approved,
            "current_action_index": 1,
        }

        with patch("backend.modules.execution.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None

            result = await handle_abort_node(state)

        assert result["aborted"] is True


# ============================================================================
# Node Tests: summarize_results_node
# ============================================================================


class TestSummarizeResultsNode:
    """
    Tests for the results summarization node.
    """

    def test_summarizes_all_success(self, executor_state_approved, execution_result_success):
        """Should summarize all successful executions."""
        state = {
            **executor_state_approved,
            "execution_results": [execution_result_success],
            "skipped_actions": [],
            "aborted": False,
            "failed_action": None,
        }

        result = summarize_results_node(state)

        assert result["all_succeeded"] is True
        assert "✅" in result["execution_summary"]
        assert "Successfully" in result["execution_summary"]

    def test_summarizes_with_failures(
        self, executor_state_approved, execution_result_success, execution_result_failure
    ):
        """Should summarize with failures."""
        state = {
            **executor_state_approved,
            "execution_results": [execution_result_success, execution_result_failure],
            "skipped_actions": [],
            "aborted": False,
            "failed_action": None,
        }

        result = summarize_results_node(state)

        assert result["all_succeeded"] is False
        assert "Issues" in result["execution_summary"] or "❌" in result["execution_summary"]

    def test_summarizes_aborted(self, executor_state_approved):
        """Should summarize aborted execution."""
        state = {
            **executor_state_approved,
            "execution_results": [],
            "skipped_actions": [],
            "aborted": True,
        }

        result = summarize_results_node(state)

        assert result["all_succeeded"] is False
        assert "Aborted" in result["execution_summary"]

    def test_summarizes_with_skipped(self, executor_state_approved, execution_result_success):
        """Should include skipped actions in summary."""
        state = {
            **executor_state_approved,
            "execution_results": [execution_result_success],
            "skipped_actions": [{"type": "rollback", "action_id": "2"}],
            "aborted": False,
        }

        result = summarize_results_node(state)

        assert "Skipped" in result["execution_summary"]

    def test_summarizes_dry_run(self, executor_state_dry_run, execution_result_success):
        """Should indicate dry run in summary."""
        state = {
            **executor_state_dry_run,
            "execution_results": [execution_result_success],
            "skipped_actions": [],
            "aborted": False,
        }

        result = summarize_results_node(state)

        assert "DRY RUN" in result["execution_summary"]


# ============================================================================
# Routing Function Tests
# ============================================================================


class TestRoutingFunctions:
    """
    Tests for routing functions.
    """

    def test_route_by_risk_low(self, executor_state_approved):
        """Low risk should route to execute."""
        state = {
            **executor_state_approved,
            "current_action": {"type": "restart_pods", "risk_level": "low"},
        }

        result = route_by_risk(state)
        assert result == "execute_action"

    def test_route_by_risk_none(self, executor_state_approved):
        """None risk should route to execute."""
        state = {
            **executor_state_approved,
            "current_action": {"type": "check_dependency", "risk_level": "none"},
        }

        result = route_by_risk(state)
        assert result == "execute_action"

    def test_route_by_risk_medium(self, executor_state_approved):
        """Medium risk should route to approval."""
        state = {
            **executor_state_approved,
            "current_action": {"type": "rollback", "risk_level": "medium"},
        }

        result = route_by_risk(state)
        assert result == "request_approval"

    def test_route_by_risk_high(self, executor_state_approved):
        """High risk should route to approval."""
        state = {
            **executor_state_approved,
            "current_action": {"type": "scale_down", "risk_level": "high"},
        }

        result = route_by_risk(state)
        assert result == "request_approval"

    def test_route_after_approval_execute(self, executor_state_approved):
        """Execute decision should route to execute."""
        state = {**executor_state_approved, "action_decision": "execute"}

        result = route_after_approval(state)
        assert result == "execute_action"

    def test_route_after_approval_skip(self, executor_state_approved):
        """Skip decision should route to record_skip."""
        state = {**executor_state_approved, "action_decision": "skip"}

        result = route_after_approval(state)
        assert result == "record_skip"

    def test_route_after_approval_abort(self, executor_state_approved):
        """Abort decision should route to handle_abort."""
        state = {**executor_state_approved, "action_decision": "abort"}

        result = route_after_approval(state)
        assert result == "handle_abort"

    def test_route_has_more_actions_yes(self, executor_state_approved):
        """Should route to prepare_next when more actions exist."""
        state = {
            **executor_state_approved,
            "current_action_index": 0,  # 2 actions, index 0 means 1 more
        }

        result = route_has_more_actions(state)
        assert result == "prepare_next_action"

    def test_route_has_more_actions_no(self, executor_state_approved):
        """Should route to summarize when no more actions."""
        state = {
            **executor_state_approved,
            "current_action_index": 2,  # 2 actions, all processed
        }

        result = route_has_more_actions(state)
        assert result == "summarize_results"

    def test_route_has_more_actions_aborted(self, executor_state_approved):
        """Should route to summarize when aborted."""
        state = {
            **executor_state_approved,
            "current_action_index": 0,
            "aborted": True,
        }

        result = route_has_more_actions(state)
        assert result == "summarize_results"

    def test_route_has_more_actions_failed(self, executor_state_approved):
        """Should route to summarize when failed with stop_on_failure."""
        state = {
            **executor_state_approved,
            "current_action_index": 0,
            "failed_action": {"type": "rollback"},
        }

        result = route_has_more_actions(state)
        assert result == "summarize_results"


# ============================================================================
# Graph Structure Tests
# ============================================================================


class TestExecutorGraphStructure:
    """
    Tests for the executor graph structure.
    """

    def test_graph_builds_without_error(self):
        """Should build graph without errors."""
        graph = build_executor_subgraph()
        assert graph is not None

    def test_graph_has_required_nodes(self):
        """Should have all required nodes defined."""
        graph = build_executor_subgraph()

        node_names = list(graph.nodes.keys())

        expected_nodes = [
            "validate_actions",
            "prepare_next_action",
            "request_approval",
            "execute_action",
            "notify_slack",
            "record_result",
            "record_skip",
            "notify_skip",
            "handle_abort",
            "summarize_results",
        ]

        for node in expected_nodes:
            assert node in node_names, f"Missing node: {node}"


# ============================================================================
# Integration Tests
# ============================================================================


class TestExecutorIntegration:
    """
    Integration tests for the executor workflow.
    """

    @pytest.mark.asyncio
    async def test_low_risk_actions_auto_execute(self, executor_state_approved):
        """Low risk actions should auto-execute without approval."""
        # Validate
        validate_result = validate_actions_node(executor_state_approved)
        state = {**executor_state_approved, **validate_result}

        # Prepare first action
        prepare_result = prepare_next_action_node(state)
        state = {**state, **prepare_result}

        # Check routing - should go to execute (low risk)
        route = route_by_risk(state)
        assert route == "execute_action"

    @pytest.mark.asyncio
    async def test_full_execution_flow(self, executor_state_approved):
        """Test complete execution flow for low risk actions."""
        # 1. Validate
        validate_result = validate_actions_node(executor_state_approved)
        state = {**executor_state_approved, **validate_result}

        # 2. Prepare first action
        prepare_result = prepare_next_action_node(state)
        state = {**state, **prepare_result}

        # 3. Execute action (mocked)
        with patch("backend.modules.execution.nodes.get_executor") as mock_get_executor:
            with patch("backend.modules.execution.nodes.execute_action") as mock_execute:
                mock_execute.return_value = {
                    "success": True,
                    "output": "Done",
                    "action_id": "1",
                    "action_type": "check_dependency",
                }
                exec_result = await execute_action_node(state)
                state = {**state, **exec_result}

        # 4. Notify Slack (mocked)
        with patch("backend.modules.execution.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None
            notify_result = await notify_slack_node(state)
            state = {**state, **notify_result}

        # 5. Record result
        record_result = record_result_node(state)
        state = {**state, **record_result}

        assert len(state["execution_results"]) == 1
        assert state["current_action_index"] == 1

    @pytest.mark.asyncio
    async def test_abort_stops_execution(self, executor_state_approved, sample_actions_mixed_risk):
        """Abort decision should stop all execution."""
        state = {
            **executor_state_approved,
            "actions_to_execute": sample_actions_mixed_risk,
            "current_action_index": 1,
            "current_action": sample_actions_mixed_risk[1],
            "action_decision": "abort",
        }

        # Handle abort
        with patch("backend.modules.execution.nodes.settings") as mock_settings:
            mock_settings.SLACK_BOT_TOKEN = None
            abort_result = await handle_abort_node(state)
            state = {**state, **abort_result}

        # Summarize
        summary_result = summarize_results_node(state)
        state = {**state, **summary_result}

        assert state["aborted"] is True
        assert state["all_succeeded"] is False
        assert "Aborted" in state["execution_summary"]
