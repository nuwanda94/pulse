"""Tests for the lightweight ad-hoc query endpoint."""

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
                    tags={"host": "a", "env": "prod"},
                    timestamp=datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
                ),
                Event(
                    name="cpu",
                    value=30.0,
                    tags={"host": "b", "env": "prod"},
                    timestamp=datetime(2026, 1, 1, 0, 20, tzinfo=UTC),
                ),
                Event(
                    name="cpu",
                    value=20.0,
                    tags={"host": "a", "env": "dev"},
                    timestamp=datetime(2026, 1, 1, 1, 5, tzinfo=UTC),
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


def test_query_requires_auth(client: TestClient) -> None:
    response = client.post("/v1/queries", json={"name": "cpu", "op": "avg"})
    assert response.status_code == 401


def test_query_avg(client: TestClient) -> None:
    response = client.post(
        "/v1/queries",
        headers={"X-API-Key": RAW_USER_KEY},
        json={"name": "cpu", "op": "avg"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["op"] == "avg"
    assert body["count"] == 3
    assert body["value"] == 20.0


def test_query_min_max_sum(client: TestClient) -> None:
    headers = {"X-API-Key": RAW_USER_KEY}
    minimum = client.post("/v1/queries", headers=headers, json={"name": "cpu", "op": "min"})
    maximum = client.post("/v1/queries", headers=headers, json={"name": "cpu", "op": "max"})
    total = client.post("/v1/queries", headers=headers, json={"name": "cpu", "op": "sum"})
    assert minimum.json()["value"] == 10.0
    assert maximum.json()["value"] == 30.0
    assert total.json()["value"] == 60.0


def test_query_tag_filter(client: TestClient) -> None:
    response = client.post(
        "/v1/queries",
        headers={"X-API-Key": RAW_USER_KEY},
        json={"name": "cpu", "op": "sum", "tags": {"host": "a"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["value"] == 30.0


def test_query_time_window(client: TestClient) -> None:
    response = client.post(
        "/v1/queries",
        headers={"X-API-Key": RAW_USER_KEY},
        json={
            "name": "cpu",
            "op": "count",
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-01T01:00:00Z",
        },
    )
    assert response.status_code == 200
    assert response.json()["value"] == 2.0


def test_query_rejects_unknown_op(client: TestClient) -> None:
    response = client.post(
        "/v1/queries",
        headers={"X-API-Key": RAW_USER_KEY},
        json={"name": "cpu", "op": "percentile"},
    )
    assert response.status_code == 422


def test_query_rejects_complex_fields(client: TestClient) -> None:
    response = client.post(
        "/v1/queries",
        headers={"X-API-Key": RAW_USER_KEY},
        json={"name": "cpu", "op": "avg", "group_by": ["host"], "sql": "SELECT 1"},
    )
    assert response.status_code == 422


def test_query_rejects_too_many_tag_filters(client: TestClient) -> None:
    response = client.post(
        "/v1/queries",
        headers={"X-API-Key": RAW_USER_KEY},
        json={
            "name": "cpu",
            "op": "avg",
            "tags": {"a": "1", "b": "2", "c": "3", "d": "4"},
        },
    )
    assert response.status_code == 422


def test_query_missing_metric_is_zero(client: TestClient) -> None:
    response = client.post(
        "/v1/queries",
        headers={"X-API-Key": RAW_USER_KEY},
        json={"name": "missing", "op": "sum"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["value"] == 0.0
