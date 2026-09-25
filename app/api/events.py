"""Single-event ingest endpoint."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.db.session import get_db
from app.models import ApiKey, Event
from app.schemas.event import EventCreate, EventRead

router = APIRouter(prefix="/v1/events", tags=["events"])


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    api_key: Annotated[ApiKey, Depends(require_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Event:
    """Persist a single event and return the stored record."""
    occurred_at = payload.timestamp or datetime.now(UTC)
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    record = Event(
        name=payload.name,
        value=payload.value,
        tags=payload.tags,
        timestamp=occurred_at,
        api_key_id=api_key.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record
