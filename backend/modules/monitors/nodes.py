"""
Monitor Subgraph Nodes - Each node does one specific task.
"""

from typing import Dict, Any
from backend.modules.monitors.state import MonitorState
from backend.modules.monitors.clients.promethus import PrometheusClient
from backend.modules.monitors.clients.kubernetes import KubernetesClient
from backend.modules.monitors.clients.loki import LokiClient
import logging

logger = logging.getLogger(__name__)


prometheus = PrometheusClient("http://prometheus:9090")
k8s = KubernetesClient(in_cluster=False)
loki = LokiClient("http://loki:3100")  


async def fetch_metrics_node(state: MonitorState) -> Dict[str, Any]:
    """
    Node 1: Fetch metrics from Prometheus.
    
    Reads: service, namespace
    Writes: metrics
    """
    service = state.get("service", "")
    namespace = state.get("namespace", "default")
    
    logger.info(f"[Monitor] Fetching metrics for {service} in {namespace}...")
    
    try:
        metrics = await prometheus.get_service_metrics(service, namespace)
        return {"metrics": metrics}
    
    except Exception as e:
        logger.error(f"[Monitor] Error fetching metrics: {e}")
        return {
            "metrics": {},
            "errors": state.get("errors", []) + [f"Metrics error: {str(e)}"]
        }


def fetch_pod_status_node(state: MonitorState) -> Dict[str, Any]:
    """
    Node 2: Fetch pod status from Kubernetes.
    
    Reads: service, namespace
    Writes: pod_status
    """
    service = state.get("service", "")
    namespace = state.get("namespace", "default")
    
    logger.info(f"[Monitor] Fetching pod status for {service}...")
    
    try:
        # Use label selector to find pods for this service
        label_selector = f"app={service}"
        pod_status = k8s.get_pods(namespace, label_selector)
        return {"pod_status": pod_status}
    
    except Exception as e:
        logger.error(f"[Monitor] Error fetching pods: {e}")
        return {
            "pod_status": {"total": 0, "running": 0, "failed": 0, "pods": []},
            "errors": state.get("errors", []) + [f"Pod status error: {str(e)}"]
        }


def fetch_events_node(state: MonitorState) -> Dict[str, Any]:
    """
    Node 3: Fetch Kubernetes events.
    
    Reads: service, namespace
    Writes: events
    """
    service = state.get("service", "")
    namespace = state.get("namespace", "default")
    
    logger.info(f"[Monitor] Fetching K8s events...")
    
    try:
        events = k8s.get_events(namespace, limit=30)
        
        # Filter to relevant events (warnings, recent)
        relevant_events = [
            e for e in events 
            if e["type"] == "Warning" or service in e.get("object", "")
        ]
        
        return {"events": relevant_events[:20]}
    
    except Exception as e:
        logger.error(f"[Monitor] Error fetching events: {e}")
        return {
            "events": [],
            "errors": state.get("errors", []) + [f"Events error: {str(e)}"]
        }


async def fetch_logs_node(state: MonitorState) -> Dict[str, Any]:
    """
    Node 4: Fetch logs (from Loki or Kubernetes).
    
    Reads: service, namespace, pod_status
    Writes: logs
    """
    service = state.get("service", "")
    namespace = state.get("namespace", "default")
    
    logger.info(f"[Monitor] Fetching logs...")
    
    logs = []
    
    try:
        # Option 1: Try Loki first
        try:
            logs = await loki.get_service_logs(
                service=service,
                namespace=namespace,
                level="error",
                limit=50
            )
        except Exception:
            # Option 2: Fall back to Kubernetes logs
            pod_status = state.get("pod_status", {})
            pods = pod_status.get("pods", [])
            
            for pod in pods[:3]:  # Get logs from first 3 pods
                try:
                    pod_logs = k8s.get_pod_logs(
                        namespace=namespace,
                        pod_name=pod["name"],
                        tail_lines=30
                    )
                    
                    # Parse log lines
                    for line in pod_logs.split("\n"):
                        if line.strip():
                            logs.append({
                                "source": pod["name"],
                                "message": line,
                                "level": "ERROR" if "error" in line.lower() else "INFO"
                            })
                except Exception:
                    continue
        
        # Filter to errors/warnings only
        error_logs = [
            log for log in logs
            if any(level in str(log).lower() for level in ["error", "warn", "fatal", "exception"])
        ]
        
        return {"logs": error_logs[:50]}
    
    except Exception as e:
        logger.error(f"[Monitor] Error fetching logs: {e}")
        return {
            "logs": [],
            "errors": state.get("errors", []) + [f"Logs error: {str(e)}"]
        }


def fetch_deployments_node(state: MonitorState) -> Dict[str, Any]:
    """
    Node 5: Fetch recent deployments.
    
    Reads: service, namespace
    Writes: recent_deployments
    """
    service = state.get("service", "")
    namespace = state.get("namespace", "default")
    
    logger.info(f"[Monitor] Fetching deployments...")
    
    try:
        label_selector = f"app={service}"
        deployments = k8s.get_deployments(namespace, label_selector)
        return {"recent_deployments": deployments}
    
    except Exception as e:
        logger.error(f"[Monitor] Error fetching deployments: {e}")
        return {
            "recent_deployments": [],
            "errors": state.get("errors", []) + [f"Deployments error: {str(e)}"]
        }


def summarize_node(state: MonitorState) -> Dict[str, Any]:
    """
    Node 6: Create a health summary.
    
    Reads: metrics, pod_status, events, logs
    Writes: health_summary
    """
    logger.info(f"[Monitor] Creating summary...")
    
    metrics = state.get("metrics", {})
    pod_status = state.get("pod_status", {})
    events = state.get("events", [])
    logs = state.get("logs", [])
    
    issues = []
    
    # Check metrics
    cpu = metrics.get("cpu_usage_percent", 0)
    if cpu and cpu > 80:
        issues.append(f"High CPU: {cpu:.1f}%")
    
    memory = metrics.get("memory_usage_percent", 0)
    if memory and memory > 80:
        issues.append(f"High Memory: {memory:.1f}%")
    
    error_rate = metrics.get("error_rate_percent", 0)
    if error_rate and error_rate > 5:
        issues.append(f"High Error Rate: {error_rate:.1f}%")
    
    # Check pods
    total_pods = pod_status.get("total", 0)
    running_pods = pod_status.get("running", 0)
    failed_pods = pod_status.get("failed", 0)
    
    if failed_pods > 0:
        issues.append(f"Failing Pods: {failed_pods}/{total_pods}")
    
    if running_pods < total_pods:
        issues.append(f"Not All Pods Running: {running_pods}/{total_pods}")
    
    # Check for crash loops
    for pod in pod_status.get("pods", []):
        if pod.get("restarts", 0) > 5:
            issues.append(f"Pod {pod['name']} has {pod['restarts']} restarts")
    
    # Check events
    warning_events = [e for e in events if e.get("type") == "Warning"]
    if warning_events:
        issues.append(f"{len(warning_events)} warning events")
    
    # Check logs
    error_logs = [l for l in logs if "error" in str(l).lower()]
    if error_logs:
        issues.append(f"{len(error_logs)} error logs")
    
    # Create summary
    if not issues:
        summary = "Service appears healthy. No issues detected."
    else:
        summary = f"Issues detected: {'; '.join(issues)}"
    
    return {"health_summary": summary}