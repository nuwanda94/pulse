"""Tests for single-event ingest."""

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.security import hash_api_key
from app.db.base import Base
from app.db.session import create_session_factory
from app.main import create_app
from app.models import ApiKey, Event

RAW_USER_KEY = "pulse_user_secret"

Factory = async_sessionmaker[AsyncSession]


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
async def sqlite_factory() -> AsyncIterator[Factory]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        session.add(
            ApiKey(
                name="user",
                key_hash=hash_api_key(RAW_USER_KEY),
                is_admin=False,
                is_active=True,
            )
        )
        await session.commit()
    yield factory
    await engine.dispose()


@pytest.fixture
def client(settings: Settings, sqlite_factory: Factory) -> Iterator[TestClient]:
    app = create_app(settings, session_factory=sqlite_factory)
    with TestClient(app) as test_client:
        yield test_client


def test_ingest_requires_auth(client: TestClient) -> None:
    response = client.post("/v1/events", json={"name": "cpu", "value": 1.0})
    assert response.status_code == 401


def test_ingest_rejects_invalid_key(client: TestClient) -> None:
    response = client.post(
        "/v1/events",
        headers={"X-API-Key": "nope"},
        json={"name": "cpu", "value": 1.0},
    )
    assert response.status_code == 401


def test_ingest_validates_payload(client: TestClient) -> None:
    headers = {"X-API-Key": RAW_USER_KEY}
    missing_name = client.post("/v1/events", headers=headers, json={"value": 1.0})
    assert missing_name.status_code == 422
    empty_name = client.post("/v1/events", headers=headers, json={"name": "", "value": 1.0})
    assert empty_name.status_code == 422
    nested_tags = client.post(
        "/v1/events",
        headers=headers,
        json={"name": "cpu", "value": 1.0, "tags": {"ok": {"nested": True}}},
    )
    assert nested_tags.status_code == 422


def test_ingest_persists_event(client: TestClient) -> None:
    headers = {"X-API-Key": RAW_USER_KEY}
    response = client.post(
        "/v1/events",
        headers=headers,
        json={
            "name": "cpu.util",
            "value": 42.5,
            "tags": {"host": "web-1", "region": "us"},
            "timestamp": "2026-01-02T03:04:05+00:00",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "cpu.util"
    assert body["value"] == 42.5
    assert body["tags"] == {"host": "web-1", "region": "us"}
    assert body["timestamp"].startswith("2026-01-02T03:04:05")
    assert body["id"]
    assert body["api_key_id"]
    assert body["created_at"]


@pytest.mark.asyncio
async def test_ingest_defaults_timestamp_and_round_trips(
    client: TestClient, sqlite_factory: Factory
) -> None:
    headers = {"X-API-Key": RAW_USER_KEY}
    response = client.post(
        "/v1/events",
        headers=headers,
        json={"name": "latency", "value": 12},
    )
    assert response.status_code == 201
    event_id = response.json()["id"]
    assert response.json()["timestamp"]
    assert response.json()["tags"] == {}

    async with sqlite_factory() as session:
        result = await session.execute(select(Event).where(Event.name == "latency"))
        stored = result.scalar_one()
        assert str(stored.id) == event_id
        assert stored.value == 12.0
        assert stored.api_key_id is not None
