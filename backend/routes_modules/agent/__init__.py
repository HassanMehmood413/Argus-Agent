"""
Agent Routes Module

Routes for agent-related operations:
- Slack webhook handlers (for approval button clicks)
- Agent invocation endpoints
- Agent status endpoints
"""

from fastapi import APIRouter

from backend.routes_modules.agent.webhook import router as webhook_router

router = APIRouter(prefix="/agent", tags=["agent"])

# Include the webhook routes
router.include_router(webhook_router)

__all__ = ["router"]
