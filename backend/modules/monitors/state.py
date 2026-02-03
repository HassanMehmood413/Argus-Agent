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
    namespace: str
    alert_labels: Dict[str, str]
    time_range: str
    # ─── INTERNAL (Used within subgraph) ───
    prometheus_queries_run: List[str]
    loki_queries_run: List[str]
    # ─── OUTPUT (Merged back to Orchestrator) ───
    metrics: Dict[str, Any]
    logs: List[Dict[str, Any]]
    pod_status: Dict[str, Any]
    events: List[Dict[str, Any]]
    recent_deployments: List[Dict[str, Any]]
    health_summary: str
    errors: List[str]
