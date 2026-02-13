"""
DevOps Agent Backend

FastAPI application for the DevOps incident management agent.
"""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes_modules import agent_router, test_router


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

def setup_logging():
    """Configure logging for the application."""
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)

    # Set specific loggers to DEBUG for webhook debugging
    logging.getLogger("backend.routes_modules.agent").setLevel(logging.DEBUG)
    logging.getLogger("backend.modules.orchestrator").setLevel(logging.DEBUG)
    logging.getLogger("backend.modules.approval").setLevel(logging.DEBUG)

    # Suppress noisy loggers
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


# Initialize logging
setup_logging()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="DevOps Agent API",
        description="""
## DevOps Incident Management Agent

This API provides endpoints for:

### 🔧 Agent Operations
- Webhook endpoints for alerts
- Agent invocation and control

### 🧪 Test Endpoints
Test each agent module with dummy data via Swagger UI:
- **Monitor** - Simulates metrics, logs, pod status collection
- **Analyzer** - Pattern detection and root cause analysis
- **Approval** - Human-in-the-loop approval workflow
- **Execution** - Action execution simulation
- **Full Pipeline** - Complete incident flow testing

### Getting Started
1. Use the `/test/*` endpoints to explore functionality
2. All test endpoints return realistic dummy data
3. Set `dry_run=True` to simulate without real changes
        """,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(agent_router, prefix="/api/v1")
    app.include_router(test_router, prefix="/api/v1")

    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API info."""
        return {
            "name": "DevOps Agent API",
            "version": "0.1.0",
            "docs": "/docs",
            "test_endpoints": "/api/v1/test/health"
        }

    @app.get("/health", tags=["Health"])
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


# Create the app instance
app = create_app()


def main():
    """Run the application with uvicorn."""
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    main()
