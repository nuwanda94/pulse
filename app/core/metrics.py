"""Prometheus metrics registry, instruments, and ASGI middleware."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

REGISTRY = CollectorRegistry()

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=("method", "path", "status"),
    registry=REGISTRY,
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=("method", "path"),
    registry=REGISTRY,
)

CONTENT_TYPE = CONTENT_TYPE_LATEST


def render_metrics() -> bytes:
    """Serialize the process registry in Prometheus text format."""
    return generate_latest(REGISTRY)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request count and latency for every request except /metrics."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        # Prefer the matched route template when available to keep cardinality low.
        template = request.url.path
        route = request.scope.get("route")
        if route is not None and getattr(route, "path", None):
            template = str(route.path)
        REQUEST_COUNT.labels(
            method=request.method,
            path=template,
            status=str(response.status_code),
        ).inc()
        REQUEST_LATENCY.labels(method=request.method, path=template).observe(elapsed)
        return response
