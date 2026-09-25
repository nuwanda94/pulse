import os
from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_settings() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_name == "Pulse"
    assert settings.debug is False
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.redis_url.startswith("redis://")
    assert settings.api_key_header == "X-API-Key"
    assert settings.rate_limit_requests == 1000
    assert settings.rate_limit_window_seconds == 60
    assert settings.log_level == "INFO"


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Pulse Test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@db:5432/pulse_test",
    )
    monkeypatch.setenv("REDIS_URL", "redis://cache:6379/2")
    monkeypatch.setenv("API_KEY_HEADER", "X-Pulse-Key")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "50")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "30")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = Settings(_env_file=None)
    assert settings.app_name == "Pulse Test"
    assert settings.debug is True
    assert "db:5432" in settings.database_url
    assert "cache:6379" in settings.redis_url
    assert settings.api_key_header == "X-Pulse-Key"
    assert settings.rate_limit_requests == 50
    assert settings.rate_limit_window_seconds == 30
    assert settings.log_level == "DEBUG"


def test_invalid_rate_limit_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(rate_limit_requests=0, _env_file=None)


def test_invalid_database_url_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="mysql://localhost/db", _env_file=None)


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "cached")
    first = get_settings()
    monkeypatch.setenv("APP_NAME", "changed")
    second = get_settings()
    assert first is second
    assert first.app_name == "cached"


def test_env_example_exists() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    assert os.path.isfile(os.path.join(root, ".env.example"))
