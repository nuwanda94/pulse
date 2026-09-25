"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Env-based configuration for Pulse."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_name: str = Field(default="Pulse")
    debug: bool = Field(default=False)
    database_url: str = Field(
        default="postgresql+asyncpg://pulse:pulse@localhost:5432/pulse",
    )
    redis_url: str = Field(default="redis://localhost:6379/0")
    api_key_header: str = Field(default="X-API-Key")
    rate_limit_requests: int = Field(default=1000, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    log_level: LogLevel = Field(default="INFO")

    @field_validator("database_url")
    @classmethod
    def _require_postgres_url(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+asyncpg://")):
            msg = "DATABASE_URL must be a postgresql or postgresql+asyncpg URL"
            raise ValueError(msg)
        return value

    @field_validator("redis_url")
    @classmethod
    def _require_redis_url(cls, value: str) -> str:
        if not value.startswith(("redis://", "rediss://")):
            msg = "REDIS_URL must be a redis or rediss URL"
            raise ValueError(msg)
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.upper()
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
