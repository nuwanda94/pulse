"""Tests for consistent error envelopes and OpenAPI polish."""

from collections.abc import Iterator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.request_context import REQUEST_ID_HEADER
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)

    @app.get("/__boom")
    async def boom() -> None:
        raise RuntimeError("secret internals")

    @app.get("/__denied")
    async def denied() -> None:
        raise HTTPException(status_code=403, detail="nope")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_http_error_includes_envelope_and_request_id(client: TestClient) -> None:
    response = client.get("/__denied", headers={REQUEST_ID_HEADER: "req-polish-1"})
    assert response.status_code == 403
    body = response.json()
    assert body["detail"] == "nope"
    assert body["error"]["code"] == "forbidden"
    assert body["error"]["message"] == "nope"
    assert body["request_id"] == "req-polish-1"
    assert response.headers[REQUEST_ID_HEADER] == "req-polish-1"


def test_validation_error_includes_envelope(settings: Settings) -> None:
    from pydantic import BaseModel

    from app.main import create_app

    app = create_app(settings)

    class Item(BaseModel):
        name: str

    @app.post("/__validate")
    async def validate(item: Item) -> Item:
        return item

    with TestClient(app) as test_client:
        response = test_client.post("/__validate", json={"name": 1})
    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    assert body["error"]["code"] == "validation_error"
    assert body["request_id"]
    assert REQUEST_ID_HEADER in response.headers


def test_unhandled_error_hides_internals(client: TestClient) -> None:
    response = client.get("/__boom")
    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal server error"
    assert body["error"]["code"] == "internal_error"
    assert "secret internals" not in str(body)


def test_openapi_has_description_and_tags(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "event ingestion" in spec["info"]["description"].lower()
    tag_names = {tag["name"] for tag in spec["tags"]}
    assert {"health", "events", "queries", "api-keys"}.issubset(tag_names)


def test_docs_are_served(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
