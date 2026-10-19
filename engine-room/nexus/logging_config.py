"""Structured logging configuration for Nexus.

Provides ``setup_logging()`` which configures :mod:`structlog` with
appropriate processors and renderers for production (JSON) and
development (coloured console) environments.
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(level: str = "INFO", log_format: str = "json") -> None:
    """Configure structlog and stdlib logging.

    Args:
        level: Root log level name (e.g. ``"INFO"``, ``"DEBUG"``).
        log_format: ``"json"`` for machine-readable output,
            ``"console"`` for human-readable coloured output.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Shared processor chain
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

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

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "aiosqlite", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
