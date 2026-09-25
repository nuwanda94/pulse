"""Tests for the async session factory and model round-trips."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import create_engine, create_session_factory, get_session
from app.models import ApiKey, Event, MetricAggregate


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as db:
        yield db
    await engine.dispose()


def test_create_engine_uses_explicit_url() -> None:
    engine = create_engine("sqlite+aiosqlite://")
    assert engine.url.drivername == "sqlite+aiosqlite"
    engine.sync_engine.dispose()


def test_create_session_factory_returns_maker() -> None:
    engine = create_engine("sqlite+aiosqlite://")
    factory = create_session_factory(engine)
    assert isinstance(factory, async_sessionmaker)
    engine.sync_engine.dispose()


async def test_get_session_yields_and_closes() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    factory = create_session_factory(engine)
    agen = get_session(factory)
    sess = await agen.__anext__()
    assert isinstance(sess, AsyncSession)
    assert sess.is_active
    await agen.aclose()
    await engine.dispose()


async def test_api_key_and_event_round_trip(session: AsyncSession) -> None:
    key = ApiKey(name="ingest", key_hash="abc123", is_admin=False, is_active=True)
    session.add(key)
    await session.flush()

    event = Event(
        name="requests",
        value=1.5,
        tags={"env": "test"},
        timestamp=datetime.now(UTC),
        api_key_id=key.id,
    )
    session.add(event)
    await session.commit()

    loaded_key = await session.get(ApiKey, key.id)
    assert loaded_key is not None
    assert loaded_key.name == "ingest"
    assert loaded_key.key_hash == "abc123"

    result = await session.execute(select(Event).where(Event.name == "requests"))
    loaded_event = result.scalar_one()
    assert loaded_event.value == 1.5
    assert loaded_event.tags == {"env": "test"}
    assert loaded_event.api_key_id == key.id


async def test_metric_aggregate_round_trip(session: AsyncSession) -> None:
    bucket = datetime(2026, 1, 1, tzinfo=UTC)
    agg = MetricAggregate(name="latency", bucket_start=bucket, count=2, sum=10.0, avg=5.0)
    session.add(agg)
    await session.commit()

    loaded = await session.get(MetricAggregate, agg.id)
    assert loaded is not None
    assert loaded.name == "latency"
    assert loaded.count == 2
    assert loaded.sum == 10.0
    assert loaded.avg == 5.0
    assert loaded.id != uuid4()
