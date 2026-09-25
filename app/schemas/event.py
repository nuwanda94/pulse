"""Pydantic schemas for event ingest."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventCreate(BaseModel):
    """Payload for ingesting a single event."""

    name: str = Field(min_length=1, max_length=256)
    value: float
    tags: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None

    @field_validator("tags")
    @classmethod
    def tags_must_be_json_object(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("tags must be an object")
        for key, item in value.items():
            if not isinstance(key, str) or key == "":
                raise ValueError("tag keys must be non-empty strings")
            if not isinstance(item, (str, int, float, bool, type(None))):
                raise ValueError("tag values must be scalars")
        return value


class EventRead(BaseModel):
    """Persisted event returned after ingest."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    value: float
    tags: dict[str, Any]
    timestamp: datetime
    created_at: datetime
    api_key_id: UUID | None = None
