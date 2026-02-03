"""
Test Routes Module

Contains test endpoints with dummy data for each agent module.
Use these endpoints via Swagger UI to test the agent workflows.
"""

from backend.routes_modules.test.router import router as test_router

__all__ = ["test_router"]
