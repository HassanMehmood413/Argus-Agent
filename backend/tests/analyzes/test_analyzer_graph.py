"""
Tests for the Analyzer Subgraph.

Tests each node individually and the full graph execution using
real GPT-4o and Qdrant (no mocks).

Prerequisites:
    - OPENAI_API_KEY environment variable set
    - Qdrant running (default: http://localhost:6333)

Run with: pytest tests/analyzes/ -v
"""

import os
import pytest
from typing import Dict, Any

from backend.modules.analyzes.state import AnalyzerState
from backend.modules.analyzes.nodes.analyze_patterns import detect_patterns_node
from backend.modules.analyzes.nodes.similar_issues import (
    search_similar_node,
    QdrantIncidentStore,
    SEED_INCIDENTS,
)
from backend.modules.analyzes.nodes.llm_analyze import llm_analyze_node
from backend.modules.analyzes.nodes.actions_ask import (
    generate_actions_node,
    VALID_ACTION_TYPES,
    _generate_actions_fallback,
    PATTERN_ACTION_HINTS,
)
from backend.modules.analyzes.graph import build_analyzer_subgraph
from backend.config.settings import settings


# ============================================================================
# Node Tests: detect_patterns_node
# ============================================================================


class TestDetectPatternsNode:
    """
    Tests for the pattern detection node (rule-based, no LLM).
    """

    def test_detects_high_memory(self, sample_metrics):
        """Should detect high memory pattern."""
        state = {"metrics": sample_metrics}  # 92.3% memory

        result = detect_patterns_node(state)

        patterns = result["patterns"]
        pattern_types = [p["type"] for p in patterns]

        assert "high_memory" in pattern_types
        high_mem = next(p for p in patterns if p["type"] == "high_memory")
        assert high_mem["value"] == 92.3
        assert high_mem["severity"] == "high"

    def test_detects_oom_killed(self, sample_events):
        """Should detect OOM killed events."""
        state = {"events": sample_events}

        result = detect_patterns_node(state)

        patterns = result["patterns"]
        pattern_types = [p["type"] for p in patterns]

        assert "oom_killed" in pattern_types
        oom = next(p for p in patterns if p["type"] == "oom_killed")
        assert oom["severity"] == "critical"

    def test_detects_crash_loop(self, sample_pod_status):
        """Should detect crash loop from high restart count."""
        state = {"pod_status": sample_pod_status}

        result = detect_patterns_node(state)

        patterns = result["patterns"]
        pattern_types = [p["type"] for p in patterns]

        assert "crash_loop" in pattern_types
        # Should have detected pods with >5 restarts
        crash_patterns = [p for p in patterns if p["type"] == "crash_loop"]
        assert len(crash_patterns) >= 1

    def test_detects_pod_failures(self, sample_pod_status):
        """Should detect failed pods."""
        state = {"pod_status": sample_pod_status}

        result = detect_patterns_node(state)

        patterns = result["patterns"]
        pattern_types = [p["type"] for p in patterns]

        assert "pod_failures" in pattern_types
        pod_fail = next(p for p in patterns if p["type"] == "pod_failures")
        assert pod_fail["value"] == 2  # 2 failed pods

    def test_detects_high_error_rate(self):
        """Should detect high error rate."""
        state = {"metrics": {"error_rate_percent": 12.5}}

        result = detect_patterns_node(state)

        patterns = result["patterns"]
        pattern_types = [p["type"] for p in patterns]

        assert "high_error_rate" in pattern_types
        error = next(p for p in patterns if p["type"] == "high_error_rate")
        assert error["severity"] == "critical"  # >10% is critical

    def test_detects_high_latency(self):
        """Should detect high latency."""
        state = {"metrics": {"latency_p99_seconds": 2.5}}

        result = detect_patterns_node(state)

        patterns = result["patterns"]
        pattern_types = [p["type"] for p in patterns]

        assert "high_latency" in pattern_types
        latency = next(p for p in patterns if p["type"] == "high_latency")
        assert latency["severity"] == "high"  # >2.0s is high

    def test_detects_recent_deployment(self, sample_deployments):
        """Should detect recent deployments."""
        state = {"recent_deployments": sample_deployments}

        result = detect_patterns_node(state)

        patterns = result["patterns"]
        pattern_types = [p["type"] for p in patterns]

        assert "recent_deployment" in pattern_types

    def test_detects_connection_errors_in_logs(self):
        """Should detect connection errors from logs."""
        state = {
            "logs": [
                {"level": "ERROR", "message": "Connection refused to database"},
                {"level": "ERROR", "message": "Failed to establish connection"},
            ]
        }

        result = detect_patterns_node(state)

        patterns = result["patterns"]
        pattern_types = [p["type"] for p in patterns]

        assert "connection_errors" in pattern_types

    def test_no_patterns_for_healthy_metrics(self):
        """Should not detect patterns for healthy metrics."""
        state = {
            "metrics": {
                "cpu_usage_percent": 30.0,
                "memory_usage_percent": 40.0,
                "error_rate_percent": 0.5,
                "latency_p99_seconds": 0.2,
            },
            "pod_status": {"total": 3, "running": 3, "failed": 0, "pods": []},
            "events": [],
            "logs": [],
            "recent_deployments": [],
        }

        result = detect_patterns_node(state)

        # May have no patterns or only info-level
        critical_patterns = [
            p for p in result["patterns"]
            if p.get("severity") in ["critical", "high"]
        ]
        assert len(critical_patterns) == 0


