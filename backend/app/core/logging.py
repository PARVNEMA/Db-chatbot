"""Structured logging configuration.

Uses ``structlog`` to produce JSON-formatted log output with contextual
processors (timestamps, log level, request ID, etc.).  Call
``setup_logging()`` once at application startup.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import get_settings


def setup_logging() -> None:
    """Configure ``structlog`` and the standard ``logging`` module.

    * In **dev** the log level is ``DEBUG`` and output is coloured for
      the console.
    * In **staging / prod** the log level is ``INFO`` and output is
      JSON for machine consumption.
    """
    settings = get_settings()

    log_level = logging.DEBUG if settings.ENVIRONMENT == "dev" else logging.INFO
    is_dev = settings.ENVIRONMENT == "dev"

    # Shared processors applied to every log event.
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.processors.UnicodeDecoder(),
    ]

    if is_dev:
        # Pretty, coloured, and readable output for local development.
        renderer: structlog.types.Processor = (
            structlog.dev.ConsoleRenderer(colors=True, pad_event=25)
        )
    else:
        # Machine-readable JSON for production.
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Quieten noisy third-party loggers.
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(logger_name).handlers.clear()
        logging.getLogger(logger_name).propagate = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a *structlog* bound logger for the given *name*.

    Usage::

        logger = get_logger(__name__)
        logger.info("something happened", user_id=42)
    """
    return structlog.get_logger(name)