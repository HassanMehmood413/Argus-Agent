# test_monitor.py - Pytest version

import pytest
from unittest.mock import  AsyncMock, patch
from backend.modules.monitors.graph import monitor_subgraph
from backend.modules.monitors.nodes import fetch_metrics_node, summarize_node

@pytest.mark.asyncio
async def test_monitor_subgraph_with_mocks():
    """
    Test the full monitor subgraph with mocked external services.
    """
    
    # Mock data that would come from Prometheus
    mock_metrics = {
        "cpu_usage_percent": 85.5,
        "memory_usage_percent": 72.0,
        "error_rate_percent": 2.5
    }
    
    # Mock data that would come from Kubernetes
    mock_pod_status = {
        "total": 5,
        "running": 4,
        "failed": 1,
        "pods": [
            {"name": "api-gateway-abc", "status": "Running", "restarts": 0},
            {"name": "api-gateway-def", "status": "Failed", "restarts": 15}
        ]
    }
    
    mock_events = [
        {"type": "Warning", "reason": "OOMKilled", "message": "Container killed"}
    ]
    
    # Patch the clients
    with patch('backend.modules.monitors.nodes.prometheus') as mock_prom, \
         patch('backend.modules.monitors.nodes.k8s') as mock_k8s:
        
        # Set up mock returns
        mock_prom.get_service_metrics = AsyncMock(return_value=mock_metrics)
        mock_k8s.get_pods.return_value = mock_pod_status
        mock_k8s.get_events.return_value = mock_events
        mock_k8s.get_deployments.return_value = []
        mock_k8s.get_pod_logs.return_value = "ERROR: Connection refused\nINFO: Retrying..."
        
        # Run the subgraph
        input_state = {
            "service": "api-gateway",
            "namespace": "production"
        }
        
        result = await monitor_subgraph.ainvoke(input_state)
        
        # Assertions
        assert result["metrics"]["cpu_usage_percent"] == 85.5
        assert result["pod_status"]["total"] == 5
        assert result["pod_status"]["failed"] == 1
        assert "Issues detected" in result["health_summary"]


@pytest.mark.asyncio
async def test_monitor_healthy_service():
    """Test when service is healthy - no issues."""
    
    mock_metrics = {
        "cpu_usage_percent": 25.0,
        "memory_usage_percent": 40.0,
        "error_rate_percent": 0.1
    }
    
    mock_pod_status = {
        "total": 3,
        "running": 3,
        "failed": 0,
        "pods": [
            {"name": "api-1", "status": "Running", "restarts": 0},
            {"name": "api-2", "status": "Running", "restarts": 0},
            {"name": "api-3", "status": "Running", "restarts": 0}
        ]
    }
    
    with patch('backend.modules.monitors.nodes.prometheus') as mock_prom, \
         patch('backend.modules.monitors.nodes.k8s') as mock_k8s:
        
        mock_prom.get_service_metrics = AsyncMock(return_value=mock_metrics)
        mock_k8s.get_pods.return_value = mock_pod_status
        mock_k8s.get_events.return_value = []
        mock_k8s.get_deployments.return_value = []
        mock_k8s.get_pod_logs.return_value = ""
        
        result = await monitor_subgraph.ainvoke({
            "service": "api-gateway",
            "namespace": "production"
        })
        
        assert "healthy" in result["health_summary"].lower()


@pytest.mark.asyncio
async def test_monitor_handles_errors():
    """Test that monitor handles errors gracefully."""
    
    with patch('backend.modules.monitors.nodes.prometheus') as mock_prom, \
         patch('backend.modules.monitors.nodes.k8s') as mock_k8s:
        
        # Simulate Prometheus being down
        mock_prom.get_service_metrics = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        mock_k8s.get_pods.return_value = {"total": 0, "running": 0, "failed": 0, "pods": []}
        mock_k8s.get_events.return_value = []
        mock_k8s.get_deployments.return_value = []
        
        result = await monitor_subgraph.ainvoke({
            "service": "api-gateway",
            "namespace": "production"
        })
        
        # Should not crash, should have error recorded
        assert "errors" in result
        assert len(result["errors"]) > 0


# ══════════════════════════════════════════════════════════════
# TEST INDIVIDUAL NODES
# ══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_fetch_metrics_node():
    """Test just the metrics fetching node."""
    
    with patch('backend.modules.monitors.nodes.prometheus') as mock_prom:
        mock_prom.get_service_metrics = AsyncMock(return_value={
            "cpu_usage_percent": 50.0
        })
        
        state = {"service": "api-gateway", "namespace": "production"}
        result = await fetch_metrics_node(state)
        
        assert "metrics" in result
        assert result["metrics"]["cpu_usage_percent"] == 50.0


def test_summarize_node_with_issues():
    """Test the summarize node detects issues."""
    
    state = {
        "metrics": {"cpu_usage_percent": 95.0},  # High CPU
        "pod_status": {"total": 5, "running": 3, "failed": 2, "pods": []},  # Failures
        "events": [{"type": "Warning", "reason": "OOMKilled", "message": "test"}],
        "logs": [{"level": "ERROR", "message": "Connection failed"}]
    }
    
    result = summarize_node(state)
    
    assert "Issues detected" in result["health_summary"]
    assert "High CPU" in result["health_summary"]


def test_summarize_node_healthy():
    """Test the summarize node when healthy."""
    
    state = {
        "metrics": {"cpu_usage_percent": 30.0},
        "pod_status": {"total": 3, "running": 3, "failed": 0, "pods": []},
        "events": [],
        "logs": []
    }
    
    result = summarize_node(state)
    
    assert "healthy" in result["health_summary"].lower()


# ══════════════════════════════════════════════════════════════
# INTEGRATION TEST (Requires real services)
# ══════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.asyncio
async def test_monitor_real_prometheus():
    """
    Integration test with real Prometheus.
    
    Run with: pytest -m integration
    Only runs if you have Prometheus running.
    """
    result = await monitor_subgraph.ainvoke({
        "service": "api-gateway",
        "namespace": "default"
    })
    
    assert "metrics" in result
    assert "health_summary" in result