"""
Action Executor Registry

Central registry for all action executors with retry logic.

WHY A REGISTRY?
===============
1. Single source of truth for action routing
2. Easy to add new action types
3. Consistent interface for all actions
4. Centralized retry logic with tenacity

HOW RETRIES WORK:
=================
Each action is wrapped with tenacity's @retry decorator:
- Max 3 attempts (configurable)
- Exponential backoff: 1s → 2s → 4s
- Only retries on transient errors (network, timeout)
- Does NOT retry on validation errors or permission denied
"""

import logging
from typing import Dict, Any, Callable, Optional
from datetime import datetime
from functools import wraps

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from backend.config.settings import settings
from backend.modules.execution.clients.kubernetes_executor import KubernetesExecutor

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# RETRY CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

class RetryableError(Exception):
    """Exception that should trigger a retry."""
    pass


class NonRetryableError(Exception):
    """Exception that should NOT trigger a retry."""
    pass


def with_retry(func: Callable) -> Callable:
    """
    Decorator that adds retry logic to action executors.

    Uses exponential backoff:
    - Attempt 1: immediate
    - Attempt 2: wait 1s
    - Attempt 3: wait 2s
    - Attempt 4: wait 4s (if max_retries=4)

    Only retries on RetryableError, not on validation or permission errors.
    """
    @retry(
        stop=stop_after_attempt(settings.EXECUTION_MAX_RETRIES),
        wait=wait_exponential(
            multiplier=settings.EXECUTION_RETRY_DELAY,
            min=settings.EXECUTION_RETRY_DELAY,
            max=30,
        ),
        retry=retry_if_exception_type(RetryableError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)

    return wrapper


# ═══════════════════════════════════════════════════════════════════════════
# ACTION EXECUTOR FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

@with_retry
async def execute_rollback(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Execute rollback action.

    Parameters from action:
    - to_revision: Optional specific revision to roll back to
    - target_version: Alternative way to specify version
    """
    namespace = action.get("target_namespace", "default")
    target = action.get("target", "").replace("deployment/", "")
    to_revision = action.get("parameters", {}).get("to_revision")

    if not target:
        raise NonRetryableError("No target specified for rollback")

    try:
        result = await executor.rollback_deployment(
            namespace=namespace,
            deployment_name=target,
            to_revision=to_revision,
            dry_run=dry_run,
        )

        if not result.get("success") and "error" in result:
            # Check if error is retryable
            error = result.get("error", "")
            if any(x in error.lower() for x in ["timeout", "connection", "unavailable"]):
                raise RetryableError(error)

        return result

    except RetryableError:
        raise
    except Exception as e:
        raise NonRetryableError(str(e))


@with_retry
async def execute_restart_pods(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Execute pod restart action.

    Parameters from action:
    - rolling: Use rolling restart (default True)
    - all_at_once: Opposite of rolling
    """
    namespace = action.get("target_namespace", "default")
    target = action.get("target", "").replace("deployment/", "")
    params = action.get("parameters", {})
    rolling = params.get("rolling", not params.get("all_at_once", False))

    if not target:
        raise NonRetryableError("No target specified for restart")

    try:
        result = await executor.restart_pods(
            namespace=namespace,
            deployment_name=target,
            rolling=rolling,
            dry_run=dry_run,
        )

        if not result.get("success") and "error" in result:
            error = result.get("error", "")
            if any(x in error.lower() for x in ["timeout", "connection", "unavailable"]):
                raise RetryableError(error)

        return result

    except RetryableError:
        raise
    except Exception as e:
        raise NonRetryableError(str(e))


@with_retry
async def execute_scale_up(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Execute scale up action.

    Parameters from action:
    - replicas_increase: Number of replicas to add
    - target_replicas: Absolute target (takes precedence)
    """
    namespace = action.get("target_namespace", "default")
    target = action.get("target", "").replace("deployment/", "")
    params = action.get("parameters", {})

    if not target:
        raise NonRetryableError("No target specified for scale_up")

    # Determine target replicas
    target_replicas = params.get("target_replicas")
    if not target_replicas:
        # Need to get current replicas and add
        replicas_increase = params.get("replicas_increase", 1)
        # For now, we'll use a default increase
        # In production, you'd query current replicas first
        target_replicas = replicas_increase + 2  # Assume 2 current replicas

    try:
        result = await executor.scale_deployment(
            namespace=namespace,
            deployment_name=target,
            replicas=target_replicas,
            dry_run=dry_run,
        )

        if not result.get("success") and "error" in result:
            error = result.get("error", "")
            if any(x in error.lower() for x in ["timeout", "connection", "unavailable"]):
                raise RetryableError(error)

        return result

    except RetryableError:
        raise
    except Exception as e:
        raise NonRetryableError(str(e))


@with_retry
async def execute_scale_down(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Execute scale down action.

    Parameters from action:
    - replicas_decrease: Number of replicas to remove
    - target_replicas: Absolute target (takes precedence)
    """
    namespace = action.get("target_namespace", "default")
    target = action.get("target", "").replace("deployment/", "")
    params = action.get("parameters", {})

    if not target:
        raise NonRetryableError("No target specified for scale_down")

    target_replicas = params.get("target_replicas")
    if not target_replicas:
        replicas_decrease = params.get("replicas_decrease", 1)
        target_replicas = max(1, 2 - replicas_decrease)  # Never go below 1

    try:
        result = await executor.scale_deployment(
            namespace=namespace,
            deployment_name=target,
            replicas=target_replicas,
            dry_run=dry_run,
        )

        if not result.get("success") and "error" in result:
            error = result.get("error", "")
            if any(x in error.lower() for x in ["timeout", "connection", "unavailable"]):
                raise RetryableError(error)

        return result

    except RetryableError:
        raise
    except Exception as e:
        raise NonRetryableError(str(e))


@with_retry
async def execute_increase_resources(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Execute resource increase action.

    Parameters from action:
    - cpu_increase: Additional CPU (e.g., "100m")
    - memory_increase: Additional memory (e.g., "256Mi")
    """
    namespace = action.get("target_namespace", "default")
    target = action.get("target", "").replace("deployment/", "")
    params = action.get("parameters", {})

    if not target:
        raise NonRetryableError("No target specified for increase_resources")

    # For simplicity, set new limits directly
    # In production, you'd query current limits and add
    cpu_limit = params.get("cpu_increase", "500m")
    memory_limit = params.get("memory_increase", "512Mi")

    try:
        result = await executor.update_resources(
            namespace=namespace,
            deployment_name=target,
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
            dry_run=dry_run,
        )

        if not result.get("success") and "error" in result:
            error = result.get("error", "")
            if any(x in error.lower() for x in ["timeout", "connection", "unavailable"]):
                raise RetryableError(error)

        return result

    except RetryableError:
        raise
    except Exception as e:
        raise NonRetryableError(str(e))


@with_retry
async def execute_decrease_resources(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute resource decrease action."""
    namespace = action.get("target_namespace", "default")
    target = action.get("target", "").replace("deployment/", "")
    params = action.get("parameters", {})

    if not target:
        raise NonRetryableError("No target specified for decrease_resources")

    cpu_limit = params.get("cpu_decrease", "250m")
    memory_limit = params.get("memory_decrease", "256Mi")

    try:
        result = await executor.update_resources(
            namespace=namespace,
            deployment_name=target,
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
            dry_run=dry_run,
        )

        if not result.get("success") and "error" in result:
            error = result.get("error", "")
            if any(x in error.lower() for x in ["timeout", "connection", "unavailable"]):
                raise RetryableError(error)

        return result

    except RetryableError:
        raise
    except Exception as e:
        raise NonRetryableError(str(e))


@with_retry
async def execute_run_diagnostics(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Execute diagnostics action.

    This is read-only and gathers diagnostic information.
    """
    namespace = action.get("target_namespace", "default")
    target = action.get("target", "").replace("deployment/", "").replace("service/", "")
    params = action.get("parameters", {})
    diagnostic_type = params.get("diagnostic_type", "basic")

    if not target:
        raise NonRetryableError("No target specified for diagnostics")

    try:
        result = await executor.run_diagnostics(
            namespace=namespace,
            deployment_name=target,
            diagnostic_type=diagnostic_type,
            dry_run=dry_run,
        )

        return result

    except Exception as e:
        raise NonRetryableError(str(e))


async def execute_check_dependency(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Check dependency health.

    This is a diagnostic action that checks if dependencies are healthy.
    """
    namespace = action.get("target_namespace", "default")
    params = action.get("parameters", {})
    dependency_name = params.get("dependency_name", "unknown")

    logger.info(f"[Action] Checking dependency: {dependency_name}")

    if dry_run:
        return {
            "success": True,
            "action": "check_dependency",
            "target": dependency_name,
            "namespace": namespace,
            "dry_run": True,
            "output": f"[DRY RUN] Would check dependency {dependency_name}",
        }

    # Run diagnostics on the dependency
    try:
        result = await executor.run_diagnostics(
            namespace=namespace,
            deployment_name=dependency_name,
            diagnostic_type="basic",
            dry_run=False,
        )

        result["action"] = "check_dependency"
        return result

    except Exception as e:
        return {
            "success": False,
            "action": "check_dependency",
            "target": dependency_name,
            "error": str(e),
        }


async def execute_notify_oncall(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Notify on-call engineer via Slack.

    This uses the existing Slack client to send a notification.
    """
    from backend.modules.approval.clients.slack import SlackClient

    params = action.get("parameters", {})
    urgency = params.get("urgency", "medium")
    message = params.get("message", "Incident requires attention")

    logger.info(f"[Action] Notifying on-call (urgency={urgency})")

    if dry_run:
        return {
            "success": True,
            "action": "notify_oncall",
            "dry_run": True,
            "output": f"[DRY RUN] Would notify on-call: {message}",
        }

    slack_token = settings.SLACK_BOT_TOKEN
    if not slack_token:
        return {
            "success": True,  # Don't fail the action if Slack not configured
            "action": "notify_oncall",
            "output": "Slack not configured, notification skipped",
            "warning": "SLACK_BOT_TOKEN not set",
        }

    try:
        slack = SlackClient(token=slack_token)

        # Format urgency emoji
        urgency_emoji = {"low": "🟡", "medium": "🟠", "high": "🔴", "critical": "🚨"}.get(
            urgency, "⚪"
        )

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{urgency_emoji} *On-Call Notification*\n\n{message}",
                },
            }
        ]

        result = await slack.client.chat_postMessage(
            channel=settings.SLACK_DEFAULT_CHANNEL,
            blocks=blocks,
            text=f"On-Call: {message}",
        )

        return {
            "success": True,
            "action": "notify_oncall",
            "channel": settings.SLACK_DEFAULT_CHANNEL,
            "urgency": urgency,
            "message_ts": result.get("ts"),
        }

    except Exception as e:
        logger.error(f"[Action] Failed to notify on-call: {e}")
        return {
            "success": False,
            "action": "notify_oncall",
            "error": str(e),
        }


async def execute_investigate(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Log investigation required.

    This is a passive action that marks the incident for manual investigation.
    """
    params = action.get("parameters", {})
    investigation_areas = params.get("investigation_areas", [])

    logger.info(f"[Action] Marking for investigation: {investigation_areas}")

    return {
        "success": True,
        "action": "investigate",
        "output": "Marked for manual investigation",
        "investigation_areas": investigation_areas,
        "requires_human": True,
    }


async def execute_update_config(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Update configuration (ConfigMap).

    NOTE: This is a placeholder - full implementation requires
    knowing the specific ConfigMap structure.
    """
    namespace = action.get("target_namespace", "default")
    params = action.get("parameters", {})
    config_key = params.get("config_key")
    new_value = params.get("new_value")

    logger.info(f"[Action] Update config: {config_key}={new_value}")

    if dry_run:
        return {
            "success": True,
            "action": "update_config",
            "namespace": namespace,
            "dry_run": True,
            "output": f"[DRY RUN] Would update {config_key} to {new_value}",
        }

    # Placeholder - would need ConfigMap name and proper patching
    return {
        "success": True,
        "action": "update_config",
        "output": f"Config update logged: {config_key}={new_value}",
        "warning": "Full ConfigMap update not implemented - logged for manual review",
    }


async def execute_enable_debug_logging(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Enable debug logging.

    NOTE: This typically requires updating environment variables
    or ConfigMaps specific to your application.
    """
    params = action.get("parameters", {})
    duration_minutes = params.get("duration_minutes", 30)
    log_level = params.get("log_level", "DEBUG")

    logger.info(f"[Action] Enable debug logging for {duration_minutes}m")

    if dry_run:
        return {
            "success": True,
            "action": "enable_debug_logging",
            "dry_run": True,
            "output": f"[DRY RUN] Would enable {log_level} logging for {duration_minutes}m",
        }

    return {
        "success": True,
        "action": "enable_debug_logging",
        "output": f"Debug logging request logged: {log_level} for {duration_minutes}m",
        "warning": "Application-specific logging not implemented - logged for manual review",
        "duration_minutes": duration_minutes,
        "log_level": log_level,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ACTION REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

ACTION_EXECUTORS: Dict[str, Callable] = {
    "rollback": execute_rollback,
    "restart_pods": execute_restart_pods,
    "scale_up": execute_scale_up,
    "scale_down": execute_scale_down,
    "increase_resources": execute_increase_resources,
    "decrease_resources": execute_decrease_resources,
    "check_dependency": execute_check_dependency,
    "update_config": execute_update_config,
    "enable_debug_logging": execute_enable_debug_logging,
    "run_diagnostics": execute_run_diagnostics,
    "notify_oncall": execute_notify_oncall,
    "investigate": execute_investigate,
}


def get_action_executor(action_type: str) -> Optional[Callable]:
    """Get the executor function for an action type."""
    return ACTION_EXECUTORS.get(action_type)


async def execute_action(
    executor: KubernetesExecutor,
    action: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Execute a single action using the appropriate executor.

    This is the main entry point for action execution.

    Args:
        executor: KubernetesExecutor instance
        action: Action dict with type, target, parameters, etc.
        dry_run: If True, simulate only

    Returns:
        Result dict with success, action, output, error, etc.
    """
    action_type = action.get("type", "unknown")
    action_id = action.get("action_id", "unknown")

    logger.info(f"[Action] Executing action {action_id}: {action_type}")

    # Get the executor function
    executor_func = get_action_executor(action_type)

    if executor_func is None:
        logger.warning(f"[Action] Unknown action type: {action_type}")
        return {
            "success": False,
            "action_id": action_id,
            "action_type": action_type,
            "error": f"Unknown action type: {action_type}",
        }

    started_at = datetime.utcnow()

    try:
        result = await executor_func(executor, action, dry_run)

        # Add metadata
        result["action_id"] = action_id
        result["action_type"] = action_type
        result["started_at"] = started_at.isoformat()
        result["completed_at"] = datetime.utcnow().isoformat()

        return result

    except NonRetryableError as e:
        logger.error(f"[Action] Non-retryable error in {action_type}: {e}")
        return {
            "success": False,
            "action_id": action_id,
            "action_type": action_type,
            "error": str(e),
            "retryable": False,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

    except RetryableError as e:
        logger.error(f"[Action] All retries exhausted for {action_type}: {e}")
        return {
            "success": False,
            "action_id": action_id,
            "action_type": action_type,
            "error": f"Failed after {settings.EXECUTION_MAX_RETRIES} retries: {e}",
            "retryable": True,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.exception(f"[Action] Unexpected error in {action_type}: {e}")
        return {
            "success": False,
            "action_id": action_id,
            "action_type": action_type,
            "error": f"Unexpected error: {e}",
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }
