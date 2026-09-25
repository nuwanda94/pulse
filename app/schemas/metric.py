"""Pydantic schemas for metric aggregation queries."""

from datetime import datetime

from pydantic import BaseModel, Field


class MetricAggregateRead(BaseModel):
    """Current count/sum/avg for a named metric."""

    name: str
    count: int
    sum: float
    avg: float


class TimeseriesPoint(BaseModel):
    """One bucket in a timeseries."""

    bucket_start: datetime
    count: int
    sum: float
    avg: float


class MetricTimeseriesRead(BaseModel):
    """Bucketed series for a named metric."""

    name: str
    interval_seconds: int = Field(gt=0)
    points: list[TimeseriesPoint]
