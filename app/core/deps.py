"""Lightweight dependency connectivity checks."""

from urllib.parse import urlparse

import asyncpg  # type: ignore[import-untyped]
from redis.asyncio import Redis


def _asyncpg_dsn(database_url: str) -> str:
    """Convert a SQLAlchemy-style URL into an asyncpg DSN if needed."""
    if database_url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + database_url.removeprefix("postgresql+asyncpg://")
    return database_url


async def check_postgres(database_url: str) -> bool:
    """Return True if a simple query against Postgres succeeds."""
    dsn = _asyncpg_dsn(database_url)
    parsed = urlparse(dsn)
    try:
        conn = await asyncpg.connect(
            dsn,
            timeout=1,
            host=parsed.hostname,
        )
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()
        return True
    except Exception:
        return False


async def check_redis(redis_url: str) -> bool:
    """Return True if Redis PING succeeds."""
    client: Redis[bytes] = Redis.from_url(
        redis_url,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        pong = await client.ping()
        return bool(pong)
    except Exception:
        return False
    finally:
        await client.close()
