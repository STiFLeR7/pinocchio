"""Async database engine, session management, and ORM base.

Provides:
- ``create_engine()`` — builds an async SQLAlchemy engine with SQLite
  WAL mode and foreign-key enforcement.
- ``async_session_factory()`` — returns a configured
  ``async_sessionmaker``.
- ``get_session()`` — async context manager yielding a session with
  automatic commit / rollback.
- ``Base`` — declarative base for all ORM models.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Boolean, DateTime, Uuid

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger("nexus.database")


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all Nexus ORM models."""

    pass


# ---------------------------------------------------------------------------
# Common mixin
# ---------------------------------------------------------------------------


class TimestampMixin:
    """Mixin that adds id, created_at, updated_at, and is_archived columns."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )


class AuditMixin:
    """Mixin for immutable, append-only tables (id + created_at only)."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# Engine creation
# ---------------------------------------------------------------------------


def _set_sqlite_pragmas(dbapi_conn: Any, _connection_record: Any) -> None:
    """Set WAL mode and enable foreign keys on every new SQLite connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.close()


def create_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    """Create an async SQLAlchemy engine.

    Args:
        database_url: SQLAlchemy-style connection URL.
        echo: If ``True``, log all SQL statements.

    Returns:
        Configured ``AsyncEngine`` with SQLite pragmas applied.
    """
    engine = create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
    )

    # Register sync-level event listener for SQLite pragmas
    sa_event.listen(
        engine.sync_engine,
        "connect",
        _set_sqlite_pragmas,
    )

    logger.info("database_engine_created", url=database_url)
    return engine


def async_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build a session factory bound to the given engine.

    Args:
        engine: The ``AsyncEngine`` to bind sessions to.

    Returns:
        An ``async_sessionmaker`` producing ``AsyncSession`` instances.
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@asynccontextmanager
async def get_session(
    session_factory: Any,
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session with automatic commit / rollback and track transaction durations.

    Args:
        session_factory: The session factory to use.

    Yields:
        An ``AsyncSession`` that commits on success or rolls back on error.
    """
    import time
    start_time = time.perf_counter()
    session = session_factory()
    try:
        yield session
        commit_start = time.perf_counter()
        await session.commit()
        commit_duration = (time.perf_counter() - commit_start) * 1000.0
        tx_duration = (time.perf_counter() - start_time) * 1000.0
        from nexus.core.metrics import record_metric
        record_metric("db_write_duration_ms", commit_duration)
        record_metric("transaction_duration_ms", tx_duration)
        logger.info(
            "db_transaction_committed",
            db_write_duration_ms=round(commit_duration, 2),
            transaction_duration_ms=round(tx_duration, 2),
        )
    except Exception:
        await session.rollback()
        tx_duration = (time.perf_counter() - start_time) * 1000.0
        from nexus.core.metrics import record_metric
        record_metric("transaction_duration_ms", tx_duration)
        logger.warning(
            "db_transaction_rolled_back",
            transaction_duration_ms=round(tx_duration, 2),
        )
        raise
    finally:
        await session.close()
