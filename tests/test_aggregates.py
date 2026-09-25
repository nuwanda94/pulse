"""Tests for on-read metric aggregation queries."""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
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
        session.add_all(
            [
                Event(
                    name="cpu",
                    value=10.0,
                    tags={},
                    timestamp=datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
                ),
                Event(
                    name="cpu",
                    value=30.0,
                    tags={},
                    timestamp=datetime(2026, 1, 1, 0, 20, tzinfo=UTC),
                ),
                Event(
                    name="cpu",
                    value=20.0,
                    tags={},
                    timestamp=datetime(2026, 1, 1, 1, 5, tzinfo=UTC),
                ),
                Event(
                    name="mem",
                    value=8.0,
                    tags={},
                    timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
                ),
            ]
        )
        await session.commit()
    yield factory
    await engine.dispose()


@pytest.fixture
def client(settings: Settings, sqlite_factory: Factory) -> Iterator[TestClient]:
    app = create_app(settings, session_factory=sqlite_factory)
    with TestClient(app) as test_client:
        yield test_client


def test_aggregate_requires_auth(client: TestClient) -> None:
    response = client.get("/v1/metrics/cpu")
    assert response.status_code == 401


def test_aggregate_unknown_metric(client: TestClient) -> None:
    response = client.get("/v1/metrics/missing", headers={"X-API-Key": RAW_USER_KEY})
    assert response.status_code == 404


def test_aggregate_current(client: TestClient) -> None:
    response = client.get("/v1/metrics/cpu", headers={"X-API-Key": RAW_USER_KEY})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "cpu"
    assert body["count"] == 3
    assert body["sum"] == 60.0
    assert body["avg"] == 20.0


def test_aggregate_time_window(client: TestClient) -> None:
    response = client.get(
        "/v1/metrics/cpu",
        headers={"X-API-Key": RAW_USER_KEY},
        params={"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T01:00:00Z"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["sum"] == 40.0
    assert body["avg"] == 20.0


def test_timeseries_hourly(client: TestClient) -> None:
    response = client.get(
        "/v1/metrics/cpu/timeseries",
        headers={"X-API-Key": RAW_USER_KEY},
        params={"interval": "1h"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "cpu"
    assert body["interval_seconds"] == 3600
    assert len(body["points"]) == 2
    assert body["points"][0]["count"] == 2
    assert body["points"][0]["sum"] == 40.0
    assert body["points"][1]["count"] == 1
    assert body["points"][1]["sum"] == 20.0


def test_timeseries_filled_window(client: TestClient) -> None:
    response = client.get(
        "/v1/metrics/cpu/timeseries",
        headers={"X-API-Key": RAW_USER_KEY},
        params={
            "interval": "1h",
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-01T03:00:00Z",
        },
    )
    assert response.status_code == 200
    points = response.json()["points"]
    assert len(points) == 3
    assert [p["count"] for p in points] == [2, 1, 0]


def test_timeseries_rejects_bad_interval(client: TestClient) -> None:
    response = client.get(
        "/v1/metrics/cpu/timeseries",
        headers={"X-API-Key": RAW_USER_KEY},
        params={"interval": "7y"},
    )
    assert response.status_code == 422
