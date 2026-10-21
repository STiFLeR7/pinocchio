"""Unit tests for the AP-306 Research Engine (RSSProvider, ResearchService)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.core.types import EventType
from nexus.intelligence.openrouter import OpenRouterClient
from nexus.intelligence.research import ResearchService, RSSProvider
from nexus.memory.models import (
    AuditLogRecord,
    ResearchFindingRecord,
    WorkflowCheckpointRecord,
)
from nexus.memory.service import MemoryService


@pytest.fixture
def mock_openrouter() -> OpenRouterClient:
    client = MagicMock(spec=OpenRouterClient)
    client.complete = AsyncMock(
        return_value='{"summary": "Test distilled summary.", "importance_score": 4, "tags": ["test", "ai"]}'
    )
    return client


# Sample feed XML payloads
SAMPLE_RSS_FEED = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
    <title>AI News Feed</title>
    <link>https://example.com/ai-news</link>
    <description>Latest in AI</description>
    <item>
        <title>New Open Source LLM Released</title>
        <link>https://example.com/item/1</link>
        <description>A new model has been released with 70B parameters.</description>
        <pubDate>Mon, 22 Jun 2026 10:00:00 +0000</pubDate>
    </item>
</channel>
</rss>
"""

SAMPLE_ATOM_FEED = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>OpenRouter Releases</title>
    <link href="https://example.com/openrouter-news"/>
    <updated>2026-06-22T10:30:00Z</updated>
    <entry>
        <title>Model price reduction update</title>
        <link href="https://example.com/entry/1"/>
        <summary>OpenRouter has reduced prices for the primary Claude fallback model.</summary>
        <published>2026-06-22T10:15:00Z</published>
    </entry>
