"""Lightweight ad-hoc query endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.db.session import get_db
from app.models import ApiKey
from app.schemas.query import QueryRequest, QueryResult
from app.services.queries import run_query

router = APIRouter(prefix="/v1/queries", tags=["queries"])


@router.post("", response_model=QueryResult)
async def create_query(
    payload: QueryRequest,
    _api_key: Annotated[ApiKey, Depends(require_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> QueryResult:
    """Run a single fixed-operator aggregation over stored events."""
    return await run_query(session, payload)
