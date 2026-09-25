"""Request-id generation/propagation and request timing middleware."""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


def generate_request_id() -> str:
    """Return a new opaque request identifier."""
    return str(uuid.uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind request_id, method, path; echo request id; log duration."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming.strip() if incoming and incoming.strip() else generate_request_id()
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        logger = structlog.get_logger("pulse.request")
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception("request_failed", duration_ms=round(elapsed_ms, 3))
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(elapsed_ms, 3),
        )
        return response
