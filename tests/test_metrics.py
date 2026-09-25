from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_metrics_content_type(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    content_type = response.headers["content-type"]
    assert content_type.startswith("text/plain")


def test_metrics_contains_expected_names(client: TestClient) -> None:
    client.get("/health")
    response = client.get("/metrics")
    body = response.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_metrics_records_health_request(client: TestClient) -> None:
    client.get("/health")
    body = client.get("/metrics").text
    assert 'http_requests_total{method="GET",path="/health",status="200"}' in body
