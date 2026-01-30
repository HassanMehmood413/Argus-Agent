"""
Pytest fixtures for Analyzes agent tests.

These fixtures provide test data and setup for testing the Analyzer subgraph
with real GPT-4o and Qdrant (no mocks).
"""

import os
import pytest
from typing import Dict, Any, List

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


# Test collection name (separate from production)
TEST_COLLECTION = "devops_incidents_test"


@pytest.fixture(scope="session")
def check_api_keys():
    """
    Verify required API keys are set.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        pytest.skip("OPENAI_API_KEY environment variable not set")

    return True


@pytest.fixture(scope="session")
def check_qdrant():
    """
    Verify Qdrant is accessible.
    """
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    try:
        client = QdrantClient(url=qdrant_url)
        client.get_collections()
        return True
    except Exception as e:
        pytest.skip(f"Qdrant not accessible at {qdrant_url}: {e}")


@pytest.fixture
def sample_alert() -> Dict[str, Any]:
    """
    Sample alert data for testing.
    """
    return {
        "alertname": "HighMemoryUsage",
        "service": "api-gateway",
        "namespace": "production",
        "severity": "high",
        "message": "Memory usage exceeds 90% on api-gateway pods",
    }


@pytest.fixture
def sample_metrics() -> Dict[str, Any]:
    """
    Sample metrics data for testing.
    """
    return {
        "cpu_usage_percent": 45.5,
        "memory_usage_percent": 92.3,
        "error_rate_percent": 2.1,
        "request_rate_per_second": 1250,
        "latency_p99_seconds": 0.45,
    }


@pytest.fixture
def sample_pod_status() -> Dict[str, Any]:
    """
    Sample pod status for testing.
    """
    return {
        "total": 5,
        "running": 3,
        "pending": 0,
        "failed": 2,
        "pods": [
            {"name": "api-gateway-abc123", "status": "Running", "restarts": 0},
            {"name": "api-gateway-def456", "status": "Running", "restarts": 1},
            {"name": "api-gateway-ghi789", "status": "Running", "restarts": 2},
            {"name": "api-gateway-jkl012", "status": "CrashLoopBackOff", "restarts": 8},
            {"name": "api-gateway-mno345", "status": "CrashLoopBackOff", "restarts": 12},
        ],
    }


@pytest.fixture
def sample_events() -> List[Dict[str, Any]]:
    """
    Sample Kubernetes events for testing.
    """
    return [
        {
            "reason": "OOMKilled",
            "message": "Container api-gateway was OOM killed",
            "type": "Warning",
        },
        {
            "reason": "BackOff",
            "message": "Back-off restarting failed container",
            "type": "Warning",
        },
    ]


@pytest.fixture
def sample_logs() -> List[Dict[str, Any]]:
    """
    Sample log entries for testing.
    """
    return [
        {
            "level": "ERROR",
            "message": "OutOfMemoryError: Java heap space",
            "timestamp": "2024-01-15T10:30:00Z",
        },
        {
            "level": "ERROR",
            "message": "Failed to allocate memory for request buffer",
            "timestamp": "2024-01-15T10:30:05Z",
        },
        {
            "level": "WARN",
            "message": "Memory usage above threshold",
            "timestamp": "2024-01-15T10:29:55Z",
        },
    ]


@pytest.fixture
def sample_deployments() -> List[Dict[str, Any]]:
    """
    Sample recent deployments for testing.
    """
    return [
        {
            "name": "api-gateway",
            "image": "api-gateway:v2.3.1",
            "revision": 42,
            "deployed_at": "2024-01-15T09:00:00Z",
        }
    ]


@pytest.fixture
def oom_incident_state(
    sample_alert,
    sample_metrics,
    sample_pod_status,
    sample_events,
    sample_logs,
    sample_deployments,
) -> Dict[str, Any]:
    """
    Complete analyzer state simulating an OOM incident.
    """
    return {
        "alert": sample_alert,
        "severity": "high",
        "metrics": sample_metrics,
        "logs": sample_logs,
        "pod_status": sample_pod_status,
        "events": sample_events,
        "recent_deployments": sample_deployments,
    }


@pytest.fixture
def high_latency_state() -> Dict[str, Any]:
    """
    Analyzer state simulating a high latency incident.
    """
    return {
        "alert": {
            "alertname": "HighLatency",
            "service": "payment-service",
            "namespace": "production",
            "severity": "medium",
            "message": "P99 latency exceeds 2 seconds",
        },
        "severity": "medium",
        "metrics": {
            "cpu_usage_percent": 78.5,
            "memory_usage_percent": 65.0,
            "error_rate_percent": 5.5,
            "request_rate_per_second": 500,
            "latency_p99_seconds": 2.5,
        },
        "logs": [
            {"level": "WARN", "message": "Slow query detected: SELECT * FROM orders..."},
            {"level": "ERROR", "message": "Connection timeout to database"},
            {"level": "ERROR", "message": "Connection pool exhausted"},
        ],
        "pod_status": {"total": 3, "running": 3, "failed": 0, "pods": []},
        "events": [],
        "recent_deployments": [],
    }


@pytest.fixture
def error_spike_state() -> Dict[str, Any]:
    """
    Analyzer state simulating an error rate spike.
    """
    return {
        "alert": {
            "alertname": "HighErrorRate",
            "service": "auth-service",
            "namespace": "production",
            "severity": "critical",
            "message": "Error rate exceeds 15%",
        },
        "severity": "critical",
        "metrics": {
            "cpu_usage_percent": 35.0,
            "memory_usage_percent": 45.0,
            "error_rate_percent": 18.5,
            "request_rate_per_second": 2000,
            "latency_p99_seconds": 0.8,
        },
        "logs": [
            {"level": "ERROR", "message": "Redis connection refused"},
            {"level": "ERROR", "message": "Failed to validate auth token"},
            {"level": "ERROR", "message": "Cache lookup failed, timeout after 5s"},
        ],
        "pod_status": {"total": 4, "running": 4, "failed": 0, "pods": []},
        "events": [],
        "recent_deployments": [],
    }


@pytest.fixture
def clean_test_collection(check_qdrant):
    """
    Clean up test collection before and after tests.
    """
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    client = QdrantClient(url=qdrant_url)

    # Delete test collection if exists
    try:
        client.delete_collection(TEST_COLLECTION)
    except Exception:
        pass

    yield

    # Cleanup after test
    try:
        client.delete_collection(TEST_COLLECTION)
    except Exception:
        pass
