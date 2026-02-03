"""
Action Executors

Each action type has a dedicated executor function that:
1. Validates the action parameters
2. Executes the action with retry logic
3. Returns a standardized result

All executors follow the same interface:
    async def execute_action(
        executor: KubernetesExecutor,
        action: Dict[str, Any],
        dry_run: bool = False
    ) -> Dict[str, Any]
"""

from backend.modules.execution.actions.registry import (
    ACTION_EXECUTORS,
    get_action_executor,
    execute_action,
)

__all__ = [
    "ACTION_EXECUTORS",
    "get_action_executor",
    "execute_action",
]