# ============================================================================
# Node Tests: search_similar_node (Qdrant RAG)
# ============================================================================


class TestSearchSimilarNode:
    """
    Tests for the Qdrant RAG similarity search node.
    """

    @pytest.fixture(autouse=True)
    def setup(self, check_api_keys, check_qdrant):
        """Ensure API keys and Qdrant are available."""
        pass

    def test_finds_similar_oom_incidents(self):
        """Should find similar OOM incidents from Qdrant."""
        # Patterns that match OOM incident
        state = {
            "patterns": [
                {"type": "high_memory", "description": "Memory at 95%"},
                {"type": "oom_killed", "description": "OOM kill detected"},
                {"type": "crash_loop", "description": "Pods restarting"},
            ],
            "alert": {"service": "api-gateway"},
        }

        result = search_similar_node(state)

        similar = result["similar_incidents"]
        assert len(similar) > 0

        # Should find the API Gateway OOM incident
        incident_ids = [inc["id"] for inc in similar]
        # INC-2024-001 is the OOM crash incident
        assert any("001" in id or "005" in id for id in incident_ids)

    def test_finds_similar_latency_incidents(self):
        """Should find similar latency incidents from Qdrant."""
        state = {
            "patterns": [
                {"type": "high_latency", "description": "P99 latency 2.5s"},
                {"type": "high_cpu", "description": "CPU at 85%"},
                {"type": "connection_errors", "description": "DB connection issues"},
            ],
            "alert": {"service": "payment-service"},
        }

        result = search_similar_node(state)

        similar = result["similar_incidents"]
        assert len(similar) > 0

        # Should have similarity scores
        for inc in similar:
            assert "similarity" in inc
            assert 0.0 <= inc["similarity"] <= 1.0
            assert "root_cause" in inc
            assert "resolution" in inc

    def test_returns_empty_for_no_patterns(self):
        """Should return empty list when no patterns provided."""
        state = {"patterns": [], "alert": {}}

        result = search_similar_node(state)

        assert result["similar_incidents"] == []

    def test_search_respects_limit(self):
        """Should return at most 3 incidents."""
        state = {
            "patterns": [
                {"type": "high_cpu", "description": "High CPU"},
                {"type": "high_memory", "description": "High memory"},
            ],
            "alert": {},
        }

        result = search_similar_node(state)

        assert len(result["similar_incidents"]) <= 3


