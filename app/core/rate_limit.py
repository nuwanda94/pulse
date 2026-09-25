"""Redis-backed (with in-memory fallback) fixed-window rate limiter."""

from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Outcome of a rate-limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int
    window_seconds: int


class RateLimitBackend(Protocol):
    async def increment(self, key: str, window_seconds: int) -> int: ...

    async def get(self, key: str) -> int: ...


class InMemoryRateLimitBackend:
    """Process-local counter store used in tests and when Redis is unavailable."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def increment(self, key: str, window_seconds: int) -> int:
        del window_seconds
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def get(self, key: str) -> int:
        return self._counts.get(key, 0)


class RedisRateLimitBackend:
    """Fixed-window counters stored in Redis."""

    def __init__(self, client: Redis[bytes]) -> None:
        self._client = client

    async def increment(self, key: str, window_seconds: int) -> int:
        count = await self._client.incr(key)
        if int(count) == 1:
            await self._client.expire(key, window_seconds)
        return int(count)

    async def get(self, key: str) -> int:
        raw = await self._client.get(key)
        if raw is None:
            return 0
        if isinstance(raw, bytes):
            return int(raw.decode())
        return int(raw)


class RateLimiter:
    """Fixed-window limiter keyed by API key id."""

    def __init__(self, backend: RateLimitBackend | None = None) -> None:
        self._backend: RateLimitBackend = backend or InMemoryRateLimitBackend()

    def _window_id(self, window_seconds: int, now: float | None = None) -> int:
        current = time() if now is None else now
        return int(current // window_seconds)

    def _reset_seconds(self, window_seconds: int, now: float | None = None) -> int:
        current = time() if now is None else now
        window_end = (self._window_id(window_seconds, current) + 1) * window_seconds
        return max(1, int(window_end - current))

    def _redis_key(self, api_key_id: UUID, window_seconds: int) -> str:
        return f"pulse:rl:{api_key_id}:{self._window_id(window_seconds)}"

    async def consume(self, api_key_id: UUID, limit: int, window_seconds: int) -> RateLimitResult:
        key = self._redis_key(api_key_id, window_seconds)
        used = await self._backend.increment(key, window_seconds)
        allowed = used <= limit
        remaining = max(0, limit - used) if allowed else 0
        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_seconds=self._reset_seconds(window_seconds),
            window_seconds=window_seconds,
        )

    async def peek(self, api_key_id: UUID, limit: int, window_seconds: int) -> RateLimitResult:
        key = self._redis_key(api_key_id, window_seconds)
        used = await self._backend.get(key)
        remaining = max(0, limit - used)
        return RateLimitResult(
            allowed=used < limit,
            limit=limit,
            remaining=remaining,
            reset_seconds=self._reset_seconds(window_seconds),
            window_seconds=window_seconds,
        )
