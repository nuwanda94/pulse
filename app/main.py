"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.api_keys import router as api_keys_router
from app.api.auth import router as auth_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.usage import router as usage_router
from app.core.config import Settings, get_settings
from app.core.metrics import MetricsMiddleware
from app.core.rate_limit import InMemoryRateLimitBackend, RateLimiter, RedisRateLimitBackend
from app.db.session import create_engine, create_session_factory


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    if not getattr(application.state, "rate_limiter_locked", False):
        try:
            redis_client = Redis.from_url(
                application.state.settings.redis_url,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
            await redis_client.ping()
            application.state.redis = redis_client
            application.state.rate_limiter = RateLimiter(RedisRateLimitBackend(redis_client))
        except Exception:
            if getattr(application.state, "rate_limiter", None) is None:
                application.state.rate_limiter = RateLimiter(InMemoryRateLimitBackend())
    yield
    engine = getattr(application.state, "engine", None)
    if engine is not None:
        await engine.dispose()
    redis = getattr(application.state, "redis", None)
    if redis is not None:
        await redis.aclose()


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    engine: AsyncEngine | None = None,
    rate_limiter: RateLimiter | None = None,
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
    if rate_limiter is not None:
        application.state.rate_limiter = rate_limiter
        application.state.rate_limiter_locked = True
    else:
        application.state.rate_limiter = RateLimiter(InMemoryRateLimitBackend())
        application.state.rate_limiter_locked = False
    application.add_middleware(MetricsMiddleware)
    application.include_router(health_router)
    application.include_router(metrics_router)
    application.include_router(auth_router)
    application.include_router(api_keys_router)
    application.include_router(events_router)
    application.include_router(usage_router)
    return application


app = create_app()
