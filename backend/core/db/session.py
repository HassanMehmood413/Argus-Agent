from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlaclchemy.orm import DeclarativeBase
from typing import AsyncGenerator, Annotated
from backend.config.settings import get_settings
from fastapi import Depends

settings = get_settings()

async_engine = create_async_engine(
    settings.DATABASE_URL,
    max_overflow=10,
    pool_size=10,
    pool_timeout=30,
)

async_session = async_sessionmaker(
    engine=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_session():
    async with async_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
