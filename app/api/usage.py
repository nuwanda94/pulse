"""Quota usage endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.auth import require_api_key
from app.models import ApiKey
from app.schemas.usage import UsageRead

router = APIRouter(prefix="/v1/usage", tags=["usage"])


@router.get("", response_model=UsageRead)
async def get_usage(
    request: Request,
    api_key: Annotated[ApiKey, Depends(require_api_key)],
) -> UsageRead:
    """Return remaining write quota for the authenticated key."""
    settings = request.app.state.settings
    limiter = request.app.state.rate_limiter
    result = await limiter.peek(
        api_key.id,
        settings.rate_limit_requests,
        settings.rate_limit_window_seconds,
    )
    return UsageRead(
        api_key_id=api_key.id,
        limit=result.limit,
        remaining=result.remaining,
        window_seconds=result.window_seconds,
        reset_seconds=result.reset_seconds,
    )
