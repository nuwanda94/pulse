"""Liveness and readiness endpoints."""

from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import Settings
from app.core.deps import check_postgres, check_redis

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


class ReadyCheck(BaseModel):
    postgres: bool
    redis: bool


class ReadyResponse(BaseModel):
    status: str
    checks: ReadyCheck


def _settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Process liveness probe; does not check dependencies."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
async def ready(request: Request) -> JSONResponse:
    """Readiness probe: Postgres and Redis must be reachable."""
    settings = _settings(request)
    postgres_ok = await check_postgres(settings.database_url)
    redis_ok = await check_redis(settings.redis_url)
    payload: dict[str, Any] = {
        "status": "ok" if postgres_ok and redis_ok else "unavailable",
        "checks": {"postgres": postgres_ok, "redis": redis_ok},
    }
    code = status.HTTP_200_OK if postgres_ok and redis_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=payload, status_code=code)
