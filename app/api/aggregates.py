"""Metric aggregation query endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.db.session import get_db
from app.models import ApiKey
from app.schemas.metric import MetricAggregateRead, MetricTimeseriesRead
from app.services.aggregates import INTERVALS, aggregate_metric, timeseries_metric

router = APIRouter(prefix="/v1/metrics", tags=["aggregates"])


@router.get("/{name}", response_model=MetricAggregateRead)
async def get_metric_aggregate(
    name: str,
    _api_key: Annotated[ApiKey, Depends(require_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> MetricAggregateRead:
    """Return the current count/sum/avg for ``name``, computed on read."""
    summary = await aggregate_metric(session, name, start=start, end=end)
    if summary.count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown metric")
    return summary


@router.get("/{name}/timeseries", response_model=MetricTimeseriesRead)
async def get_metric_timeseries(
    name: str,
    _api_key: Annotated[ApiKey, Depends(require_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
    interval: Annotated[str, Query()] = "1h",
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> MetricTimeseriesRead:
    """Return a bucketed timeseries for ``name``."""
    if interval not in INTERVALS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"interval must be one of: {', '.join(INTERVALS)}",
        )
    return await timeseries_metric(
        session, name, interval=interval, start=start, end=end
    )
