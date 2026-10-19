"""E2E tests for the proactive Priority Feed.

Exercises the full path with a real database session:
research findings → PriorityFeedService (importance filter + influencer digest + channel routing)
→ transactional outbox → outbox delivery resolves to the #priority-feed channel, mentioning owner.

No Discord, no network: a fake discord service captures which channel each post targets.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from nexus.gateway.communication_outbox import (
    _deliver_discord_chunks,
    flush_outbox_synchronously,
)
from nexus.intelligence.feed import PriorityFeedService
from nexus.memory.models import ResearchFindingRecord, SystemOutboxRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from nexus.config import NexusSettings


class FakeDiscord:
    """Captures (channel_key, content) instead of touching Discord."""

    def __init__(self) -> None:
        self.posts: list[tuple[str, str]] = []

    async def post_message(self, channel_key: str, content: str | None = None, **_: object) -> None:
        self.posts.append((channel_key, content or ""))


async def _add_finding(
    session: AsyncSession, *, title: str, score: int, url: str = "", source: str = "hackernews"
) -> uuid.UUID:
    rec = ResearchFindingRecord(
        id=uuid.uuid4(),
        source=source,
        title=title,
        url=url,
        summary="- A concise bullet point.\n- Another detail.",
        tags=["ai"],
        importance_score=score,
    )
    session.add(rec)
    await session.flush()
    return rec.id


async def test_high_importance_finding_is_queued_to_priority_feed(
    db_session: AsyncSession, test_settings: NexusSettings
) -> None:
    hi = await _add_finding(db_session, title="OpenAI custom chip", score=5, url="https://x.test/a")
    lo = await _add_finding(db_session, title="Minor blog post", score=2, url="https://x.test/b")

    feed = PriorityFeedService(db_session, test_settings)
    corr = await feed.dispatch_new_findings([hi, lo])

    assert corr is not None
    rows = (
        (await db_session.execute(select(SystemOutboxRecord).where(SystemOutboxRecord.correlation_id == corr)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.channel == "discord"
    assert row.source_type == "priority_feed"
    # Routed via the channel harness to the priority feed channel key.
    assert row.payload["channel_key"] == "priority_feed"
    # The high-importance item is present; the low one is filtered out.
    assert "OpenAI custom chip" in row.payload["content"]
    assert "Minor blog post" not in row.payload["content"]
    # Owner is mentioned (PRIORITY_FEED policy.mention_owner is True).
    assert "<@111222333>" in row.payload["content"]


async def test_no_dispatch_when_nothing_clears_threshold(
    db_session: AsyncSession, test_settings: NexusSettings
) -> None:
    lo1 = await _add_finding(db_session, title="low one", score=1)
    lo2 = await _add_finding(db_session, title="low two", score=3)

    feed = PriorityFeedService(db_session, test_settings)
    corr = await feed.dispatch_new_findings([lo1, lo2])

    assert corr is None
    rows = (await db_session.execute(select(SystemOutboxRecord))).scalars().all()
    assert rows == []


async def test_disabled_feed_does_not_dispatch(
    db_session: AsyncSession, test_settings: NexusSettings
) -> None:
    test_settings.scheduling.priority_feed_enabled = False
    hi = await _add_finding(db_session, title="huge news", score=5)

    feed = PriorityFeedService(db_session, test_settings)
    assert await feed.dispatch_new_findings([hi]) is None


async def test_digest_caps_items_and_summarizes_remainder(
    db_session: AsyncSession, test_settings: NexusSettings
) -> None:
    test_settings.scheduling.priority_feed_max_items = 2
    ids = [
        await _add_finding(db_session, title=f"finding {i}", score=5, url=f"https://x.test/{i}")
        for i in range(5)
    ]

    feed = PriorityFeedService(db_session, test_settings)
    corr = await feed.dispatch_new_findings(ids)
    assert corr is not None

    row = (
        (await db_session.execute(select(SystemOutboxRecord).where(SystemOutboxRecord.correlation_id == corr)))
        .scalars()
        .one()
    )
    content = row.payload["content"]
    assert content.count("🔥 5/5") == 2  # only max_items rendered in full
    assert "and 3 more" in content


async def test_outbox_delivers_priority_feed_to_correct_channel(
    db_session: AsyncSession, test_settings: NexusSettings
) -> None:
    """The generalized outbox routes the queued digest to #priority-feed, not #summaries."""
    hi = await _add_finding(db_session, title="ground-breaking", score=5, url="https://x.test/z")
    feed = PriorityFeedService(db_session, test_settings)
    corr = await feed.dispatch_new_findings([hi])
    assert corr is not None

    discord = FakeDiscord()
    await flush_outbox_synchronously(db_session, corr, discord, email_service=None)

    assert discord.posts, "expected a delivery"
    channel_key, content = discord.posts[0]
    assert channel_key == "priority_feed"
    assert "ground-breaking" in content


async def test_legacy_discord_payload_defaults_to_summaries(db_session: AsyncSession) -> None:
    """A payload without channel_key still targets 'summaries' (backward compatibility)."""
    discord = FakeDiscord()
    await _deliver_discord_chunks(discord, "legacy briefing body")
    assert discord.posts == [("summaries", "legacy briefing body")]
