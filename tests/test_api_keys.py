"""Tests for API-key create, list, and revoke endpoints."""

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
                    name="already-revoked",
                    key_hash=hash_api_key("pulse_revoked_secret"),
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


def test_create_list_requires_auth(client: TestClient) -> None:
    assert client.get("/v1/api-keys").status_code == 401
    assert client.post("/v1/api-keys", json={"name": "x"}).status_code == 401


def test_create_list_forbidden_for_non_admin(client: TestClient) -> None:
    headers = {"X-API-Key": RAW_USER_KEY}
    assert client.get("/v1/api-keys", headers=headers).status_code == 403
    response = client.post("/v1/api-keys", headers=headers, json={"name": "x"})
    assert response.status_code == 403


def test_create_returns_secret_once_and_list_omits_it(client: TestClient) -> None:
    headers = {"X-API-Key": RAW_ADMIN_KEY}
    created = client.post(
        "/v1/api-keys",
        headers=headers,
        json={"name": "ingest", "is_admin": False},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "ingest"
    assert body["is_admin"] is False
    assert body["is_active"] is True
    assert body["revoked_at"] is None
    secret = body["secret"]
    assert secret.startswith("pulse_")
    assert "key_hash" not in body

    listed = client.get("/v1/api-keys", headers=headers)
    assert listed.status_code == 200
    names = {item["name"] for item in listed.json()}
    assert "ingest" in names
    assert all("secret" not in item for item in listed.json())
    assert all("key_hash" not in item for item in listed.json())

    me = client.get("/v1/me", headers={"X-API-Key": secret})
    assert me.status_code == 200
    assert me.json()["name"] == "ingest"


def test_revoke_key_and_subsequent_auth_fails(client: TestClient) -> None:
    headers = {"X-API-Key": RAW_ADMIN_KEY}
    created = client.post("/v1/api-keys", headers=headers, json={"name": "temp"})
    key_id = created.json()["id"]
    secret = created.json()["secret"]

    revoked = client.delete(f"/v1/api-keys/{key_id}", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["is_active"] is False
    assert revoked.json()["revoked_at"] is not None
    assert "secret" not in revoked.json()

    assert client.get("/v1/me", headers={"X-API-Key": secret}).status_code == 401

    again = client.delete(f"/v1/api-keys/{key_id}", headers=headers)
    assert again.status_code == 200
    assert again.json()["is_active"] is False


def test_revoke_missing_key_returns_404(client: TestClient) -> None:
    headers = {"X-API-Key": RAW_ADMIN_KEY}
    response = client.delete(
        "/v1/api-keys/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert response.status_code == 404


def test_revoke_forbidden_for_non_admin(client: TestClient) -> None:
    headers = {"X-API-Key": RAW_USER_KEY}
    response = client.delete(
        "/v1/api-keys/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert response.status_code == 403
