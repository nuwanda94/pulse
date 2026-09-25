"""Tests for API-key authentication and admin authorization."""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.security import hash_api_key
from app.db.base import Base
from app.db.session import create_session_factory
from app.main import create_app
from app.models import ApiKey

RAW_USER_KEY = "pulse_user_secret"
RAW_ADMIN_KEY = "pulse_admin_secret"
RAW_REVOKED_KEY = "pulse_revoked_secret"


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
async def sqlite_factory() -> AsyncIterator[object]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        session.add_all(
            [
                ApiKey(
                    name="user",
                    key_hash=hash_api_key(RAW_USER_KEY),
                    is_admin=False,
                    is_active=True,
                ),
                ApiKey(
                    name="admin",
                    key_hash=hash_api_key(RAW_ADMIN_KEY),
                    is_admin=True,
                    is_active=True,
                ),
                ApiKey(
                    name="revoked",
                    key_hash=hash_api_key(RAW_REVOKED_KEY),
                    is_admin=False,
                    is_active=False,
                    revoked_at=datetime.now(UTC),
                ),
            ]
        )
        await session.commit()
    yield factory
    await engine.dispose()


@pytest.fixture
def client(settings: Settings, sqlite_factory: object) -> Iterator[TestClient]:
    app = create_app(settings, session_factory=sqlite_factory)  # type: ignore[arg-type]
    with TestClient(app) as test_client:
        yield test_client


def test_hash_api_key_is_stable() -> None:
    digest = hash_api_key("abc")
    assert digest == hash_api_key("abc")
    assert digest != hash_api_key("abd")
    assert len(digest) == 64


def test_me_missing_key_returns_401(client: TestClient) -> None:
    response = client.get("/v1/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"


def test_me_invalid_key_returns_401(client: TestClient) -> None:
    response = client.get("/v1/me", headers={"X-API-Key": "nope"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_me_revoked_key_returns_401(client: TestClient) -> None:
    response = client.get("/v1/me", headers={"X-API-Key": RAW_REVOKED_KEY})
    assert response.status_code == 401


def test_me_valid_key_returns_metadata(client: TestClient) -> None:
    response = client.get("/v1/me", headers={"X-API-Key": RAW_USER_KEY})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "user"
    assert body["is_admin"] is False
    assert "id" in body


def test_admin_ping_forbidden_for_non_admin(client: TestClient) -> None:
    response = client.get("/v1/admin/ping", headers={"X-API-Key": RAW_USER_KEY})
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


def test_admin_ping_ok_for_admin(client: TestClient) -> None:
    response = client.get("/v1/admin/ping", headers={"X-API-Key": RAW_ADMIN_KEY})
    assert response.status_code == 200
    assert response.json()["is_admin"] is True
    assert response.json()["name"] == "admin"
