from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def client(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr("app.api.health.check_postgres", AsyncMock(return_value=True))
    monkeypatch.setattr("app.api.health.check_redis", AsyncMock(return_value=True))
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_ok_when_deps_up(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"postgres": True, "redis": True}


def test_ready_503_when_postgres_down(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.health.check_postgres", AsyncMock(return_value=False))
    monkeypatch.setattr("app.api.health.check_redis", AsyncMock(return_value=True))
    app = create_app(settings)
    with TestClient(app) as test_client:
        response = test_client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["postgres"] is False
    assert body["checks"]["redis"] is True


def test_ready_503_when_redis_down(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.health.check_postgres", AsyncMock(return_value=True))
    monkeypatch.setattr("app.api.health.check_redis", AsyncMock(return_value=False))
    app = create_app(settings)
    with TestClient(app) as test_client:
        response = test_client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["postgres"] is True
    assert body["checks"]["redis"] is False
