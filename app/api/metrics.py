"""Prometheus scrape endpoint."""

from fastapi import APIRouter
from starlette.responses import Response

from app.core.metrics import CONTENT_TYPE, render_metrics

router = APIRouter(tags=["observability"])


@router.get("/metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics in text exposition format."""
    return Response(content=render_metrics(), media_type=CONTENT_TYPE)
