"""Tests for per-API-key write rate limiting."""

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.rate_limit import InMemoryRateLimitBackend, RateLimiter
from app.core.security import hash_api_key
from app.db.base import Base
from app.db.session import create_session_factory
from app.main import create_app
from app.models import ApiKey

RAW_USER_KEY = "pulse_user_secret"
RAW_OTHER_KEY = "pulse_other_secret"

Factory = async_sessionmaker[AsyncSession]


@pytest.fixture
def settings() -> Settings:
    return Settings(
        rate_limit_requests=3,
        rate_limit_window_seconds=60,
        _env_file=None,
    )


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
        session.add(
            ApiKey(
                name="other",
                key_hash=hash_api_key(RAW_OTHER_KEY),
                is_admin=False,
                is_active=True,
            )
        )
        await session.commit()
    yield factory
    await engine.dispose()


@pytest.fixture
def client(settings: Settings, sqlite_factory: Factory) -> Iterator[TestClient]:
    app = create_app(
        settings,
        session_factory=sqlite_factory,
        rate_limiter=RateLimiter(InMemoryRateLimitBackend()),
    )
    with TestClient(app) as test_client:
        yield test_client


def test_usage_requires_auth(client: TestClient) -> None:
    response = client.get("/v1/usage")
    assert response.status_code == 401


def test_usage_starts_at_full_quota(client: TestClient) -> None:
    response = client.get("/v1/usage", headers={"X-API-Key": RAW_USER_KEY})
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 3
    assert body["remaining"] == 3
    assert body["window_seconds"] == 60
    assert body["reset_seconds"] >= 1
    assert body["api_key_id"]


def test_write_endpoints_return_429_when_limit_exceeded(client: TestClient) -> None:
    headers = {"X-API-Key": RAW_USER_KEY}
    statuses = [
        client.post("/v1/events", headers=headers, json={"name": "cpu", "value": i}).status_code
        for i in range(4)
    ]
    assert statuses[:3] == [201, 201, 201]
    assert statuses[3] == 429
    body = client.post("/v1/events", headers=headers, json={"name": "cpu", "value": 99}).json()
    assert "rate limit" in body["detail"].lower()


def test_rate_limit_is_per_api_key(client: TestClient) -> None:
    for index in range(3):
        response = client.post(
            "/v1/events",
            headers={"X-API-Key": RAW_USER_KEY},
            json={"name": "a", "value": index},
        )
        assert response.status_code == 201
    blocked = client.post(
        "/v1/events",
        headers={"X-API-Key": RAW_USER_KEY},
        json={"name": "a", "value": 9},
    )
    other = client.post(
        "/v1/events",
        headers={"X-API-Key": RAW_OTHER_KEY},
        json={"name": "b", "value": 1},
    )
    assert blocked.status_code == 429
    assert other.status_code == 201


def test_usage_decrements_after_writes(client: TestClient) -> None:
    headers = {"X-API-Key": RAW_USER_KEY}
    client.post("/v1/events", headers=headers, json={"name": "cpu", "value": 1})
    client.post(
        "/v1/events/batch",
        headers=headers,
        json={"events": [{"name": "mem", "value": 2}]},
    )
    usage = client.get("/v1/usage", headers=headers)
    assert usage.status_code == 200
    assert usage.json()["remaining"] == 1


def test_batch_is_also_rate_limited(client: TestClient) -> None:
    headers = {"X-API-Key": RAW_USER_KEY}
    for index in range(3):
        response = client.post(
            "/v1/events/batch",
            headers=headers,
            json={"events": [{"name": f"e{index}", "value": index}]},
        )
        assert response.status_code == 201
    limited = client.post(
        "/v1/events/batch",
        headers=headers,
        json={"events": [{"name": "overflow", "value": 1}]},
    )
    assert limited.status_code == 429
