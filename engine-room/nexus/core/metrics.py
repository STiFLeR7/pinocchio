"""Nexus Core Metrics tracking and persistence module (AP-502).

Provides simple in-memory metrics aggregation and periodic database flushes.
"""

from __future__ import annotations

import asyncio
import collections
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus import __version__
from nexus.database import get_session
from nexus.memory.models import SystemMetricAggregateRecord, SystemMetricRawRecord

logger = structlog.get_logger("nexus.core.metrics")

# In-memory metrics stores for sliding-window metrics
_metrics: dict[str, collections.deque[tuple[float, float]]] = {
    "db_write_duration_ms": collections.deque(maxlen=10000),
    "transaction_duration_ms": collections.deque(maxlen=10000),
    "lock_wait_ms": collections.deque(maxlen=10000),
    "approval_latency_ms": collections.deque(maxlen=10000),
    "execution_start_latency_ms": collections.deque(maxlen=10000),
    "event_flush_duration_ms": collections.deque(maxlen=10000),
    "openrouter_latency_ms": collections.deque(maxlen=10000),
    "discord_latency_ms": collections.deque(maxlen=10000),
    "smtp_latency_ms": collections.deque(maxlen=10000),
    "briefing_generation_duration_ms": collections.deque(maxlen=10000),
}

# Volatile write buffer for database persistence
_write_buffer: list[dict[str, Any]] = []


def record_metric(name: str, value: float) -> None:
    """Record a metric data point in memory and add to write buffer."""
    now_sec = time.time()
    if name in _metrics:
        _metrics[name].append((now_sec, value))
    else:
        # Register on the fly if needed
        _metrics[name] = collections.deque(maxlen=10000)
        _metrics[name].append((now_sec, value))

    _write_buffer.append({
        "metric_name": name,
        "metric_value": value,
        "recorded_at": datetime.now(UTC),
    })


def get_metrics_summary(past_seconds: float = 86400) -> dict[str, dict[str, Any]]:
    """Aggregate metrics over the past sliding window from memory."""
    now = time.time()
    cutoff = now - past_seconds
    summary = {}
    for name, deque in _metrics.items():
        values = [val for ts, val in deque if ts >= cutoff]
        if values:
            summary[name] = {
                "avg": sum(values) / len(values),
                "max": max(values),
                "min": min(values),
                "count": len(values),
                "sum": sum(values),
            }
        else:
            summary[name] = {
                "avg": 0.0,
                "max": 0.0,
                "min": 0.0,
                "count": 0,
                "sum": 0.0,
            }
    return summary


async def flush_metrics_to_db(session_factory: Any) -> None:
    """Flush raw metrics from write buffer to database raw table."""
    global _write_buffer
    if not _write_buffer:
        return

    buffer_to_write = _write_buffer
    _write_buffer = []

    try:
        insert_data = []
        for item in buffer_to_write:
            insert_data.append({
                "id": uuid.uuid4(),
                "metric_name": item["metric_name"],
                "metric_value": item["metric_value"],
                "release_version": __version__,
                "created_at": item["recorded_at"],
            })

        from sqlalchemy.ext.asyncio import AsyncSession
        if isinstance(session_factory, AsyncSession):
            stmt = insert(SystemMetricRawRecord)
            await session_factory.execute(stmt, insert_data)
        else:
            async with get_session(session_factory) as session:
                stmt = insert(SystemMetricRawRecord)
                await session.execute(stmt, insert_data)


        logger.debug("metrics_flushed_to_db", count=len(insert_data))
    except Exception as e:
        logger.error("metrics_flush_failed", error=str(e))
        # Restore buffer to prevent data loss
        _write_buffer = buffer_to_write + _write_buffer


async def run_metrics_flush_loop(
    session_factory: Any,
    interval: float = 5.0,
) -> None:
    """Continuous loop running in background to persist raw metrics."""
    logger.info("metrics_persistence_flush_loop_started", interval=interval)
    while True:
        try:
            await flush_metrics_to_db(session_factory)
        except Exception as e:
            logger.error("metrics_flush_loop_failed", error=str(e))
        await asyncio.sleep(interval)


# ---------------------------------------------------------------------------
# Telemetry Aggregation & Retention Jobs (AP-502)
# ---------------------------------------------------------------------------


