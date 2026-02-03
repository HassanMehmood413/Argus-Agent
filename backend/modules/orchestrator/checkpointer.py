import logging
from functools import lru_cache
from typing import Optional, TYPE_CHECKING

from langgraph.checkpoint.memory import MemorySaver

from backend.config.settings import get_settings

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# CHECKPOINTER FACTORY
# ═══════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def get_checkpointer_sync() -> MemorySaver:
    """
    Get a synchronous in-memory checkpointer.

    WHY MEMORY SAVER?
    - Quick setup for development/testing
    - No database dependency
    - State lost on restart (not for production!)

    Returns:
        MemorySaver instance
    """
    logger.info("[Checkpointer] Using MemorySaver (in-memory, non-persistent)")
    return MemorySaver()


async def get_async_checkpointer() -> "AsyncPostgresSaver":
    """
    Get an async PostgreSQL checkpointer.

    WHY ASYNC POSTGRES?
    - Non-blocking I/O for better performance
    - Persistent state across restarts
    - Works with your existing asyncpg database

    NOTE: LangGraph's PostgresSaver uses psycopg, not asyncpg.
    We convert the URL format accordingly.

    Returns:
        AsyncPostgresSaver instance (already setup)
    """
    # Lazy import to avoid issues when postgres dependencies aren't installed

    settings = get_settings()

    # Convert asyncpg URL to psycopg format
    # From: postgresql+asyncpg://user:pass@host/db
    # To:   postgresql://user:pass@host/db
    db_url = settings.DATABASE_URL.replace("+asyncpg", "")

    logger.info("[Checkpointer] Using AsyncPostgresSaver (PostgreSQL)")

    # Create the async checkpointer
    checkpointer = AsyncPostgresSaver.from_conn_string(db_url)

    # Setup creates the required tables if they don't exist
    await checkpointer.setup()

    return checkpointer


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

# For sync contexts (testing, simple scripts)
_sync_checkpointer: Optional[MemorySaver] = None

# For async contexts (FastAPI, production)
_async_checkpointer: Optional["AsyncPostgresSaver"] = None


def get_checkpointer() -> MemorySaver:
    """
    Get the synchronous checkpointer (singleton).

    Use this for development and testing.
    For production async code, use get_async_checkpointer().

    Returns:
        MemorySaver instance
    """
    global _sync_checkpointer
    if _sync_checkpointer is None:
        _sync_checkpointer = get_checkpointer_sync()
    return _sync_checkpointer


async def get_production_checkpointer() -> "AsyncPostgresSaver":
    """
    Get the production async PostgreSQL checkpointer (singleton).

    This should be called once at app startup and reused.

    Returns:
        AsyncPostgresSaver instance
    """
    global _async_checkpointer
    if _async_checkpointer is None:
        _async_checkpointer = await get_async_checkpointer()
    return _async_checkpointer
