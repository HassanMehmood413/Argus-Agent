"""
Kubernetes Executor Client

Performs write operations against Kubernetes for remediation actions.

SUPPORTS MULTIPLE DEPLOYMENT TOOLS:
===================================
1. kubectl (native) - Uses Kubernetes Python client directly
2. helm - Executes helm CLI commands
3. argocd - Uses ArgoCD API for GitOps workflows

WHY SEPARATE FROM MONITOR CLIENT?
=================================
- Monitor client is read-only (safe, no side effects)
- Executor client performs write operations (risky, needs careful handling)
- Different error handling and retry strategies
- Clear separation of concerns
"""

import logging
import subprocess
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from backend.config.settings import settings

logger = logging.getLogger(__name__)


class KubernetesExecutor:
    """
    Kubernetes executor for performing remediation actions.

    This client handles:
    - Pod restarts (delete pods to trigger restart)
    - Scaling deployments up/down
    - Rolling back deployments
    - Updating resource limits
    - ConfigMap updates

    All operations support dry-run mode for testing.
    """

    def __init__(
        self,
        in_cluster: bool = None,
        deployment_tool: str = None,
    ):
        """
        Initialize Kubernetes executor.

        Args:
            in_cluster: True if running inside Kubernetes (defaults to settings)
            deployment_tool: kubectl, helm, or argocd (defaults to settings)
        """
        self.in_cluster = in_cluster if in_cluster is not None else settings.K8S_IN_CLUSTER
        self.deployment_tool = deployment_tool or settings.DEPLOYMENT_TOOL
        self.core_v1: Optional[client.CoreV1Api] = None
        self.apps_v1: Optional[client.AppsV1Api] = None
        self._initialized = False

        self._init_client()

    def _init_client(self):
        """Initialize Kubernetes client."""
        try:
            if self.in_cluster:
                config.load_incluster_config()
            else:
                config.load_kube_config()

            self.core_v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self._initialized = True
            logger.info(f"[K8sExecutor] Initialized with tool: {self.deployment_tool}")

        except ConfigException as e:
            logger.warning(f"[K8sExecutor] Kubernetes config not available: {e}")
        except Exception as e:
            logger.warning(f"[K8sExecutor] Failed to initialize: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # ROLLBACK OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    async def rollback_deployment(
        self,
        namespace: str,
        deployment_name: str,
        to_revision: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Roll back a deployment to a previous revision.

        HOW IT WORKS (by tool):
        - kubectl: Uses rollout undo via API patch
        - helm: Executes helm rollback command
        - argocd: Syncs to previous revision via API

        Args:
            namespace: Kubernetes namespace
            deployment_name: Name of the deployment
            to_revision: Specific revision to roll back to (None = previous)
            dry_run: If True, simulate only

        Returns:
            Result dict with success status and details
        """
        logger.info(
            f"[K8sExecutor] Rolling back {deployment_name} in {namespace} "
            f"(tool={self.deployment_tool}, dry_run={dry_run})"
        )

        if dry_run:
            return self._dry_run_result("rollback", deployment_name, namespace)

        if self.deployment_tool == "kubectl":
            return await self._rollback_kubectl(namespace, deployment_name, to_revision)
        elif self.deployment_tool == "helm":
            return await self._rollback_helm(namespace, deployment_name, to_revision)
        elif self.deployment_tool == "argocd":
            return await self._rollback_argocd(namespace, deployment_name, to_revision)
        else:
            return self._error_result(f"Unknown deployment tool: {self.deployment_tool}")

    async def _rollback_kubectl(
        self,
        namespace: str,
        deployment_name: str,
        to_revision: Optional[int],
    ) -> Dict[str, Any]:
        """Roll back using native Kubernetes Python API (no kubectl CLI needed)."""
        if not self._initialized:
            return self._error_result("Kubernetes client not initialized")

        try:
            # Get current deployment
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
            )

            current_revision = deployment.metadata.annotations.get(
                "deployment.kubernetes.io/revision", "unknown"
            )

            # Get all ReplicaSets for this deployment
            label_selector = ",".join(
                f"{k}={v}"
                for k, v in (deployment.spec.selector.match_labels or {}).items()
            )
            replica_sets = self.apps_v1.list_namespaced_replica_set(
                namespace=namespace,
                label_selector=label_selector,
            )

            # Sort ReplicaSets by revision (descending)
            sorted_rs = sorted(
                replica_sets.items,
                key=lambda rs: int(
                    rs.metadata.annotations.get(
                        "deployment.kubernetes.io/revision", "0"
                    )
                ),
                reverse=True,
            )

            if len(sorted_rs) < 2:
                # No previous revision to roll back to -- do a rolling restart instead
                logger.warning(
                    f"[K8sExecutor] No previous revision for {deployment_name}, "
                    "performing rolling restart instead"
                )
                return await self._rolling_restart(namespace, deployment_name)

            # Find the target ReplicaSet
            if to_revision:
                target_rs = next(
                    (
                        rs for rs in sorted_rs
                        if rs.metadata.annotations.get(
                            "deployment.kubernetes.io/revision"
                        ) == str(to_revision)
                    ),
                    None,
                )
                if not target_rs:
                    return self._error_result(
                        f"Revision {to_revision} not found", "rollback", deployment_name
                    )
            else:
                # Previous revision = second in the sorted list
                target_rs = sorted_rs[1]

            target_revision = target_rs.metadata.annotations.get(
                "deployment.kubernetes.io/revision", "unknown"
            )

            # Patch the deployment's pod template with the target RS's template
            patch_body = {
                "spec": {
                    "template": target_rs.spec.template.to_dict()
                }
            }

            self.apps_v1.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=patch_body,
            )

            return {
                "success": True,
                "action": "rollback",
                "target": deployment_name,
                "namespace": namespace,
                "previous_revision": current_revision,
                "rolled_back_to": target_revision,
                "output": f"Rolled back {deployment_name} from revision {current_revision} to {target_revision}",
            }

        except ApiException as e:
            return self._error_result(f"API error: {e.reason}", "rollback", deployment_name)
        except Exception as e:
            return self._error_result(str(e), "rollback", deployment_name)

    async def _rollback_helm(
        self,
        namespace: str,
        release_name: str,
        to_revision: Optional[int],
    ) -> Dict[str, Any]:
        """Roll back using Helm."""
        # For Helm, deployment_name is usually the release name
        cmd = ["helm", "rollback", release_name, "-n", namespace]
        if to_revision:
            cmd.append(str(to_revision))

        result = await self._run_command(cmd)

        if result["returncode"] == 0:
            return {
                "success": True,
                "action": "rollback",
                "target": release_name,
                "namespace": namespace,
                "tool": "helm",
                "rolled_back_to": to_revision or "previous",
                "output": result["stdout"],
            }
        else:
            return self._error_result(result["stderr"], "rollback", release_name)

    async def _rollback_argocd(
        self,
        namespace: str,
        app_name: str,
        to_revision: Optional[int],
    ) -> Dict[str, Any]:
        """Roll back using ArgoCD."""
        # ArgoCD rollback via CLI
        cmd = ["argocd", "app", "rollback", app_name]
        if to_revision:
            cmd.extend(["--revision", str(to_revision)])

        result = await self._run_command(cmd)

        if result["returncode"] == 0:
            return {
                "success": True,
                "action": "rollback",
                "target": app_name,
                "namespace": namespace,
                "tool": "argocd",
                "rolled_back_to": to_revision or "previous",
                "output": result["stdout"],
            }
        else:
            return self._error_result(result["stderr"], "rollback", app_name)

    # ═══════════════════════════════════════════════════════════════════════
    # POD RESTART OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    async def restart_pods(
        self,
        namespace: str,
        deployment_name: str,
        rolling: bool = True,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Restart pods for a deployment.

        HOW IT WORKS:
        - rolling=True: Uses rollout restart (graceful, no downtime)
        - rolling=False: Deletes all pods at once (faster but causes downtime)

        Args:
            namespace: Kubernetes namespace
            deployment_name: Name of the deployment
            rolling: Use rolling restart (recommended)
            dry_run: If True, simulate only

        Returns:
            Result dict with success status
        """
        logger.info(
            f"[K8sExecutor] Restarting pods for {deployment_name} "
            f"(rolling={rolling}, dry_run={dry_run})"
        )

        if dry_run:
            return self._dry_run_result("restart_pods", deployment_name, namespace)

        if rolling:
            return await self._rolling_restart(namespace, deployment_name)
        else:
            return await self._delete_pods(namespace, deployment_name)

    async def _rolling_restart(
        self,
        namespace: str,
        deployment_name: str,
    ) -> Dict[str, Any]:
        """Perform rolling restart using Python Kubernetes API (no kubectl CLI needed).

        Works by patching the deployment with a restart annotation,
        which triggers a rolling update of all pods.
        """
        if not self._initialized:
            return self._error_result("Kubernetes client not initialized")

        try:
            restart_time = datetime.utcnow().isoformat() + "Z"
            patch_body = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "kubectl.kubernetes.io/restartedAt": restart_time
                            }
                        }
                    }
                }
            }

            self.apps_v1.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=patch_body,
            )

            return {
                "success": True,
                "action": "restart_pods",
                "target": deployment_name,
                "namespace": namespace,
                "method": "rolling",
                "output": f"Rolling restart triggered for {deployment_name} at {restart_time}",
            }

        except ApiException as e:
            return self._error_result(f"API error: {e.reason}", "restart_pods", deployment_name)
        except Exception as e:
            return self._error_result(str(e), "restart_pods", deployment_name)

    async def _delete_pods(
        self,
        namespace: str,
        deployment_name: str,
    ) -> Dict[str, Any]:
        """Delete all pods for a deployment (immediate restart)."""
        if not self._initialized:
            return self._error_result("Kubernetes client not initialized")

        try:
            # Get pods for this deployment
            label_selector = f"app={deployment_name}"
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector,
            )

            deleted_pods = []
            for pod in pods.items:
                self.core_v1.delete_namespaced_pod(
                    name=pod.metadata.name,
                    namespace=namespace,
                )
                deleted_pods.append(pod.metadata.name)

            return {
                "success": True,
                "action": "restart_pods",
                "target": deployment_name,
                "namespace": namespace,
                "method": "delete",
                "deleted_pods": deleted_pods,
                "count": len(deleted_pods),
            }

        except ApiException as e:
            return self._error_result(f"API error: {e.reason}", "restart_pods", deployment_name)
        except Exception as e:
            return self._error_result(str(e), "restart_pods", deployment_name)

    # ═══════════════════════════════════════════════════════════════════════
    # SCALING OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    async def scale_deployment(
        self,
        namespace: str,
        deployment_name: str,
        replicas: int,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Scale a deployment to a specific number of replicas.

        Args:
            namespace: Kubernetes namespace
            deployment_name: Name of the deployment
            replicas: Target number of replicas
            dry_run: If True, simulate only

        Returns:
            Result dict with success status
        """
        logger.info(
            f"[K8sExecutor] Scaling {deployment_name} to {replicas} replicas "
            f"(dry_run={dry_run})"
        )

        if dry_run:
            return self._dry_run_result("scale", deployment_name, namespace, replicas=replicas)

        if not self._initialized:
            return self._error_result("Kubernetes client not initialized")

        try:
            # Get current deployment
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
            )
            previous_replicas = deployment.spec.replicas

            # Patch the deployment
            body = {"spec": {"replicas": replicas}}
            self.apps_v1.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=body,
            )

            return {
                "success": True,
                "action": "scale",
                "target": deployment_name,
                "namespace": namespace,
                "previous_replicas": previous_replicas,
                "new_replicas": replicas,
            }

        except ApiException as e:
            return self._error_result(f"API error: {e.reason}", "scale", deployment_name)
        except Exception as e:
            return self._error_result(str(e), "scale", deployment_name)

    async def update_resources(
        self,
        namespace: str,
        deployment_name: str,
        cpu_limit: Optional[str] = None,
        memory_limit: Optional[str] = None,
        cpu_request: Optional[str] = None,
        memory_request: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Update resource limits/requests for a deployment.

        Args:
            namespace: Kubernetes namespace
            deployment_name: Name of the deployment
            cpu_limit: CPU limit (e.g., "500m", "2")
            memory_limit: Memory limit (e.g., "512Mi", "2Gi")
            cpu_request: CPU request
            memory_request: Memory request
            dry_run: If True, simulate only

        Returns:
            Result dict with success status
        """
        logger.info(
            f"[K8sExecutor] Updating resources for {deployment_name} "
            f"(cpu={cpu_limit}, mem={memory_limit}, dry_run={dry_run})"
        )

        if dry_run:
            return self._dry_run_result(
                "update_resources",
                deployment_name,
                namespace,
                cpu_limit=cpu_limit,
                memory_limit=memory_limit,
            )

        if not self._initialized:
            return self._error_result("Kubernetes client not initialized")

        try:
            # Build the patch
            resources = {"limits": {}, "requests": {}}

            if cpu_limit:
                resources["limits"]["cpu"] = cpu_limit
            if memory_limit:
                resources["limits"]["memory"] = memory_limit
            if cpu_request:
                resources["requests"]["cpu"] = cpu_request
            if memory_request:
                resources["requests"]["memory"] = memory_request

            # Patch the first container
            patch = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [{"name": deployment_name, "resources": resources}]
                        }
                    }
                }
            }

            self.apps_v1.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=patch,
            )

            return {
                "success": True,
                "action": "update_resources",
                "target": deployment_name,
                "namespace": namespace,
                "new_resources": resources,
            }

        except ApiException as e:
            return self._error_result(f"API error: {e.reason}", "update_resources", deployment_name)
        except Exception as e:
            return self._error_result(str(e), "update_resources", deployment_name)

    # ═══════════════════════════════════════════════════════════════════════
    # DIAGNOSTIC OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    async def run_diagnostics(
        self,
        namespace: str,
        deployment_name: str,
        diagnostic_type: str = "basic",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Run diagnostic checks on a deployment.

        This is a read-only operation that gathers diagnostic info.

        Args:
            namespace: Kubernetes namespace
            deployment_name: Name of the deployment
            diagnostic_type: Type of diagnostics (basic, detailed)
            dry_run: If True, simulate only

        Returns:
            Diagnostic results
        """
        logger.info(f"[K8sExecutor] Running {diagnostic_type} diagnostics for {deployment_name}")

        if dry_run:
            return self._dry_run_result("run_diagnostics", deployment_name, namespace)

        if not self._initialized:
            return self._error_result("Kubernetes client not initialized")

        diagnostics = {
            "success": True,
            "action": "run_diagnostics",
            "target": deployment_name,
            "namespace": namespace,
            "diagnostic_type": diagnostic_type,
            "results": {},
        }

        try:
            # Get deployment status
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
            )

            diagnostics["results"]["deployment"] = {
                "replicas_desired": deployment.spec.replicas,
                "replicas_ready": deployment.status.ready_replicas or 0,
                "replicas_available": deployment.status.available_replicas or 0,
                "conditions": [
                    {"type": c.type, "status": c.status, "reason": c.reason}
                    for c in (deployment.status.conditions or [])
                ],
            }

            # Get pod status
            label_selector = f"app={deployment_name}"
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector,
            )

            diagnostics["results"]["pods"] = {
                "total": len(pods.items),
                "running": sum(1 for p in pods.items if p.status.phase == "Running"),
                "pending": sum(1 for p in pods.items if p.status.phase == "Pending"),
                "failed": sum(1 for p in pods.items if p.status.phase == "Failed"),
            }

            # Get recent events
            events = self.core_v1.list_namespaced_event(
                namespace=namespace,
                field_selector=f"involvedObject.name={deployment_name}",
                limit=10,
            )

            diagnostics["results"]["recent_events"] = [
                {"type": e.type, "reason": e.reason, "message": e.message}
                for e in events.items
            ]

            return diagnostics

        except ApiException as e:
            return self._error_result(f"API error: {e.reason}", "run_diagnostics", deployment_name)
        except Exception as e:
            return self._error_result(str(e), "run_diagnostics", deployment_name)

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    async def _run_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Run a shell command asynchronously."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.EXECUTION_TIMEOUT_SECONDS,
            )

            return {
                "returncode": process.returncode,
                "stdout": stdout.decode().strip(),
                "stderr": stderr.decode().strip(),
            }

        except asyncio.TimeoutError:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {settings.EXECUTION_TIMEOUT_SECONDS}s",
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    def _dry_run_result(
        self,
        action: str,
        target: str,
        namespace: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate a dry-run result."""
        result = {
            "success": True,
            "action": action,
            "target": target,
            "namespace": namespace,
            "dry_run": True,
            "output": f"[DRY RUN] Would execute {action} on {target}",
        }
        result.update(kwargs)
        return result

    def _error_result(
        self,
        error: str,
        action: str = "unknown",
        target: str = "unknown",
    ) -> Dict[str, Any]:
        """Generate an error result."""
        return {
            "success": False,
            "action": action,
            "target": target,
            "error": error,
        }
