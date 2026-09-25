"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from app.core.config import Settings


def configure_logging(settings: Settings | None = None) -> None:
    """Configure stdlib logging and structlog processors.

    Safe to call more than once; processors are replaced rather than stacked.
    """
    level_name = settings.log_level if settings is not None else "INFO"
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    if settings is not None and settings.debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)
