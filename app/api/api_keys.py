"""Admin endpoints for creating, listing, and revoking API keys."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.security import generate_api_key, hash_api_key
from app.db.session import get_db
from app.models import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyPublic

router = APIRouter(prefix="/v1/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    _: Annotated[ApiKey, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKeyCreated:
    """Create a new API key and return the raw secret once."""
    raw = generate_api_key()
    record = ApiKey(
        name=payload.name,
        key_hash=hash_api_key(raw),
        is_admin=payload.is_admin,
        is_active=True,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return ApiKeyCreated(
        id=record.id,
        name=record.name,
        is_admin=record.is_admin,
        is_active=record.is_active,
        created_at=record.created_at,
        revoked_at=record.revoked_at,
        secret=raw,
    )


@router.get("", response_model=list[ApiKeyPublic])
async def list_api_keys(
    _: Annotated[ApiKey, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ApiKey]:
    """List all API keys without secrets or hashes."""
    result = await session.execute(select(ApiKey).order_by(ApiKey.created_at))
    return list(result.scalars().all())


@router.delete("/{key_id}", response_model=ApiKeyPublic)
async def revoke_api_key(
    key_id: UUID,
    _: Annotated[ApiKey, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKey:
    """Revoke an API key. Idempotent if already revoked."""
    result = await session.execute(select(ApiKey).where(ApiKey.id == key_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    if record.is_active or record.revoked_at is None:
        record.is_active = False
        record.revoked_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(record)
    return record
