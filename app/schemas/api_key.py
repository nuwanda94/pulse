"""Pydantic schemas for API-key management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    """Payload for creating a new API key."""

    name: str = Field(min_length=1, max_length=128)
    is_admin: bool = False


class ApiKeyPublic(BaseModel):
    """Public metadata for an API key (never includes the secret)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    revoked_at: datetime | None = None


class ApiKeyCreated(ApiKeyPublic):
    """Creation response; includes the raw secret exactly once."""

    secret: str
