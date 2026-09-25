"""API-key authentication and admin authorization dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import hash_api_key
from app.db.session import get_db
from app.models import ApiKey


def _settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


async def require_api_key(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKey:
    """Extract, look up, and attach the current API key."""
    settings = _settings(request)
    raw_key = request.headers.get(settings.api_key_header)
    if raw_key is None or raw_key.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    digest = hash_api_key(raw_key)
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_hash == digest,
            ApiKey.is_active.is_(True),
            ApiKey.revoked_at.is_(None),
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    request.state.api_key = api_key
    return api_key


async def require_admin(
    api_key: Annotated[ApiKey, Depends(require_api_key)],
) -> ApiKey:
    """Require an active admin-scoped API key."""
    if not api_key.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return api_key