class TestQdrantIncidentStore:
    """
    Direct tests for the QdrantIncidentStore class.
    """

    @pytest.fixture(autouse=True)
    def setup(self, check_api_keys, check_qdrant, clean_test_collection):
        """Setup and cleanup test collection."""
        pass

    def test_create_collection_and_seed(self):
        """Should create collection and seed incidents."""
        from tests.analyzes.conftest import TEST_COLLECTION

        store = QdrantIncidentStore(collection_name=TEST_COLLECTION)
        store.ensure_collection()
        store.seed_incidents()

        # Verify collection exists with data
        info = store.client.get_collection(TEST_COLLECTION)
        assert info.points_count == len(SEED_INCIDENTS)

    def test_semantic_search_quality(self):
        """Test semantic search finds relevant results."""
        from tests.analyzes.conftest import TEST_COLLECTION

        store = QdrantIncidentStore(collection_name=TEST_COLLECTION)
        store.ensure_collection()
        store.seed_incidents()

        # Search for memory-related patterns
        patterns = [
            {"type": "high_memory", "description": "Memory usage at 95%"},
            {"type": "oom_killed", "description": "Out of memory kill event"},
        ]

        results = store.search_similar(patterns, limit=3)

        assert len(results) > 0
        # First result should be memory-related
        assert any(
            "memory" in r["title"].lower() or "oom" in r["title"].lower()
            for r in results
        )

    def test_add_incident(self):
        """Should add new incidents to store."""
        from tests.analyzes.conftest import TEST_COLLECTION

        store = QdrantIncidentStore(collection_name=TEST_COLLECTION)
        store.ensure_collection()

        initial_count = store.client.get_collection(TEST_COLLECTION).points_count

        new_incident = {
            "id": "INC-TEST-001",
            "title": "Test Incident",
            "patterns": ["test_pattern"],
            "root_cause": "Test root cause",
            "resolution": "Test resolution",
            "service": "test-service",
            "date": "2024-03-01",
            "description": "Test description",
        }

        store.add_incident(new_incident)

        new_count = store.client.get_collection(TEST_COLLECTION).points_count
        assert new_count == initial_count + 1


# ============================================================================
# Node Tests: llm_analyze_node (GPT-4o)
# ============================================================================


