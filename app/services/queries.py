"""Evaluate a restricted ad-hoc aggregation query against events."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event
from app.schemas.query import QueryRequest, QueryResult


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _matches_tags(event_tags: dict[str, Any], required: dict[str, str]) -> bool:
    for key, expected in required.items():
        actual = event_tags.get(key)
        if actual is None or str(actual) != expected:
            return False
    return True


def _compute(op: str, values: list[float]) -> float:
    if op == "count":
        return float(len(values))
    if not values:
        return 0.0
    if op == "sum":
        return float(sum(values))
    if op == "avg":
        return float(sum(values)) / len(values)
    if op == "min":
        return float(min(values))
    if op == "max":
        return float(max(values))
    raise ValueError(f"unsupported op: {op}")


async def run_query(session: AsyncSession, query: QueryRequest) -> QueryResult:
    stmt = select(Event).where(Event.name == query.name)
    if query.start is not None:
        stmt = stmt.where(Event.timestamp >= _aware(query.start))
    if query.end is not None:
        stmt = stmt.where(Event.timestamp < _aware(query.end))
    result = await session.execute(stmt)
    events = list(result.scalars().all())
    if query.tags:
        events = [event for event in events if _matches_tags(event.tags, query.tags)]
    values = [event.value for event in events]
    return QueryResult(
        name=query.name,
        op=query.op,
        value=_compute(query.op, values),
        count=len(values),
        start=query.start,
        end=query.end,
    )