async def run_aggregation_and_retention(
    session: AsyncSession,
    baseline_ver: str = "0.5.0-baseline",
) -> None:
    """Aggregate raw metrics hourly and execute data retention purges."""
    now = datetime.now(UTC)
    one_hour_ago = now - timedelta(hours=1)

    # 1. Fetch raw metrics for previous hour
    stmt = select(
        SystemMetricRawRecord.metric_name,
        func.avg(SystemMetricRawRecord.metric_value).label("avg_val"),
        func.max(SystemMetricRawRecord.metric_value).label("max_val"),
        func.min(SystemMetricRawRecord.metric_value).label("min_val"),
        func.count(SystemMetricRawRecord.id).label("entry_cnt"),
    ).where(
        SystemMetricRawRecord.created_at >= one_hour_ago,
        SystemMetricRawRecord.created_at < now,
    ).group_by(SystemMetricRawRecord.metric_name)

    res = await session.execute(stmt)
    rows = res.all()

    for row in rows:
        # Check if already aggregated for this hour boundary to prevent duplicates
        dup_stmt = select(SystemMetricAggregateRecord).where(
            SystemMetricAggregateRecord.metric_name == row.metric_name,
            SystemMetricAggregateRecord.aggregated_at == one_hour_ago,
            SystemMetricAggregateRecord.measurement_window == "hourly",
        )
        dup_res = await session.execute(dup_stmt)
        if dup_res.scalar_one_or_none():
            continue

        agg_rec = SystemMetricAggregateRecord(
            id=uuid.uuid4(),
            metric_name=row.metric_name,
            avg_value=float(row.avg_val),
            max_value=float(row.max_val),
            min_value=float(row.min_val),
            entry_count=int(row.entry_cnt),
            baseline_version=baseline_ver,
            release_version=__version__,
            measurement_window="hourly",
            aggregated_at=one_hour_ago,
        )
        session.add(agg_rec)

    # 2. Retention Purging
    # Raw metrics: delete entries older than 7 days
    raw_retention_limit = now - timedelta(days=7)
    raw_del_stmt = delete(SystemMetricRawRecord).where(
        SystemMetricRawRecord.created_at < raw_retention_limit
    )
    await session.execute(raw_del_stmt)

    # Aggregates: delete entries older than 90 days
    agg_retention_limit = now - timedelta(days=90)
    agg_del_stmt = delete(SystemMetricAggregateRecord).where(
        SystemMetricAggregateRecord.aggregated_at < agg_retention_limit
    )
    await session.execute(agg_del_stmt)

    await session.flush()
    logger.info("metrics_aggregation_and_retention_completed")


# ---------------------------------------------------------------------------
# Historical Metrics Queries & Version Comparison Support
# ---------------------------------------------------------------------------


async def query_metric_history(
    session: AsyncSession,
    metric_name: str,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Retrieve historical hourly aggregated metric entries."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    stmt = (
        select(SystemMetricAggregateRecord)
        .where(
            SystemMetricAggregateRecord.metric_name == metric_name,
            SystemMetricAggregateRecord.aggregated_at >= cutoff,
        )
        .order_by(SystemMetricAggregateRecord.aggregated_at.asc())
    )
    res = await session.execute(stmt)
    records = res.scalars().all()

    return [
        {
            "metric_name": r.metric_name,
            "avg_value": r.avg_value,
            "max_value": r.max_value,
            "min_value": r.min_value,
            "entry_count": r.entry_count,
            "release_version": r.release_version,
            "aggregated_at": r.aggregated_at,
        }
        for r in records
    ]


async def compare_metric_versions(
    session: AsyncSession,
    metric_name: str,
    version_a: str,
    version_b: str,
) -> dict[str, Any]:
    """Compare performance metrics between two versions (release or baseline)."""
    stmt_a = select(
        func.avg(SystemMetricAggregateRecord.avg_value).label("avg_val"),
        func.max(SystemMetricAggregateRecord.max_value).label("max_val"),
        func.min(SystemMetricAggregateRecord.min_value).label("min_val"),
        func.sum(SystemMetricAggregateRecord.entry_count).label("total_cnt"),
    ).where(
        SystemMetricAggregateRecord.metric_name == metric_name,
        SystemMetricAggregateRecord.release_version == version_a,
    )
    res_a = await session.execute(stmt_a)
    row_a = res_a.one()

    stmt_b = select(
        func.avg(SystemMetricAggregateRecord.avg_value).label("avg_val"),
        func.max(SystemMetricAggregateRecord.max_value).label("max_val"),
        func.min(SystemMetricAggregateRecord.min_value).label("min_val"),
        func.sum(SystemMetricAggregateRecord.entry_count).label("total_cnt"),
    ).where(
        SystemMetricAggregateRecord.metric_name == metric_name,
        SystemMetricAggregateRecord.release_version == version_b,
    )
    res_b = await session.execute(stmt_b)
    row_b = res_b.one()

    return {
        "metric_name": metric_name,
        "version_a": {
            "release_version": version_a,
            "avg": float(row_a.avg_val or 0.0),
            "max": float(row_a.max_val or 0.0),
            "min": float(row_a.min_val or 0.0),
            "count": int(row_a.total_cnt or 0),
        },
        "version_b": {
            "release_version": version_b,
            "avg": float(row_b.avg_val or 0.0),
            "max": float(row_b.max_val or 0.0),
            "min": float(row_b.min_val or 0.0),
            "count": int(row_b.total_cnt or 0),
        },
    }
