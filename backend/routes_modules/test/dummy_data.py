"""
Dummy Data for Test Routes

Contains realistic dummy data for testing each agent module.
"""

from datetime import datetime, timedelta
import random
import uuid


def get_dummy_metrics(service: str, namespace: str) -> dict:
    """Generate dummy metrics data."""
    return {
        "cpu_usage": {
            "current": round(random.uniform(60, 95), 2),
            "avg_15m": round(random.uniform(50, 80), 2),
            "max_15m": round(random.uniform(80, 100), 2),
            "unit": "percent"
        },
        "memory_usage": {
            "current": round(random.uniform(70, 95), 2),
            "avg_15m": round(random.uniform(60, 85), 2),
            "max_15m": round(random.uniform(85, 100), 2),
            "unit": "percent"
        },
        "error_rate": {
            "current": round(random.uniform(5, 25), 2),
            "avg_15m": round(random.uniform(2, 15), 2),
            "threshold": 5.0,
            "unit": "percent"
        },
        "request_latency_p99": {
            "current": round(random.uniform(500, 2000), 0),
            "avg_15m": round(random.uniform(200, 800), 0),
            "threshold": 500,
            "unit": "ms"
        },
        "requests_per_second": {
            "current": round(random.uniform(100, 500), 0),
            "avg_15m": round(random.uniform(150, 400), 0),
            "unit": "rps"
        },
        "service": service,
        "namespace": namespace,
        "collected_at": datetime.utcnow().isoformat()
    }


def get_dummy_pod_status(service: str, namespace: str) -> dict:
    """Generate dummy pod status data."""
    pods = []
    statuses = ["Running", "Running", "Running", "CrashLoopBackOff", "OOMKilled"]

    for i in range(random.randint(2, 5)):
        pod_id = f"{service}-{uuid.uuid4().hex[:8]}"
        status = random.choice(statuses)
        pods.append({
            "name": pod_id,
            "status": status,
            "restarts": random.randint(0, 10) if status != "Running" else random.randint(0, 2),
            "age": f"{random.randint(1, 72)}h",
            "cpu_request": "100m",
            "cpu_limit": "500m",
            "memory_request": "256Mi",
            "memory_limit": "512Mi",
            "node": f"node-{random.randint(1, 5)}.cluster.local",
            "ready": status == "Running"
        })

    unhealthy = [p for p in pods if p["status"] != "Running"]

    return {
        "service": service,
        "namespace": namespace,
        "total_pods": len(pods),
        "healthy_pods": len([p for p in pods if p["status"] == "Running"]),
        "unhealthy_pods": len(unhealthy),
        "pods": pods,
        "issues": [
            f"Pod {p['name']} is in {p['status']} state with {p['restarts']} restarts"
            for p in unhealthy
        ]
    }


def get_dummy_events(service: str, namespace: str) -> list:
    """Generate dummy Kubernetes events."""
    event_types = [
        ("Warning", "OOMKilled", f"Container {service} was OOMKilled"),
        ("Warning", "BackOff", f"Back-off restarting failed container {service}"),
        ("Warning", "FailedScheduling", "0/5 nodes are available: insufficient memory"),
        ("Normal", "Pulled", f"Successfully pulled image for {service}"),
        ("Normal", "Created", f"Created container {service}"),
        ("Warning", "Unhealthy", "Readiness probe failed: connection refused"),
        ("Warning", "FailedMount", "Unable to attach or mount volumes"),
    ]

    events = []
    now = datetime.utcnow()

    for i in range(random.randint(3, 8)):
        event_type, reason, message = random.choice(event_types)
        events.append({
            "type": event_type,
            "reason": reason,
            "message": message,
            "count": random.randint(1, 15),
            "first_seen": (now - timedelta(minutes=random.randint(5, 60))).isoformat(),
            "last_seen": (now - timedelta(minutes=random.randint(0, 5))).isoformat(),
            "source": "kubelet",
            "namespace": namespace
        })

    return events


def get_dummy_logs(service: str) -> list:
    """Generate dummy log entries."""
    log_templates = [
        ("ERROR", f"Connection to database timed out after 30s"),
        ("ERROR", f"OutOfMemoryError: Java heap space"),
        ("ERROR", f"Failed to process payment: timeout"),
        ("WARN", f"High memory usage detected: 95%"),
        ("WARN", f"Slow query detected: 5.2s"),
        ("ERROR", f"Circuit breaker opened for downstream service"),
        ("ERROR", f"NullPointerException at PaymentService.java:142"),
        ("INFO", f"Retrying failed request, attempt 3/5"),
        ("ERROR", f"Connection pool exhausted, no available connections"),
    ]

    logs = []
    now = datetime.utcnow()

    for i in range(random.randint(5, 15)):
        level, message = random.choice(log_templates)
        logs.append({
            "timestamp": (now - timedelta(seconds=random.randint(0, 900))).isoformat(),
            "level": level,
            "message": message,
            "service": service,
            "pod": f"{service}-{uuid.uuid4().hex[:8]}",
            "trace_id": uuid.uuid4().hex[:16]
        })

    return sorted(logs, key=lambda x: x["timestamp"], reverse=True)


