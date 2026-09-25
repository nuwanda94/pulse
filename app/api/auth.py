"""Auth probe endpoints used to exercise API-key dependencies."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import require_admin, require_api_key
from app.models import ApiKey

router = APIRouter(prefix="/v1", tags=["auth"])


class CurrentKeyResponse(BaseModel):
    id: UUID
    name: str
    is_admin: bool


@router.get("/me", response_model=CurrentKeyResponse)
async def current_key(api_key: Annotated[ApiKey, Depends(require_api_key)]) -> CurrentKeyResponse:
    """Return metadata for the authenticated key (never the secret)."""
    return CurrentKeyResponse(id=api_key.id, name=api_key.name, is_admin=api_key.is_admin)


@router.get("/admin/ping", response_model=CurrentKeyResponse)
async def admin_ping(api_key: Annotated[ApiKey, Depends(require_admin)]) -> CurrentKeyResponse:
    """Admin-only probe used to verify elevated authorization."""
    return CurrentKeyResponse(id=api_key.id, name=api_key.name, is_admin=api_key.is_admin)
