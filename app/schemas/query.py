"""Pydantic schemas for the lightweight ad-hoc query endpoint."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ALLOWED_OPS = ("count", "sum", "avg", "min", "max")
MAX_TAG_FILTERS = 3


class QueryRequest(BaseModel):
    """Fixed-operator aggregation over ingested events."""

    name: str = Field(min_length=1, max_length=256)
    op: Literal["count", "sum", "avg", "min", "max"]
    tags: dict[str, str] = Field(default_factory=dict)
    start: datetime | None = None
    end: datetime | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be empty")
        return stripped

    @field_validator("tags")
    @classmethod
    def _limit_tags(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > MAX_TAG_FILTERS:
            raise ValueError(f"at most {MAX_TAG_FILTERS} tag filters are allowed")
        cleaned: dict[str, str] = {}
        for key, val in value.items():
            k = key.strip()
            if not k:
                raise ValueError("tag keys must not be empty")
            cleaned[k] = val
        return cleaned

    @model_validator(mode="before")
    @classmethod
    def _reject_complex(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        forbidden = {
            "group_by",
            "having",
            "joins",
            "join",
            "subquery",
            "queries",
            "pipeline",
            "sql",
            "expression",
            "expr",
        }
        present = sorted(key for key in data if key in forbidden)
        if present:
            raise ValueError(f"unsupported query fields: {', '.join(present)}")
        return data


class QueryResult(BaseModel):
    """Result of a single-operator aggregation."""

    name: str
    op: Literal["count", "sum", "avg", "min", "max"]
    value: float
    count: int
    start: datetime | None = None
    end: datetime | None = None
