"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def create_engine(database_url: str | None = None, *, echo: bool = False) -> AsyncEngine:
    """Create an async engine for the given (or configured) database URL."""
    url = database_url or get_settings().database_url
    return create_async_engine(url, echo=echo, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return an async sessionmaker bound to ``engine``."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session and close it afterwards."""
    async with session_factory() as session:
        yield session


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a session from app.state.session_factory."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session
