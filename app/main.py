"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.api_keys import router as api_keys_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.core.config import Settings, get_settings
from app.core.metrics import MetricsMiddleware
from app.db.session import create_engine, create_session_factory


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    yield
    engine = getattr(application.state, "engine", None)
    if engine is not None:
        await engine.dispose()


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    engine: AsyncEngine | None = None,
) -> FastAPI:
    """Build and return the Pulse FastAPI application."""
    resolved = settings or get_settings()
    application = FastAPI(
        title=resolved.app_name,
        debug=resolved.debug,
        lifespan=lifespan,
    )
    application.state.settings = resolved
    if session_factory is not None:
        application.state.session_factory = session_factory
        application.state.engine = engine
    else:
        built_engine = create_engine(resolved.database_url, echo=resolved.debug)
        application.state.engine = built_engine
        application.state.session_factory = create_session_factory(built_engine)
    application.add_middleware(MetricsMiddleware)
    application.include_router(health_router)
    application.include_router(metrics_router)
    application.include_router(auth_router)
    application.include_router(api_keys_router)
    return application


app = create_app()