def get_dummy_deployments(service: str, namespace: str) -> list:
    """Generate dummy recent deployments."""
    deployments = []
    now = datetime.utcnow()

    for i in range(random.randint(1, 3)):
        version = f"v1.{random.randint(0, 9)}.{random.randint(0, 20)}"
        deployments.append({
            "version": version,
            "deployed_at": (now - timedelta(hours=random.randint(1, 48))).isoformat(),
            "deployed_by": random.choice(["jenkins", "argocd", "github-actions"]),
            "commit": uuid.uuid4().hex[:7],
            "status": random.choice(["successful", "successful", "rolled_back"]),
            "replicas": random.randint(2, 5),
            "namespace": namespace,
            "service": service
        })

    return sorted(deployments, key=lambda x: x["deployed_at"], reverse=True)


def get_dummy_alert(alert_name: str, severity: str, service: str) -> dict:
    """Generate dummy alert data."""
    return {
        "alertname": alert_name,
        "severity": severity,
        "service": service,
        "instance": f"{service}:8080",
        "job": service,
        "description": f"High error rate detected in {service}",
        "summary": f"{alert_name} is firing for {service}",
        "starts_at": datetime.utcnow().isoformat(),
        "labels": {
            "alertname": alert_name,
            "severity": severity,
            "service": service,
            "namespace": "production",
            "team": "platform"
        },
        "annotations": {
            "description": f"Error rate for {service} is above threshold",
            "runbook_url": f"https://runbooks.example.com/{alert_name.lower()}"
        }
    }


def get_dummy_patterns() -> list:
    """Generate dummy detected patterns."""
    patterns = [
        {
            "type": "high_memory",
            "severity": "high",
            "description": "Memory usage exceeded 90% threshold",
            "evidence": ["memory_usage.current = 94.5%", "Recent OOMKilled events"],
            "confidence": 0.95
        },
        {
            "type": "high_error_rate",
            "severity": "high",
            "description": "Error rate significantly above threshold",
            "evidence": ["error_rate.current = 15.3%", "threshold = 5%"],
            "confidence": 0.92
        },
        {
            "type": "pod_crash_loop",
            "severity": "critical",
            "description": "Multiple pods in CrashLoopBackOff state",
            "evidence": ["2 pods unhealthy", "Restart count > 5"],
            "confidence": 0.98
        },
        {
            "type": "recent_deployment",
            "severity": "medium",
            "description": "Issues started after recent deployment",
            "evidence": ["Deployment 2h ago", "Issues began ~1.5h ago"],
            "confidence": 0.78
        }
    ]
    return random.sample(patterns, k=random.randint(2, 4))


def get_dummy_recommended_actions(patterns: list) -> list:
    """Generate recommended actions based on patterns."""
    actions = []

    pattern_types = [p["type"] for p in patterns]

    if "high_memory" in pattern_types or "pod_crash_loop" in pattern_types:
        actions.append({
            "type": "restart_pod",
            "target": f"payment-service-{uuid.uuid4().hex[:8]}",
            "risk": "low",
            "description": "Restart unhealthy pod to recover from memory pressure",
            "estimated_impact": "1-2 minutes of degraded service",
            "priority": 1
        })

    if "high_error_rate" in pattern_types:
        actions.append({
            "type": "scale_up",
            "target": "payment-service",
            "replicas": 5,
            "risk": "medium",
            "description": "Increase replicas to handle load",
            "estimated_impact": "Increased resource usage",
            "priority": 2
        })

    if "recent_deployment" in pattern_types:
        actions.append({
            "type": "rollback",
            "target": "payment-service",
            "revision": "v1.2.3",
            "risk": "high",
            "description": "Rollback to previous stable version",
            "estimated_impact": "Service restart, potential brief downtime",
            "priority": 3
        })

    # Always add a diagnostic action
    actions.append({
        "type": "increase_logging",
        "target": "payment-service",
        "level": "DEBUG",
        "duration": "30m",
        "risk": "low",
        "description": "Temporarily increase log verbosity for debugging",
        "estimated_impact": "Increased log volume",
        "priority": 4
    })

    return actions


def get_dummy_execution_result(action: dict, dry_run: bool) -> dict:
    """Generate dummy execution result for an action."""
    success = random.random() > 0.1  # 90% success rate

    result = {
        "action": action,
        "success": success,
        "dry_run": dry_run,
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": (datetime.utcnow() + timedelta(seconds=random.randint(1, 10))).isoformat(),
        "duration_ms": random.randint(500, 5000)
    }

    if dry_run:
        result["message"] = f"[DRY RUN] Would execute: {action['type']} on {action['target']}"
        result["success"] = True
    elif success:
        result["message"] = f"Successfully executed {action['type']} on {action['target']}"
        if action["type"] == "restart_pod":
            result["details"] = {"new_pod": f"{action['target'].rsplit('-', 1)[0]}-{uuid.uuid4().hex[:8]}"}
        elif action["type"] == "scale_up":
            result["details"] = {"previous_replicas": 3, "new_replicas": action.get("replicas", 5)}
        elif action["type"] == "rollback":
            result["details"] = {"from_version": "v1.3.0", "to_version": action.get("revision", "v1.2.3")}
    else:
        result["message"] = f"Failed to execute {action['type']} on {action['target']}"
        result["error"] = "Timeout waiting for pod to become ready"

    return result
