"""On-read aggregation of ingested events."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event
from app.schemas.metric import MetricAggregateRead, MetricTimeseriesRead, TimeseriesPoint

INTERVALS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "1d": 86400,
}
DEFAULT_INTERVAL = "1h"


def interval_seconds(interval: str) -> int:
    key = interval.strip().lower()
    if key not in INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")
    return INTERVALS[key]


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _floor_bucket(value: datetime, seconds: int) -> datetime:
    instant = _aware(value)
    epoch = int(instant.timestamp())
    floored = epoch - (epoch % seconds)
    return datetime.fromtimestamp(floored, tz=UTC)


async def _load_events(
    session: AsyncSession,
    name: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[Event]:
    stmt = select(Event).where(Event.name == name)
    if start is not None:
        stmt = stmt.where(Event.timestamp >= _aware(start))
    if end is not None:
        stmt = stmt.where(Event.timestamp < _aware(end))
    stmt = stmt.order_by(Event.timestamp.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _summarize(name: str, values: list[float]) -> MetricAggregateRead:
    count = len(values)
    total = float(sum(values)) if count else 0.0
    avg = total / count if count else 0.0
    return MetricAggregateRead(name=name, count=count, sum=total, avg=avg)


async def aggregate_metric(
    session: AsyncSession,
    name: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> MetricAggregateRead:
    events = await _load_events(session, name, start=start, end=end)
    return _summarize(name, [event.value for event in events])


async def timeseries_metric(
    session: AsyncSession,
    name: str,
    *,
    interval: str = DEFAULT_INTERVAL,
    start: datetime | None = None,
    end: datetime | None = None,
) -> MetricTimeseriesRead:
    seconds = interval_seconds(interval)
    events = await _load_events(session, name, start=start, end=end)
    buckets: dict[datetime, list[float]] = {}
    for event in events:
        key = _floor_bucket(event.timestamp, seconds)
        buckets.setdefault(key, []).append(event.value)

    points: list[TimeseriesPoint] = []
    if start is not None and end is not None:
        cursor = _floor_bucket(start, seconds)
        stop = _aware(end)
        while cursor < stop:
            values = buckets.get(cursor, [])
            total = float(sum(values)) if values else 0.0
            count = len(values)
            points.append(
                TimeseriesPoint(
                    bucket_start=cursor,
                    count=count,
                    sum=total,
                    avg=(total / count if count else 0.0),
                )
            )
            cursor = cursor + timedelta(seconds=seconds)
    else:
        for key in sorted(buckets):
            values = buckets[key]
            total = float(sum(values))
            count = len(values)
            points.append(
                TimeseriesPoint(
                    bucket_start=key,
                    count=count,
                    sum=total,
                    avg=total / count,
                )
            )

    return MetricTimeseriesRead(name=name, interval_seconds=seconds, points=points)
