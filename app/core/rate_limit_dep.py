"""FastAPI dependency that enforces write rate limits per API key."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.auth import require_api_key
from app.models import ApiKey


async def enforce_write_rate_limit(
    request: Request,
    api_key: Annotated[ApiKey, Depends(require_api_key)],
) -> ApiKey:
    """Consume one write token for the authenticated key or raise 429."""
    settings = request.app.state.settings
    limiter = request.app.state.rate_limiter
    result = await limiter.consume(
        api_key.id,
        settings.rate_limit_requests,
        settings.rate_limit_window_seconds,
    )
    request.state.rate_limit = result
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(result.reset_seconds),
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": "0",
            },
        )
    return api_key
