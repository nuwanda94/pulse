"""Usage / quota schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class UsageRead(BaseModel):
    """Remaining quota for the current API key."""

    api_key_id: UUID
    limit: int = Field(ge=1)
    remaining: int = Field(ge=0)
    window_seconds: int = Field(ge=1)
    reset_seconds: int = Field(ge=0)
