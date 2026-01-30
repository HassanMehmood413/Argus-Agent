from typing import TypedDict, Dict, List, Any




class MonitorState(TypedDict, total=False):
    """
    State for the Monitor subgraph.
    
    INPUT (read from OrchestratorState):
    - service: which service to monitor
    - namespace: which K8s namespace
    
    OUTPUT (written back to OrchestratorState):
    - metrics: collected metrics
    - logs: collected logs
    - pod_status: pod information
    - events: K8s events
    - recent_deployments: recent deploys
    """
    
    # ─── INPUT (Mapped from Orchestrator) ───
    
    service: str
    # The service name to investigate
    # Mapped from: alert.service
    # Example: "api-gateway"
    
    namespace: str
    # Kubernetes namespace
    # Mapped from: alert.namespace
    # Example: "production"
    
    alert_labels: Dict[str, str]
    # All labels from the alert (useful for queries)
    # Mapped from: alert.labels
    # Example: {"pod": "api-gateway-xyz", "instance": "10.0.0.5"}
    
    time_range: str
    # How far back to look
    # Default: "1h"
    # Could be adjusted based on alert duration
    
    
    # ─── INTERNAL (Used within subgraph) ───
    
    prometheus_queries_run: List[str]
    # Track which queries we've run (for debugging)
    
    loki_queries_run: List[str]
    # Track log queries
    
    
    # ─── OUTPUT (Merged back to Orchestrator) ───
    
    metrics: Dict[str, Any]
    # Collected metrics
    # Structure:
    # {
    #     "cpu_usage_percent": 85.5,
    #     "memory_usage_percent": 72.3,
    #     "memory_usage_bytes": 1543503872,
    #     "error_rate_per_second": 5.2,
    #     "request_rate_per_second": 1250.0,
    #     "latency_p50_ms": 45.2,
    #     "latency_p99_ms": 234.5,
    #     "replicas_desired": 5,
    #     "replicas_ready": 3,
    #     "network_rx_bytes": 12345678,
    #     "network_tx_bytes": 87654321,
    # }
    
    logs: List[Dict[str, Any]]
    # Collected logs
    # Structure:
    # [
    #     {
    #         "timestamp": "2024-01-15T10:30:45Z",
    #         "level": "ERROR",
    #         "message": "Connection refused to database",
    #         "source": "api-gateway-pod-xyz",
    #         "trace_id": "abc123",  # if available
    #     },
    #     ...
    # ]
    
    pod_status: Dict[str, Any]
    # Pod information
    # Structure:
    # {
    #     "total": 5,
    #     "running": 3,
    #     "pending": 0,
    #     "failed": 2,
    #     "restarting": 2,  # pods with restarts > 3
    #     "pods": [
    #         {
    #             "name": "api-gateway-abc123",
    #             "status": "Running",
    #             "restarts": 0,
    #             "ready": True,
    #             "age": "2d",
    #             "node": "worker-1",
    #             "ip": "10.0.0.5"
    #         },
    #         {
    #             "name": "api-gateway-def456",
    #             "status": "CrashLoopBackOff",
    #             "restarts": 15,
    #             "ready": False,
    #             "age": "2d",
    #             "node": "worker-2",
    #             "ip": "10.0.0.6"
    #         }
    #     ]
    # }
    
    events: List[Dict[str, Any]]
    # Kubernetes events
    # Structure:
    # [
    #     {
    #         "type": "Warning",
    #         "reason": "OOMKilled",
    #         "message": "Container killed due to OOM",
    #         "object": "pod/api-gateway-def456",
    #         "count": 5,
    #         "first_seen": "2024-01-15T09:00:00Z",
    #         "last_seen": "2024-01-15T10:30:00Z"
    #     }
    # ]
    
    recent_deployments: List[Dict[str, Any]]
    # Recent deployments
    # Structure:
    # [
    #     {
    #         "name": "api-gateway",
    #         "revision": 42,
    #         "image": "api-gateway:v2.3.1",
    #         "previous_image": "api-gateway:v2.3.0",
    #         "deployed_at": "2024-01-15T08:00:00Z",
    #         "deployed_by": "github-actions",
    #         "replicas": 5
    #     }
    # ]
    
    health_summary: str
    # Quick summary for the analyzer
    # Example: "Service degraded: 2/5 pods failing, high error rate"
    
    errors: List[str]
    # Errors encountered during monitoring
    # Example: ["Metrics error: Connection refused", "Logs error: Timeout"]