"""Unit tests for the AP-502 Telemetry Metrics Persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus import __version__
from nexus.core.metrics import (
    compare_metric_versions,
    flush_metrics_to_db,
    query_metric_history,
    record_metric,
    run_aggregation_and_retention,
)
from nexus.memory.models import SystemMetricAggregateRecord, SystemMetricRawRecord


@pytest.mark.asyncio
async def test_metrics_flushing_persistence(db_session: AsyncSession) -> None:
    """Verify that calling record_metric and flushing commits raw metrics to sqlite."""
    # Clear write buffer first
    from nexus.core import metrics
    metrics._write_buffer = []

    # Record some test metrics
    record_metric("db_write_duration_ms", 12.5)
    record_metric("db_write_duration_ms", 18.2)
    record_metric("transaction_duration_ms", 45.1)

    # Flush to database
    await flush_metrics_to_db(db_session)

    # Force identity map expiration
    db_session.expire_all()

    # Verify rows written
    stmt = select(SystemMetricRawRecord).order_by(SystemMetricRawRecord.created_at.asc())
    res = await db_session.execute(stmt)
    records = res.scalars().all()

    assert len(records) == 3
    assert records[0].metric_name == "db_write_duration_ms"
    assert records[0].metric_value == 12.5
    assert records[0].release_version == __version__
    assert records[1].metric_value == 18.2
    assert records[2].metric_name == "transaction_duration_ms"
    assert records[2].metric_value == 45.1


@pytest.mark.asyncio
async def test_metrics_hourly_aggregation(db_session: AsyncSession) -> None:
    """Verify that raw metrics from the previous hour are correctly aggregated."""
    now = datetime.now(UTC)
    last_hour = now - timedelta(minutes=45)

    # Seed raw metrics in the database representing the past hour
    db_session.add_all([
        SystemMetricRawRecord(
            id=uuid.uuid4(),
            metric_name="transaction_duration_ms",
            metric_value=20.0,
            release_version="0.5.0",
            created_at=last_hour,
        ),
        SystemMetricRawRecord(
            id=uuid.uuid4(),
            metric_name="transaction_duration_ms",
            metric_value=30.0,
            release_version="0.5.0",
            created_at=last_hour,
        ),
        SystemMetricRawRecord(
            id=uuid.uuid4(),
            metric_name="transaction_duration_ms",
            metric_value=40.0,
            release_version="0.5.0",
            created_at=last_hour,
        ),
    ])
    await db_session.commit()

    # Run aggregation
    await run_aggregation_and_retention(db_session, baseline_ver="0.5.0-baseline")

    db_session.expire_all()

    # Verify hourly aggregate committed
    stmt = select(SystemMetricAggregateRecord).where(
        SystemMetricAggregateRecord.metric_name == "transaction_duration_ms"
    )
    res = await db_session.execute(stmt)
    aggregates = res.scalars().all()

    assert len(aggregates) == 1
    agg = aggregates[0]
    assert agg.avg_value == 30.0
    assert agg.max_value == 40.0
    assert agg.min_value == 20.0
    assert agg.entry_count == 3
    assert agg.baseline_version == "0.5.0-baseline"
    assert agg.release_version == __version__
    assert agg.measurement_window == "hourly"


@pytest.mark.asyncio
async def test_metrics_retention_purging(db_session: AsyncSession) -> None:
    """Verify that raw metrics >7 days and aggregates >90 days are automatically purged."""
    now = datetime.now(UTC)

    # 8 days old raw metric (should be deleted)
    old_raw = SystemMetricRawRecord(
        id=uuid.uuid4(),
        metric_name="db_write_duration_ms",
        metric_value=15.0,
        release_version="0.5.0",
        created_at=now - timedelta(days=8),
    )
    # 2 days old raw metric (should be kept)
    new_raw = SystemMetricRawRecord(
        id=uuid.uuid4(),
        metric_name="db_write_duration_ms",
        metric_value=25.0,
        release_version="0.5.0",
        created_at=now - timedelta(days=2),
    )

    # 95 days old aggregate (should be deleted)
    old_agg = SystemMetricAggregateRecord(
        id=uuid.uuid4(),
        metric_name="db_write_duration_ms",
        avg_value=12.0,
        max_value=20.0,
        min_value=5.0,
        entry_count=10,
        baseline_version="0.5.0-baseline",
        release_version="0.5.0",
        measurement_window="hourly",
        aggregated_at=now - timedelta(days=95),
    )
    # 30 days old aggregate (should be kept)
    new_agg = SystemMetricAggregateRecord(
        id=uuid.uuid4(),
        metric_name="db_write_duration_ms",
        avg_value=15.0,
        max_value=25.0,
        min_value=8.0,
        entry_count=12,
        baseline_version="0.5.0-baseline",
        release_version="0.5.0",
        measurement_window="hourly",
        aggregated_at=now - timedelta(days=30),
    )

    db_session.add_all([old_raw, new_raw, old_agg, new_agg])
    await db_session.commit()

    # Run purge
    await run_aggregation_and_retention(db_session)

    db_session.expire_all()

    # Check raw metrics
    raw_res = await db_session.execute(select(SystemMetricRawRecord))
    raws = raw_res.scalars().all()
    assert len(raws) == 1
    assert raws[0].id == new_raw.id

    # Check aggregates
    agg_res = await db_session.execute(select(SystemMetricAggregateRecord))
    aggs = agg_res.scalars().all()
    assert len(aggs) == 1
    assert aggs[0].id == new_agg.id


@pytest.mark.asyncio
async def test_historical_metrics_queries(db_session: AsyncSession) -> None:
    """Verify query_metric_history retrieves the correct aggregated data sequence."""
    now = datetime.now(UTC)
    db_session.add_all([
        SystemMetricAggregateRecord(
            id=uuid.uuid4(),
            metric_name="db_write_duration_ms",
            avg_value=10.0,
            max_value=12.0,
            min_value=8.0,
            entry_count=5,
            baseline_version="0.5.0-baseline",
            release_version="0.5.0",
            measurement_window="hourly",
            aggregated_at=now - timedelta(hours=3),
        ),
        SystemMetricAggregateRecord(
            id=uuid.uuid4(),
            metric_name="db_write_duration_ms",
            avg_value=15.0,
            max_value=20.0,
            min_value=10.0,
            entry_count=8,
            baseline_version="0.5.0-baseline",
            release_version="0.5.0",
            measurement_window="hourly",
            aggregated_at=now - timedelta(hours=2),
        ),
    ])
    await db_session.commit()

    history = await query_metric_history(db_session, "db_write_duration_ms", days=1)
    assert len(history) == 2
    assert history[0]["avg_value"] == 10.0
    assert history[1]["avg_value"] == 15.0


@pytest.mark.asyncio
async def test_version_comparison_telemetry(db_session: AsyncSession) -> None:
    """Verify compare_metric_versions aggregates values for release comparison scopes."""
    now = datetime.now(UTC)

    # Version A
    db_session.add(SystemMetricAggregateRecord(
        id=uuid.uuid4(),
        metric_name="transaction_duration_ms",
        avg_value=25.0,
        max_value=35.0,
        min_value=15.0,
        entry_count=10,
        baseline_version="0.5.0-baseline",
        release_version="v1_candidate_a",
        measurement_window="hourly",
        aggregated_at=now - timedelta(hours=2),
    ))

    # Version B
    db_session.add(SystemMetricAggregateRecord(
        id=uuid.uuid4(),
        metric_name="transaction_duration_ms",
        avg_value=18.0,
        max_value=24.0,
        min_value=12.0,
        entry_count=12,
        baseline_version="0.5.0-baseline",
        release_version="v1_candidate_b",
        measurement_window="hourly",
        aggregated_at=now - timedelta(hours=2),
    ))

    await db_session.commit()

    comparison = await compare_metric_versions(
        db_session, "transaction_duration_ms", "v1_candidate_a", "v1_candidate_b"
    )

    assert comparison["metric_name"] == "transaction_duration_ms"
    assert comparison["version_a"]["release_version"] == "v1_candidate_a"
    assert comparison["version_a"]["avg"] == 25.0
    assert comparison["version_a"]["count"] == 10

    assert comparison["version_b"]["release_version"] == "v1_candidate_b"
    assert comparison["version_b"]["avg"] == 18.0
    assert comparison["version_b"]["count"] == 12
