"""Single-event and batch ingest endpoints."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.db.session import get_db
from app.models import ApiKey, Event
from app.schemas.event import EventBatchCreate, EventBatchRead, EventCreate, EventRead

router = APIRouter(prefix="/v1/events", tags=["events"])

IdempotencyStore = dict[tuple[UUID, str], list[UUID]]


def _normalize_timestamp(value: datetime | None, fallback: datetime) -> datetime:
    occurred_at = value or fallback
    if occurred_at.tzinfo is None:
        return occurred_at.replace(tzinfo=UTC)
    return occurred_at


def _event_from_payload(payload: EventCreate, api_key_id: UUID, fallback: datetime) -> Event:
    return Event(
        name=payload.name,
        value=payload.value,
        tags=payload.tags,
        timestamp=_normalize_timestamp(payload.timestamp, fallback),
        api_key_id=api_key_id,
    )


def _idempotency_store(request: Request) -> IdempotencyStore:
    store = getattr(request.app.state, "idempotency_store", None)
    if store is None:
        store = {}
        request.app.state.idempotency_store = store
    return store


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    api_key: Annotated[ApiKey, Depends(require_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Event:
    """Persist a single event and return the stored record."""
    record = _event_from_payload(payload, api_key.id, datetime.now(UTC))
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


@router.post("/batch", response_model=EventBatchRead, status_code=status.HTTP_201_CREATED)
async def create_events_batch(
    payload: EventBatchCreate,
    request: Request,
    api_key: Annotated[ApiKey, Depends(require_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> EventBatchRead:
    """Persist a batch of events with optional idempotent replay."""
    store = _idempotency_store(request)
    cache_key: tuple[UUID, str] | None = None
    if idempotency_key is not None and idempotency_key.strip() != "":
        cache_key = (api_key.id, idempotency_key.strip())
        cached_ids = store.get(cache_key)
        if cached_ids is not None:
            result = await session.execute(select(Event).where(Event.id.in_(cached_ids)))
            by_id = {row.id: row for row in result.scalars().all()}
            events = [by_id[event_id] for event_id in cached_ids if event_id in by_id]
            return EventBatchRead(
                count=len(events),
                events=[EventRead.model_validate(event) for event in events],
                idempotent_replay=True,
            )

    now = datetime.now(UTC)
    records = [_event_from_payload(item, api_key.id, now) for item in payload.events]
    session.add_all(records)
    await session.commit()
    for record in records:
        await session.refresh(record)

    if cache_key is not None:
        store[cache_key] = [record.id for record in records]

    return EventBatchRead(
        count=len(records),
        events=[EventRead.model_validate(record) for record in records],
        idempotent_replay=False,
    )