class TestLLMAnalyzeNode:
    """
    Tests for the GPT-4o LLM analysis node.
    """

    @pytest.fixture(autouse=True)
    def setup(self, check_api_keys):
        """Ensure OpenAI API key is available."""
        pass

    @pytest.mark.asyncio
    async def test_analyzes_oom_incident(self, oom_incident_state):
        """Should analyze OOM incident and identify root cause."""
        # First detect patterns
        patterns_result = detect_patterns_node(oom_incident_state)
        state = {**oom_incident_state, **patterns_result}

        # Add some similar incidents
        state["similar_incidents"] = [
            {
                "id": "INC-2024-001",
                "title": "API Gateway OOM Crash",
                "similarity": 0.85,
                "root_cause": "Memory leak due to unclosed connections",
                "resolution": "Rolled back deployment",
            }
        ]

        result = await llm_analyze_node(state)

        assert "root_cause" in result
        assert len(result["root_cause"]) > 10
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0
        assert "evidence" in result
        assert len(result["evidence"]) > 0
        assert "analysis_reasoning" in result

    @pytest.mark.asyncio
    async def test_analyzes_latency_incident(self, high_latency_state):
        """Should analyze latency incident."""
        patterns_result = detect_patterns_node(high_latency_state)
        state = {**high_latency_state, **patterns_result}
        state["similar_incidents"] = []

        result = await llm_analyze_node(state)

        assert "root_cause" in result
        assert "confidence" in result
        # Analysis should mention latency-related concepts
        reasoning = result["analysis_reasoning"].lower()
        assert any(
            term in reasoning
            for term in ["latency", "slow", "database", "connection", "timeout"]
        )

    @pytest.mark.asyncio
    async def test_analyzes_error_spike(self, error_spike_state):
        """Should analyze error rate spike incident."""
        patterns_result = detect_patterns_node(error_spike_state)
        state = {**error_spike_state, **patterns_result}
        state["similar_incidents"] = []

        result = await llm_analyze_node(state)

        assert "root_cause" in result
        assert "evidence" in result
        # Should have reasonable confidence for clear error patterns
        assert result["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_requires_openai_key(self):
        """Should raise error if OPENAI_API_KEY not set."""
        # Temporarily unset key
        original_key = os.environ.pop("OPENAI_API_KEY", None)

        try:
            state = {"patterns": [], "similar_incidents": []}
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                await llm_analyze_node(state)
        finally:
            # Restore key
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key


# ============================================================================
# Node Tests: generate_actions_node (Hybrid LLM + Fallback)
# ============================================================================


class TestGenerateActionsNode:
    """
    Tests for the action generation node (hybrid LLM + fallback).
    """

    @pytest.fixture(autouse=True)
    def setup(self, check_api_keys):
        """Ensure OpenAI API key is available."""
        pass

    @pytest.mark.asyncio
    async def test_generates_rollback_for_oom(self):
        """Should generate rollback action for OOM incidents."""
        state = {
            "patterns": [
                {"type": "oom_killed", "description": "OOM kill"},
                {"type": "high_memory", "description": "High memory"},
            ],
            "alert": {"service": "api-gateway", "namespace": "production"},
            "root_cause": "Memory leak in recent deployment",
            "confidence": 0.8,
            "severity": "critical",
            "similar_incidents": [],
            "recent_deployments": [{"name": "api-gateway", "image": "v2.3.1", "revision": 42}],
        }

        result = await generate_actions_node(state)

        actions = result["recommended_actions"]
        assert len(actions) > 0

        action_types = [a["type"] for a in actions]
        # LLM should suggest rollback or increase_resources for OOM
        assert any(t in action_types for t in ["rollback", "increase_resources", "restart_pods"])

        # Check action structure
        for action in actions:
            assert "type" in action
            assert "reason" in action
            assert "risk_level" in action
            assert action["type"] in VALID_ACTION_TYPES

    @pytest.mark.asyncio
    async def test_generates_restart_for_connection_errors(self):
        """Should generate restart action for connection errors."""
        state = {
            "patterns": [
                {"type": "connection_errors", "description": "DB connection failed"},
            ],
            "alert": {"service": "payment-service", "namespace": "default"},
            "root_cause": "Database connection pool exhausted",
            "confidence": 0.7,
            "severity": "medium",
            "similar_incidents": [],
            "recent_deployments": [],
        }

        result = await generate_actions_node(state)

        actions = result["recommended_actions"]
        action_types = [a["type"] for a in actions]

        assert "restart_pods" in action_types or "check_dependency" in action_types

    @pytest.mark.asyncio
    async def test_requires_approval_for_critical(self):
        """Should require approval for critical severity."""
        state = {
            "patterns": [{"type": "high_cpu", "description": "CPU spike"}],
            "alert": {"service": "test", "namespace": "prod"},
            "root_cause": "CPU intensive operation",
            "confidence": 0.9,
            "severity": "critical",
            "similar_incidents": [],
            "recent_deployments": [],
        }

        result = await generate_actions_node(state)

        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_requires_approval_for_low_confidence(self):
        """Should require approval when confidence is low."""
        state = {
            "patterns": [{"type": "high_cpu", "description": "CPU spike"}],
            "alert": {"service": "test", "namespace": "prod"},
            "root_cause": "Unknown cause",
            "confidence": 0.5,  # Low confidence
            "severity": "low",
            "similar_incidents": [],
            "recent_deployments": [],
        }

        result = await generate_actions_node(state)

        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_max_actions_limit(self):
        """Should return at most MAX_ACTIONS actions."""
        state = {
            "patterns": [
                {"type": "high_cpu", "description": "High CPU"},
                {"type": "high_memory", "description": "High memory"},
                {"type": "crash_loop", "description": "Crash loop"},
                {"type": "connection_errors", "description": "Connection errors"},
            ],
            "alert": {"service": "test", "namespace": "prod"},
            "root_cause": "Multiple issues detected",
            "confidence": 0.8,
            "severity": "high",
            "similar_incidents": [],
            "recent_deployments": [],
        }

        result = await generate_actions_node(state)

        assert len(result["recommended_actions"]) <= settings.MAX_ACTIONS

    @pytest.mark.asyncio
    async def test_llm_generates_contextual_actions(self):
        """LLM should generate actions based on root cause and similar incidents."""
        state = {
            "patterns": [
                {"type": "high_memory", "description": "Memory at 95%"},
                {"type": "crash_loop", "description": "Pods restarting frequently"},
            ],
            "alert": {"service": "api-gateway", "namespace": "production"},
            "root_cause": "Memory leak in v2.3.1 due to unclosed database connections",
            "confidence": 0.85,
            "severity": "high",
            "similar_incidents": [
                {
                    "id": "INC-2024-001",
                    "title": "API Gateway OOM Crash",
                    "similarity": 0.9,
                    "root_cause": "Memory leak due to unclosed connections",
                    "resolution": "Rolled back to v2.3.0, deployed hotfix",
                }
            ],
            "recent_deployments": [
                {"name": "api-gateway", "image": "api-gateway:v2.3.1", "revision": 42}
            ],
        }

        result = await generate_actions_node(state)

        actions = result["recommended_actions"]
        assert len(actions) > 0

        # Should have reasoning about why actions were chosen
        assert "actions_reasoning" in result

        # Actions should have expected_outcome and rollback_plan
        for action in actions:
            assert "expected_outcome" in action
            assert "source" in action  # Should indicate llm or fallback

    @pytest.mark.asyncio
    async def test_actions_include_new_fields(self):
        """Actions should include expected_outcome and rollback_plan."""
        state = {
            "patterns": [{"type": "high_latency", "description": "P99 > 2s"}],
            "alert": {"service": "payment-service", "namespace": "prod"},
            "root_cause": "Database slow queries",
            "confidence": 0.75,
            "severity": "medium",
            "similar_incidents": [],
            "recent_deployments": [],
        }

        result = await generate_actions_node(state)

        for action in result["recommended_actions"]:
            assert "expected_outcome" in action
            assert "rollback_plan" in action


class TestGenerateActionsFallback:
    """
    Tests for the fallback rule-based action generation.
    """

    def test_fallback_generates_actions_from_patterns(self):
        """Fallback should generate actions based on pattern hints."""
        state = {
            "patterns": [
                {"type": "high_cpu", "description": "CPU at 90%"},
                {"type": "recent_deployment", "description": "Deployed v2.0"},
            ],
            "alert": {"service": "test-service", "namespace": "default"},
            "confidence": 0.6,
            "severity": "medium",
            "similar_incidents": [],
        }

        result = _generate_actions_fallback(state)

        actions = result["recommended_actions"]
        assert len(actions) > 0

        action_types = [a["type"] for a in actions]
        # Should suggest scale_up or rollback for high_cpu + recent_deployment
        assert any(t in action_types for t in ["scale_up", "rollback"])

    def test_fallback_investigate_when_no_patterns(self):
        """Fallback should suggest investigate when no matching patterns."""
        state = {
            "patterns": [{"type": "unknown_pattern", "description": "Something weird"}],
            "alert": {"service": "test", "namespace": "default"},
            "confidence": 0.5,
            "severity": "low",
            "similar_incidents": [],
        }

        result = _generate_actions_fallback(state)

        actions = result["recommended_actions"]
        assert len(actions) > 0
        assert actions[0]["type"] == "investigate"

    def test_fallback_adds_similar_incident_note(self):
        """Fallback should add note from highly similar incidents."""
        state = {
            "patterns": [{"type": "high_memory", "description": "Memory high"}],
            "alert": {"service": "api-gateway", "namespace": "prod"},
            "confidence": 0.8,
            "severity": "medium",
            "similar_incidents": [
                {
                    "id": "INC-001",
                    "similarity": 0.85,
                    "resolution": "Restarted pods and scaled up",
                }
            ],
        }

        result = _generate_actions_fallback(state)

        actions = result["recommended_actions"]
        # First action should have a note about similar incident
        assert "note" in actions[0]
        assert "INC-001" in actions[0]["note"]


# ============================================================================
# Full Graph Integration Tests
# ============================================================================


class TestAnalyzerGraph:
    """
    Integration tests for the complete Analyzer subgraph.
    """

    @pytest.fixture(autouse=True)
    def setup(self, check_api_keys, check_qdrant):
        """Ensure all services are available."""
        pass

    @pytest.mark.asyncio
    async def test_full_graph_oom_incident(self, oom_incident_state):
        """Test full graph execution for OOM incident."""
        graph = build_analyzer_subgraph()

        result = await graph.ainvoke(oom_incident_state)

        # Verify all expected outputs are present
        assert "patterns" in result
        assert len(result["patterns"]) > 0

        assert "similar_incidents" in result

        assert "root_cause" in result
        assert len(result["root_cause"]) > 10

        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0

        assert "evidence" in result
        assert len(result["evidence"]) > 0

        assert "recommended_actions" in result
        assert len(result["recommended_actions"]) > 0

        assert "requires_approval" in result

    @pytest.mark.asyncio
    async def test_full_graph_latency_incident(self, high_latency_state):
        """Test full graph execution for latency incident."""
        graph = build_analyzer_subgraph()

        result = await graph.ainvoke(high_latency_state)

        # Should detect latency patterns
        pattern_types = [p["type"] for p in result["patterns"]]
        assert "high_latency" in pattern_types

        # Should have analysis
        assert result["root_cause"] != "Unable to determine root cause"
        assert result["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_full_graph_error_spike(self, error_spike_state):
        """Test full graph execution for error rate spike."""
        graph = build_analyzer_subgraph()

        result = await graph.ainvoke(error_spike_state)

        # Should detect error patterns
        pattern_types = [p["type"] for p in result["patterns"]]
        assert "high_error_rate" in pattern_types

        # Critical incidents should require approval
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_graph_handles_minimal_state(self):
        """Test graph handles minimal input gracefully."""
        graph = build_analyzer_subgraph()

        minimal_state = {
            "alert": {"service": "unknown", "alertname": "TestAlert"},
            "severity": "low",
            "metrics": {},
            "logs": [],
            "pod_status": {},
            "events": [],
            "recent_deployments": [],
        }

        result = await graph.ainvoke(minimal_state)

        # Should still produce valid output
        assert "patterns" in result
        assert "root_cause" in result
        assert "recommended_actions" in result

    @pytest.mark.asyncio
    async def test_graph_state_preserved(self, oom_incident_state):
        """Test that input state is preserved through graph."""
        graph = build_analyzer_subgraph()

        result = await graph.ainvoke(oom_incident_state)

        # Original state should be preserved
        assert result["alert"] == oom_incident_state["alert"]
        assert result["metrics"] == oom_incident_state["metrics"]
        assert result["severity"] == oom_incident_state["severity"]


# ============================================================================
# Performance/Reliability Tests
# ============================================================================


class TestAnalyzerReliability:
    """
    Tests for analyzer reliability and edge cases.
    """

    @pytest.fixture(autouse=True)
    def setup(self, check_api_keys, check_qdrant):
        """Ensure all services are available."""
        pass

    @pytest.mark.asyncio
    async def test_handles_empty_patterns(self):
        """Graph should handle case where no patterns detected."""
        graph = build_analyzer_subgraph()

        state = {
            "alert": {"service": "healthy-service"},
            "severity": "low",
            "metrics": {
                "cpu_usage_percent": 20,
                "memory_usage_percent": 30,
                "error_rate_percent": 0.1,
            },
            "logs": [],
            "pod_status": {"total": 3, "running": 3, "failed": 0, "pods": []},
            "events": [],
            "recent_deployments": [],
        }

        result = await graph.ainvoke(state)

        # Should still complete successfully
        assert "root_cause" in result
        assert "recommended_actions" in result

    @pytest.mark.asyncio
    async def test_handles_special_characters_in_logs(self):
        """Graph should handle special characters in log messages."""
        graph = build_analyzer_subgraph()

        state = {
            "alert": {"service": "test-service"},
            "severity": "medium",
            "metrics": {"error_rate_percent": 8.0},
            "logs": [
                {"level": "ERROR", "message": "Error: <xml>&amp;special</xml>"},
                {"level": "ERROR", "message": "Stack trace: at func() line 'x\"y'"},
            ],
            "pod_status": {},
            "events": [],
            "recent_deployments": [],
        }

        result = await graph.ainvoke(state)

        # Should complete without error
        assert "root_cause" in result

    @pytest.mark.asyncio
    async def test_consistent_output_structure(self, oom_incident_state):
        """Verify output structure is consistent across runs."""
        graph = build_analyzer_subgraph()

        result = await graph.ainvoke(oom_incident_state)

        # Check all expected keys exist
        expected_keys = [
            "alert",
            "severity",
            "metrics",
            "patterns",
            "similar_incidents",
            "root_cause",
            "confidence",
            "evidence",
            "analysis_reasoning",
            "recommended_actions",
            "requires_approval",
        ]

        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

        # Check types
        assert isinstance(result["patterns"], list)
        assert isinstance(result["similar_incidents"], list)
        assert isinstance(result["confidence"], float)
        assert isinstance(result["evidence"], list)
        assert isinstance(result["recommended_actions"], list)
        assert isinstance(result["requires_approval"], bool)
