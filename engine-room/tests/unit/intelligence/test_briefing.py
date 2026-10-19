"""Unit tests for the AP-307 Daily Briefing Engine (BriefingService, BriefingType)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.communication.discord.service import DiscordService
from nexus.communication.email.service import EmailService
from nexus.intelligence.briefing import BriefingService, BriefingType
from nexus.memory.models import (
    BriefingRecord,
    ResearchFindingRecord,
    TaskRecord,
    WorkflowCheckpointRecord,
)
from nexus.memory.service import MemoryService


@pytest.fixture
def mock_discord() -> DiscordService:
    service = MagicMock(spec=DiscordService)
    service.post_message = AsyncMock(return_value=MagicMock())
    return service


@pytest.fixture
def mock_email() -> EmailService:
    service = MagicMock(spec=EmailService)
    service.send_briefing_email = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_briefing_generation_successful_run(
    db_session: AsyncSession,
    mock_discord: DiscordService,
    mock_email: EmailService,
) -> None:
    """Verify BriefingService aggregates database entities, persists BriefingRecord, and dispatches to channels."""
    memory_service = MemoryService(db_session)
    service = BriefingService(db_session, memory_service, mock_discord, mock_email)

    # Seed open task
    task = TaskRecord(
        id=uuid.uuid4(),
        title="Deploy API Server",
        status="active",
        priority=3,
    )
    db_session.add(task)

    # Seed research finding
    finding = ResearchFindingRecord(
        id=uuid.uuid4(),
        source="openai",
        title="GPT-5 Specs",
        url="https://example.com/gpt5",
        summary="Summarized GPT5 specifications.",
        tags=["specs"],
        importance_score=5,
        discovered_at=datetime.now(UTC),
    )
    db_session.add(finding)
    await db_session.flush()

    # Execute
    workflow_id = uuid.uuid4()
    briefing_id = await service.generate_and_dispatch_briefing(
        briefing_type=BriefingType.MORNING,
        channels=["memory", "discord", "email"],
        workflow_id=workflow_id,
    )

    # Verify briefing persisted
    stmt = select(BriefingRecord).where(BriefingRecord.id == briefing_id)
    res = await db_session.execute(stmt)
    briefing = res.scalar_one()

    assert briefing.briefing_type == "morning"
    assert briefing.status == "sent"
    assert briefing.finding_count == 1
    assert "GPT-5 Specs" in briefing.summary
    assert "Deploy API Server" in briefing.summary

    # Verify channel dispatches called
    mock_discord.post_message.assert_called()
    mock_email.send_briefing_email.assert_called()

    # Verify Checkpoints
    chk_stmt = (
        select(WorkflowCheckpointRecord)
        .where(WorkflowCheckpointRecord.workflow_id == workflow_id)
        .order_by(WorkflowCheckpointRecord.created_at.desc())
    )
    chk_res = await db_session.execute(chk_stmt)
    chk = chk_res.scalars().all()
    assert len(chk) > 0
    assert chk[0].step_name == "completed"


@pytest.mark.asyncio
async def test_briefing_no_findings_run(
    db_session: AsyncSession,
    mock_discord: DiscordService,
) -> None:
    """Verify briefing generates correctly when there are no research findings in the past 24 hours."""
    memory_service = MemoryService(db_session)
    service = BriefingService(db_session, memory_service, mock_discord, None)

    briefing_id = await service.generate_and_dispatch_briefing(
        briefing_type=BriefingType.OPERATIONAL,
        channels=["memory", "discord"],
    )

    stmt = select(BriefingRecord).where(BriefingRecord.id == briefing_id)
    res = await db_session.execute(stmt)
    briefing = res.scalar_one()

    assert briefing.finding_count == 0
    assert "No new technical research items" in briefing.summary
    assert briefing.status == "sent"


@pytest.mark.asyncio
async def test_briefing_discord_delivery_failure_partial_status(
    db_session: AsyncSession,
    mock_discord: DiscordService,
    mock_email: EmailService,
) -> None:
    """Verify that a channel delivery exception flags the briefing status as partial and saves checkpoints."""
    memory_service = MemoryService(db_session)
    service = BriefingService(db_session, memory_service, mock_discord, mock_email)

    # Make Discord trigger an error
    mock_discord.post_message.side_effect = Exception("Discord rate limit error")

    workflow_id = uuid.uuid4()
    briefing_id = await service.generate_and_dispatch_briefing(
        briefing_type=BriefingType.FAILURE,
        channels=["memory", "discord", "email"],
        workflow_id=workflow_id,
    )

    stmt = select(BriefingRecord).where(BriefingRecord.id == briefing_id)
    res = await db_session.execute(stmt)
    briefing = res.scalar_one()

    # Should be "partial" because Discord failed but email/memory succeeded
    assert briefing.status == "partial"
    assert "email" in briefing.delivery_channels
    assert "discord" not in briefing.delivery_channels

    # Restore checkpoint should return discord_delivered (as last step before SMTP)
    chk_state = await memory_service.restore_checkpoint(workflow_id)
    assert chk_state["step"] == "completed"
    assert "discord" not in chk_state["delivered_channels"]


@pytest.mark.asyncio
async def test_briefing_delivery_recovery_resume(
    db_session: AsyncSession,
    mock_discord: DiscordService,
    mock_email: EmailService,
) -> None:
    """Verify that resuming a failed delivery checkpoint retries the failed channel and completes status."""
    memory_service = MemoryService(db_session)
    service = BriefingService(db_session, memory_service, mock_discord, mock_email)

    workflow_id = uuid.uuid4()
    briefing_id = uuid.uuid4()

    # Seed a pre-existing partial BriefingRecord
    briefing_rec = BriefingRecord(
        id=briefing_id,
        briefing_type="morning",
        generated_at=datetime.now(UTC),
        delivery_channels=["memory"],
        content_hash="mock_hash_123",
        finding_count=0,
        status="partial",
        summary="Mock summary contents.",
    )
    db_session.add(briefing_rec)
    await db_session.flush()

    # Create checkpoint matching local_delivered (i.e. only memory succeeded)
    checkpoint_state = {
        "run_id": str(workflow_id),
        "step": "local_delivered",
        "briefing_type": "morning",
        "channels": ["memory", "discord", "email"],
        "delivered_channels": ["memory"],
        "briefing_id": str(briefing_id),
    }
    await memory_service.create_checkpoint(workflow_id, "local_delivered", checkpoint_state)

    # Resume
    resumed_id = await service.resume_briefing_run(workflow_id)

    assert resumed_id == briefing_id

    # Verify database update
    stmt = select(BriefingRecord).where(BriefingRecord.id == briefing_id)
    res = await db_session.execute(stmt)
    briefing = res.scalar_one()

    assert briefing.status == "sent"
    assert "discord" in briefing.delivery_channels
    assert "email" in briefing.delivery_channels