</feed>
"""


def test_rss_provider_parse_rss() -> None:
    """Verify RSS feed parsing yields normalized elements and datetime objects."""
    provider = RSSProvider()
    findings = provider._parse_feed_xml(SAMPLE_RSS_FEED, "openai")

    assert len(findings) == 1
    item = findings[0]
    assert item["source"] == "openai"
    assert item["title"] == "New Open Source LLM Released"
    assert item["url"] == "https://example.com/item/1"
    assert "70B parameters" in item["summary"]
    assert isinstance(item["published_at"], datetime)
    assert item["published_at"].year == 2026


def test_rss_provider_parse_atom() -> None:
    """Verify Atom feed parsing yields normalized elements and datetime objects."""
    provider = RSSProvider()
    findings = provider._parse_feed_xml(SAMPLE_ATOM_FEED, "openrouter")

    assert len(findings) == 1
    item = findings[0]
    assert item["source"] == "openrouter"
    assert item["title"] == "Model price reduction update"
    assert item["url"] == "https://example.com/entry/1"
    assert "reduced prices" in item["summary"]
    assert isinstance(item["published_at"], datetime)
    assert item["published_at"].minute == 15


@pytest.mark.asyncio
async def test_research_service_successful_run(
    db_session: AsyncSession,
    mock_openrouter: OpenRouterClient,
) -> None:
    """Verify ResearchService crawls, deduplicates, summarizes, and persists finding records."""
    memory_service = MemoryService(db_session)
    service = ResearchService(db_session, mock_openrouter, memory_service)

    # Mock RSS feed fetcher
    mock_collect = AsyncMock(
        return_value=[
            {
                "source": "openai",
                "title": "GPT-5 Announcement",
                "url": "https://example.com/gpt5",
                "summary": "Full specs announced today.",
                "published_at": datetime(2026, 6, 22, 12, 0, tzinfo=UTC),
            }
        ]
    )

    rss_prov = service._providers["rss_provider"]
    rss_prov.collect_sources = mock_collect

    # Execute
    workflow_id = uuid.uuid4()
    persisted_ids = await service.execute_research_run(
        feeds={"openai": "https://openai.com/blog/rss.xml"},
        workflow_id=workflow_id,
    )

    assert len(persisted_ids) == 1
    finding_id = persisted_ids[0]

    # Verify Database finding
    stmt = select(ResearchFindingRecord).where(ResearchFindingRecord.id == finding_id)
    res = await db_session.execute(stmt)
    finding = res.scalar_one()

    assert finding.title == "GPT-5 Announcement"
    assert finding.source == "openai"
    assert finding.url == "https://example.com/gpt5"
    assert finding.importance_score == 4
    assert finding.tags == ["test", "ai"]
    assert finding.summary == "Test distilled summary."

    # Verify audit logs
    audit_stmt = select(AuditLogRecord).where(AuditLogRecord.event_type == EventType.RESEARCH_COMPLETED.value)
    audit_res = await db_session.execute(audit_stmt)
    audit_log = audit_res.scalar_one_or_none()
    assert audit_log is not None
    assert str(workflow_id) in audit_log.data["run_id"]

    # Verify Checkpoint is stored as completed
    chk_stmt = (
        select(WorkflowCheckpointRecord)
        .where(WorkflowCheckpointRecord.workflow_id == workflow_id)
        .order_by(WorkflowCheckpointRecord.created_at.desc())
    )
    chk_res = await db_session.execute(chk_stmt)
    checkpoints = chk_res.scalars().all()
    assert len(checkpoints) > 0
    assert checkpoints[0].step_name == "completed"


@pytest.mark.asyncio
async def test_research_service_deduplication(
    db_session: AsyncSession,
    mock_openrouter: OpenRouterClient,
) -> None:
    """Verify that duplicate URL findings are discarded and not re-saved or re-summarized."""
    memory_service = MemoryService(db_session)
    service = ResearchService(db_session, mock_openrouter, memory_service)

    # Seed an existing finding in DB
    existing_finding = ResearchFindingRecord(
        id=uuid.uuid4(),
        source="openai",
        title="GPT-5 Announcement",
        url="https://example.com/gpt5",
        summary="Old summary",
        tags=["old"],
        importance_score=3,
        discovered_at=datetime.now(UTC),
    )
    db_session.add(existing_finding)
    await db_session.flush()

    # RSS Mock returns one duplicate, one new
    mock_collect = AsyncMock(
        return_value=[
            {
                "source": "openai",
                "title": "GPT-5 Announcement",
                "url": "https://example.com/gpt5",
                "summary": "Duplicate specs.",
                "published_at": datetime(2026, 6, 22, 12, 0, tzinfo=UTC),
            },
            {
                "source": "openai",
                "title": "DALL-E 4 Release",
                "url": "https://example.com/dalle4",
                "summary": "New model.",
                "published_at": datetime(2026, 6, 22, 13, 0, tzinfo=UTC),
            },
        ]
    )
    rss_prov = service._providers["rss_provider"]
    rss_prov.collect_sources = mock_collect

    persisted_ids = await service.execute_research_run(
        feeds={"openai": "https://openai.com/blog/rss.xml"}
    )

    assert len(persisted_ids) == 1

    # Assert only DALL-E 4 was saved
    stmt = select(ResearchFindingRecord).where(ResearchFindingRecord.id == persisted_ids[0])
    res = await db_session.execute(stmt)
    finding = res.scalar_one()
    assert finding.title == "DALL-E 4 Release"


@pytest.mark.asyncio
async def test_research_checkpoint_recovery_resume(
    db_session: AsyncSession,
    mock_openrouter: OpenRouterClient,
) -> None:
    """Verify that a research loop can resume from a mid-execution checkpoint state."""
    memory_service = MemoryService(db_session)
    service = ResearchService(db_session, mock_openrouter, memory_service)

    # 1. Manually create a "deduplicated" state checkpoint
    workflow_id = uuid.uuid4()
    checkpoint_state = {
        "run_id": str(workflow_id),
        "step": "deduplicated",
        "feeds": {"openai": "https://openai.com/blog/rss.xml"},
        "findings": [
            {
                "source": "openai",
                "title": "Sora 2 Details",
                "url": "https://example.com/sora2",
                "summary": "Video generator updates.",
                "published_at": datetime(2026, 6, 22, 14, 0, tzinfo=UTC).isoformat(),
            }
        ],
    }
    await memory_service.create_checkpoint(workflow_id, "deduplicated", checkpoint_state)

    # 2. Resume execution
    persisted_ids = await service.resume_research_run(workflow_id)

    assert len(persisted_ids) == 1
    finding_id = persisted_ids[0]

    # Verify Sora 2 is processed and persisted
    stmt = select(ResearchFindingRecord).where(ResearchFindingRecord.id == finding_id)
    res = await db_session.execute(stmt)
    finding = res.scalar_one()
    assert finding.title == "Sora 2 Details"
    assert finding.summary == "Test distilled summary."
