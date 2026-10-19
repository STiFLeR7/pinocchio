"""Proactive Priority Feed dispatcher.

After a research run, the highest-signal *new* findings are pushed to the operator between the
scheduled 08:00 briefings — an "influencer-style" drop that mentions the owner.

This service is **transport-independent**: it resolves the destination through the channel harness
(:class:`~nexus.communication.channels.ChannelRouter` → :class:`ChannelRole.PRIORITY_FEED`) and
enqueues a row on the transactional communication outbox. It never imports Discord and never sends
anything itself — the outbox worker drains it, exactly like briefings. Research stays oblivious to
where its findings end up.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from nexus.communication.channels import ChannelRole, ChannelRouter
from nexus.memory.models import ResearchFindingRecord, SystemOutboxRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from nexus.config import NexusSettings

logger = structlog.get_logger("nexus.intelligence.feed")


class PriorityFeedService:
    """Selects high-importance findings and queues an owner-tagged digest to the priority feed."""

    def __init__(self, db_session: AsyncSession, settings: NexusSettings) -> None:
        self.session = db_session
        self.settings = settings
        self.router = ChannelRouter(settings.discord.channels)

    async def dispatch_new_findings(self, finding_ids: list[uuid.UUID]) -> uuid.UUID | None:
        """Queue a priority-feed digest for the high-importance subset of ``finding_ids``.

        Returns the outbox correlation id if a digest was enqueued, else ``None`` (nothing cleared
        the importance threshold, or the feed is disabled).
        """
        sc = self.settings.scheduling
        if not sc.priority_feed_enabled or not finding_ids:
            return None

        findings = await self._load_priority_findings(finding_ids, sc.priority_feed_min_score)
        if not findings:
            logger.info("priority_feed_no_high_importance_findings", candidates=len(finding_ids))
            return None

        content = self._render_digest(findings, sc.priority_feed_max_items)
        channel_key = self.router.channel_key(ChannelRole.PRIORITY_FEED)
        correlation_id = uuid.uuid4()

        self.session.add(
            SystemOutboxRecord(
                id=uuid.uuid4(),
                channel="discord",
                payload={"content": content, "channel_key": channel_key},
                status="pending",
                correlation_id=correlation_id,
                source_type="priority_feed",
                source_id=None,
            )
        )
        await self.session.flush()

        logger.info(
            "priority_feed_digest_enqueued",
            correlation_id=str(correlation_id),
            items=len(findings),
            channel_key=channel_key,
        )
        return correlation_id

    async def _load_priority_findings(
        self, finding_ids: list[uuid.UUID], min_score: int
    ) -> list[ResearchFindingRecord]:
        """Load the findings that exist and meet the importance threshold, highest score first."""
        stmt = (
            select(ResearchFindingRecord)
            .where(ResearchFindingRecord.id.in_(finding_ids))
            .where(ResearchFindingRecord.importance_score >= min_score)
            .order_by(ResearchFindingRecord.importance_score.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    def _render_digest(self, findings: list[ResearchFindingRecord], max_items: int) -> str:
        """Render an influencer-style digest, mentioning the owner if the role policy requires it."""
        policy = self.router.policy(ChannelRole.PRIORITY_FEED)
        shown = findings[:max_items]
        remainder = len(findings) - len(shown)

        lines: list[str] = []
        header = f"🚨 **Priority Feed** — {len(findings)} high-signal drop{'s' if len(findings) != 1 else ''}"
        if policy.mention_owner:
            mention = self._owner_mention()
            if mention:
                header = f"{header} {mention}"
        lines.append(header)
        lines.append("")

        for idx, f in enumerate(shown, start=1):
            score = f.importance_score or 0
            source = f.source or "unknown"
            lines.append(f"**{idx}. {f.title}** · 🔥 {score}/5 · `{source}`")
            if f.summary:
                lines.append(self._first_line(f.summary))
            if f.url:
                lines.append(f"🔗 {f.url}")
            lines.append("")

        if remainder > 0:
            lines.append(f"_…and {remainder} more in the next briefing._")

        return "\n".join(lines).strip()

    def _owner_mention(self) -> str:
        """Build a Discord mention string for the configured owner(s)."""
        owner_ids = self.settings.discord.owner_ids
        return " ".join(f"<@{oid}>" for oid in owner_ids)

    @staticmethod
    def _first_line(summary: str) -> str:
        """Collapse a (possibly multi-line/bulleted) summary to a single punchy line."""
        for raw in summary.splitlines():
            line = raw.strip().lstrip("-*• ").strip()
            if line:
                return line if len(line) <= 240 else line[:237] + "…"
        return ""
