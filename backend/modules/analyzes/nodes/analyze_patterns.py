from typing import Dict, Any, List



def detect_patterns_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node 1: Detect patterns and anomalies in the monitoring data.

    This is RULE-BASED (not LLM) - fast and deterministic.
    """
    print("[Analyzer] Detecting patterns...")

    patterns = []

    metrics = state.get("metrics", {})
    pod_status = state.get("pod_status", {})
    events = state.get("events", [])
    logs = state.get("logs", [])
    recent_deployments = state.get("recent_deployments", [])


    # ══════════════════════════════════════════════════════════════
    # METRIC PATTERNS
    # ══════════════════════════════════════════════════════════════

    # High CPU
    cpu = metrics.get("cpu_usage_percent")
    if cpu and cpu > 80:
        patterns.append({
            "type": "high_cpu",
            "severity": "high" if cpu > 90 else "medium",
            "value": cpu,
            "threshold": 80,
            "description": f"CPU usage is {cpu:.1f}% (threshold: 80%)"
        })

    # High Memory
    memory = metrics.get("memory_usage_percent")
    if memory and memory > 80:
        patterns.append({
            "type": "high_memory",
            "severity": "high" if memory > 90 else "medium",
            "value": memory,
            "threshold": 80,
            "description": f"Memory usage is {memory:.1f}% (threshold: 80%)"
        })

    # High Error Rate
    error_rate = metrics.get("error_rate_percent")
    if error_rate and error_rate > 5:
        patterns.append({
            "type": "high_error_rate",
            "severity": "critical" if error_rate > 10 else "high",
            "value": error_rate,
            "threshold": 5,
            "description": f"Error rate is {error_rate:.1f}% (threshold: 5%)"
        })

    # High Latency
    latency = metrics.get("latency_p99_seconds")
    if latency and latency > 1.0:
        patterns.append({
            "type": "high_latency",
            "severity": "high" if latency > 2.0 else "medium",
            "value": latency,
            "threshold": 1.0,
            "description": f"P99 latency is {latency:.2f}s (threshold: 1.0s)"
        })


    # ══════════════════════════════════════════════════════════════
    # POD PATTERNS
    # ══════════════════════════════════════════════════════════════

    # Failing pods
    failed_pods = pod_status.get("failed", 0)
    total_pods = pod_status.get("total", 0)
    if failed_pods > 0:
        patterns.append({
            "type": "pod_failures",
            "severity": "critical" if failed_pods > total_pods / 2 else "high",
            "value": failed_pods,
            "total": total_pods,
            "description": f"{failed_pods}/{total_pods} pods are failing"
        })

    # Crash looping pods
    for pod in pod_status.get("pods", []):
        restarts = pod.get("restarts", 0)
        if restarts > 5:
            patterns.append({
                "type": "crash_loop",
                "severity": "critical" if restarts > 10 else "high",
                "pod_name": pod.get("name"),
                "restarts": restarts,
                "description": f"Pod {pod.get('name')} has restarted {restarts} times"
            })


    # ══════════════════════════════════════════════════════════════
    # EVENT PATTERNS
    # ══════════════════════════════════════════════════════════════

    for event in events:
        reason = event.get("reason", "").lower()

        # OOM Killed
        if "oom" in reason or "outofmemory" in reason:
            patterns.append({
                "type": "oom_killed",
                "severity": "critical",
                "event": event,
                "description": f"OOM Kill detected: {event.get('message', '')}"
            })

        # Image pull errors
        if "pull" in reason and ("err" in reason or "fail" in reason):
            patterns.append({
                "type": "image_pull_error",
                "severity": "high",
                "event": event,
                "description": f"Image pull error: {event.get('message', '')}"
            })

        # Liveness/Readiness probe failures
        if "probe" in reason.lower() or "unhealthy" in reason.lower():
            patterns.append({
                "type": "probe_failure",
                "severity": "high",
                "event": event,
                "description": f"Health probe failed: {event.get('message', '')}"
            })


    # ══════════════════════════════════════════════════════════════
    # LOG PATTERNS
    # ══════════════════════════════════════════════════════════════

    error_logs = [l for l in logs if l.get("level", "").upper() in ["ERROR", "FATAL"]]
    if len(error_logs) > 10:
        patterns.append({
            "type": "error_spike",
            "severity": "high",
            "count": len(error_logs),
            "description": f"High number of error logs: {len(error_logs)} errors"
        })

    # Look for specific error patterns in logs
    connection_errors = [l for l in logs if "connection" in l.get("message", "").lower()]
    if connection_errors:
        patterns.append({
            "type": "connection_errors",
            "severity": "high",
            "count": len(connection_errors),
            "description": f"Connection errors detected in logs ({len(connection_errors)} occurrences)"
        })

    timeout_errors = [l for l in logs if "timeout" in l.get("message", "").lower()]
    if timeout_errors:
        patterns.append({
            "type": "timeout_errors",
            "severity": "medium",
            "count": len(timeout_errors),
            "description": f"Timeout errors detected ({len(timeout_errors)} occurrences)"
        })


    # ══════════════════════════════════════════════════════════════
    # DEPLOYMENT PATTERNS
    # ══════════════════════════════════════════════════════════════

    if recent_deployments:
        # Check if there was a recent deployment (within last 2 hours)
        from datetime import datetime, timedelta

        for dep in recent_deployments:
            deployed_at = dep.get("deployed_at")
            if deployed_at:
                # Simple check - in real code, parse the timestamp properly
                patterns.append({
                    "type": "recent_deployment",
                    "severity": "info",
                    "deployment": dep.get("name"),
                    "image": dep.get("image"),
                    "revision": dep.get("revision"),
                    "description": f"Recent deployment: {dep.get('name')} ({dep.get('image')})"
                })


    print(f"[Analyzer] Found {len(patterns)} patterns")

    return {"patterns": patterns}
