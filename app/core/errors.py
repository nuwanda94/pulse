"""Consistent HTTP error envelopes and FastAPI exception handlers."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.request_context import REQUEST_ID_HEADER

STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "unavailable",
}


def request_id_of(request: Request) -> str:
    """Return the request id bound by middleware, or unknown."""
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    header = request.headers.get(REQUEST_ID_HEADER)
    if header and header.strip():
        return header.strip()
    return "unknown"


def error_body(
    *,
    status_code: int,
    detail: Any,
    request_id: str,
    extra_details: Any | None = None,
) -> dict[str, Any]:
    """Build a body that keeps FastAPI's `detail` field and adds an envelope."""
    if isinstance(detail, str):
        message = detail
    elif isinstance(detail, list):
        message = "Request validation failed"
    else:
        message = "Request failed"
    code = STATUS_CODES.get(status_code, "http_error")
    payload: dict[str, Any] = {
        "detail": detail,
        "error": {"code": code, "message": message},
        "request_id": request_id,
    }
    if extra_details is not None:
        payload["error"]["details"] = extra_details
    return payload


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Serialize HTTPException with a stable envelope."""
    if not isinstance(exc, HTTPException):
        return await unhandled_exception_handler(request, exc)
    body = error_body(
        status_code=exc.status_code,
        detail=exc.detail,
        request_id=request_id_of(request),
    )
    headers = dict(exc.headers or {})
    headers.setdefault(REQUEST_ID_HEADER, request_id_of(request))
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Serialize validation errors with a stable envelope."""
    if not isinstance(exc, RequestValidationError):
        return await unhandled_exception_handler(request, exc)
    errors = jsonable_encoder(exc.errors())
    body = error_body(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=errors,
        request_id=request_id_of(request),
        extra_details=errors,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=body,
        headers={REQUEST_ID_HEADER: request_id_of(request)},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Hide internal exceptions behind a generic 500 envelope."""
    del exc
    body = error_body(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
        request_id=request_id_of(request),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=body,
        headers={REQUEST_ID_HEADER: request_id_of(request)},
    )


def register_exception_handlers(application: FastAPI) -> None:
    """Attach Pulse error handlers to the application."""
    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(Exception, unhandled_exception_handler)
