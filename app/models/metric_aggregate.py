"""Pre-aggregated metric buckets."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MetricAggregate(Base):
    """Count/sum/avg for a named metric over a time bucket."""

    __tablename__ = "metric_aggregates"
    __table_args__ = (
        UniqueConstraint("name", "bucket_start", name="uq_metric_aggregates_name_bucket"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sum: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
