"""
Routes Modules

Contains all API route modules organized by domain:
- auth: Authentication routes (login, register, tokens)
- agent: Agent-related routes (webhooks, agent invocation)
- test: Test routes with dummy data for Swagger UI testing
"""

from backend.routes_modules.agent import router as agent_router
from backend.routes_modules.test import test_router

__all__ = [
    "agent_router",
    "test_router",
]
