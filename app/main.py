"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.core.config import Settings, get_settings
from app.core.metrics import MetricsMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the Pulse FastAPI application."""
    resolved = settings or get_settings()
    application = FastAPI(
        title=resolved.app_name,
        debug=resolved.debug,
        lifespan=lifespan,
    )
    application.state.settings = resolved
    application.add_middleware(MetricsMiddleware)
    application.include_router(health_router)
    application.include_router(metrics_router)
    return application


app = create_app()
