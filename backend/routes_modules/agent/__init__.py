"""
Agent Routes Module

Routes for agent-related operations:
- Incident management (create, status, resume)
- Slack webhook handlers (for approval button clicks)
"""

from fastapi import APIRouter

from backend.routes_modules.agent.routes import router as agent_routes

router = APIRouter(prefix="/agent", tags=["Agent"])

# Include all agent routes
router.include_router(agent_routes)

__all__ = ["router"]
