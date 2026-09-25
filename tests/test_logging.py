from collections.abc import Iterator

import pytest
import structlog
from fastapi.testclient import TestClient
from structlog.testing import CapturingLogger

from app.core.config import Settings
from app.core.logging import configure_logging, get_logger
from app.core.request_context import REQUEST_ID_HEADER, generate_request_id
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_generate_request_id_is_unique() -> None:
    first = generate_request_id()
    second = generate_request_id()
    assert first != second
    assert len(first) >= 8


def test_health_echoes_generated_request_id(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert REQUEST_ID_HEADER in response.headers
    assert response.headers[REQUEST_ID_HEADER]


def test_health_propagates_incoming_request_id(client: TestClient) -> None:
    request_id = "req-test-123"
    response = client.get("/health", headers={REQUEST_ID_HEADER: request_id})
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == request_id


def test_configure_logging_and_get_logger() -> None:
    configure_logging(Settings(_env_file=None, log_level="DEBUG", debug=True))
    logger = get_logger("pulse.test")
    logger.info("hello", extra_field=1)


def test_request_completed_log_contains_expected_fields(settings: Settings) -> None:
    capturing = CapturingLogger()
    app = create_app(settings)
    structlog.configure(
        processors=[structlog.contextvars.merge_contextvars],
        logger_factory=lambda *args, **kwargs: capturing,
        wrapper_class=structlog.BoundLogger,
        cache_logger_on_first_use=False,
    )
    with TestClient(app) as test_client:
        test_client.get("/health", headers={REQUEST_ID_HEADER: "rid-abc"})

    messages: list[dict[str, object]] = []
    for method, args, kwargs in capturing.calls:
        if method not in {"info", "msg", "exception"}:
            continue
        if isinstance(kwargs, dict) and kwargs:
            messages.append(kwargs)
        elif args and isinstance(args[-1], dict):
            messages.append(args[-1])
    completed = [m for m in messages if m.get("event") == "request_completed"]
    assert completed, f"expected request_completed log, got {capturing.calls!r}"
    record = completed[-1]
    assert record["request_id"] == "rid-abc"
    assert record["method"] == "GET"
    assert record["path"] == "/health"
    assert record["status_code"] == 200
    assert "duration_ms" in record
    assert isinstance(record["duration_ms"], float | int)
