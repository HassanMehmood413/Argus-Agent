from typing import Dict, List, Any, Optional
from datetime import datetime
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
import logging

logger = logging.getLogger(__name__)


class KubernetesClient:
    """
    Client for querying Kubernetes API.
    
    Uses the official kubernetes Python client.
    """
    
    def __init__(self, in_cluster: bool = False):
        """
        Initialize K8s client.
        
        Args:
            in_cluster: True if running inside Kubernetes
        """
        self.core_v1: Optional[client.CoreV1Api] = None
        self.apps_v1: Optional[client.AppsV1Api] = None
        self._initialized = False
        
        try:
            if in_cluster:
                config.load_incluster_config()
            else:
                config.load_kube_config()
            
            self.core_v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self._initialized = True
        except ConfigException as e:
            logger.warning(f"Kubernetes config not available: {e}. Client will return empty data.")
        except Exception as e:
            logger.warning(f"Failed to initialize Kubernetes client: {e}. Client will return empty data.")
    
    def get_pods(
        self, 
        namespace: str, 
        label_selector: str = None
    ) -> Dict[str, Any]:
        """
        Get pods in a namespace.
        
        Args:
            namespace: K8s namespace
            label_selector: Filter pods (e.g., "app=api-gateway")
        
        Returns:
            Pod status summary
        """
        if not self._initialized:
            return {"total": 0, "running": 0, "pending": 0, "failed": 0, "pods": []}
        
        pods = self.core_v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector
        )
        
        pod_list = []
        total = len(pods.items)
        running = 0
        pending = 0
        failed = 0
        
        for pod in pods.items:
            phase = pod.status.phase
            
            if phase == "Running":
                running += 1
            elif phase == "Pending":
                pending += 1
            elif phase in ["Failed", "Unknown"]:
                failed += 1
            
            # Get restart count
            restarts = 0
            if pod.status.container_statuses:
                restarts = sum(
                    cs.restart_count 
                    for cs in pod.status.container_statuses
                )
            
            pod_list.append({
                "name": pod.metadata.name,
                "status": phase,
                "restarts": restarts,
                "ready": self._is_pod_ready(pod),
                "age": self._calculate_age(pod.metadata.creation_timestamp),
                "node": pod.spec.node_name,
                "ip": pod.status.pod_ip
            })
        
        return {
            "total": total,
            "running": running,
            "pending": pending,
            "failed": failed,
            "pods": pod_list
        }
    
    def get_events(
        self, 
        namespace: str, 
        involved_object_name: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get Kubernetes events.
        
        Args:
            namespace: K8s namespace
            involved_object_name: Filter by object name
            limit: Max events to return
        
        Returns:
            List of events
        """
        if not self._initialized:
            return []
        
        if involved_object_name:
            field_selector = f"involvedObject.name={involved_object_name}"
        else:
            field_selector = None
        
        events = self.core_v1.list_namespaced_event(
            namespace=namespace,
            field_selector=field_selector,
            limit=limit
        )
        
        event_list = []
        for event in events.items:
            event_list.append({
                "type": event.type,  # Normal or Warning
                "reason": event.reason,
                "message": event.message,
                "object": f"{event.involved_object.kind}/{event.involved_object.name}",
                "count": event.count,
                "first_seen": event.first_timestamp.isoformat() if event.first_timestamp else None,
                "last_seen": event.last_timestamp.isoformat() if event.last_timestamp else None
            })
        
        # Sort by last_seen (most recent first)
        event_list.sort(key=lambda x: x["last_seen"] or "", reverse=True)
        
        return event_list[:limit]
    
    def get_deployments(
        self, 
        namespace: str, 
        label_selector: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get deployments and their status.
        """
        if not self._initialized:
            return []
        
        deployments = self.apps_v1.list_namespaced_deployment(
            namespace=namespace,
            label_selector=label_selector
        )
        
        deployment_list = []
        for dep in deployments.items:
            # Get current image
            image = None
            if dep.spec.template.spec.containers:
                image = dep.spec.template.spec.containers[0].image
            
            deployment_list.append({
                "name": dep.metadata.name,
                "replicas_desired": dep.spec.replicas,
                "replicas_ready": dep.status.ready_replicas or 0,
                "replicas_available": dep.status.available_replicas or 0,
                "image": image,
                "created_at": dep.metadata.creation_timestamp.isoformat() if dep.metadata.creation_timestamp else None,
                "revision": dep.metadata.annotations.get("deployment.kubernetes.io/revision", "unknown")
            })
        
        return deployment_list
    
    def get_pod_logs(
        self, 
        namespace: str, 
        pod_name: str, 
        tail_lines: int = 100,
        container: str = None
    ) -> str:
        """
        Get logs from a pod.
        """
        if not self._initialized:
            return ""
        
        return self.core_v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=tail_lines,
            container=container
        )
    
    def _is_pod_ready(self, pod) -> bool:
        """Check if pod is ready."""
        if not pod.status.conditions:
            return False
        for condition in pod.status.conditions:
            if condition.type == "Ready":
                return condition.status == "True"
        return False
    
    def _calculate_age(self, timestamp) -> str:
        """Calculate age string from timestamp."""
        if not timestamp:
            return "unknown"
        
        delta = datetime.utcnow().replace(tzinfo=timestamp.tzinfo) - timestamp
        
        if delta.days > 0:
            return f"{delta.days}d"
        elif delta.seconds >= 3600:
            return f"{delta.seconds // 3600}h"
        elif delta.seconds >= 60:
            return f"{delta.seconds // 60}m"
        else:
            return f"{delta.seconds}s"

