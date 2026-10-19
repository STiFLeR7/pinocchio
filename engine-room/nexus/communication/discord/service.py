"""Service layer adapter for Discord communication.

Acts as the interface between the Nexus system state transitions and active
Discord channels.
"""

from __future__ import annotations

import uuid
from typing import Any

import discord
import structlog

from nexus.communication.discord.bot import ApprovalView, NexusBot

logger = structlog.get_logger("nexus.communication.discord.service")

# Global reference to running bot
_bot_instance: NexusBot | None = None


def set_bot(bot: NexusBot) -> None:
    """Set the active global bot instance."""
    global _bot_instance
    _bot_instance = bot


def get_bot() -> NexusBot | None:
    """Get the active global bot instance."""
    return _bot_instance


class DiscordService:
    """Provides high-level methods to post notifications, logs, and approval gates to Discord."""

    def __init__(self, bot: NexusBot | None = None) -> None:
        """Initialize with bot client reference or resolve from global context."""
        self._bot = bot

    @property
    def bot(self) -> NexusBot:
        """Resolve active bot instance, raising error if not connected."""
        active_bot = self._bot or get_bot()
        if active_bot is None:
            raise RuntimeError("Discord bot is not running or initialized.")
        return active_bot

    async def post_message(
        self,
        channel_key: str,
        content: str | None = None,
        embed: discord.Embed | None = None,
        view: discord.ui.View | None = None,
    ) -> discord.Message | None:
        """Post a message or embed to a mapped channel key."""
        bot = self.bot
        channel = bot.get_channel_by_config(channel_key)

        if not channel:
            logger.warning("discord_channel_not_resolved", channel_key=channel_key)
            return None

        kwargs: dict[str, Any] = {}
        if content is not None:
            kwargs["content"] = content
        if embed is not None:
            kwargs["embed"] = embed
        if view is not None:
            kwargs["view"] = view

        try:
            msg = await channel.send(**kwargs)
            logger.debug(
                "discord_message_posted",
                channel=channel.name,
                message_id=msg.id,
            )
            return msg
        except Exception as e:
            logger.error("discord_post_message_failed", channel=channel_key, error=str(e))
            return None

    async def send_approval_request(
        self,
        task_id: uuid.UUID,
        approval_id: uuid.UUID,
        task_title: str,
        task_description: str | None,
        task_priority: int,
    ) -> discord.Message | None:
        """Post an interactive approval request card to the `#approvals` channel."""
        embed = discord.Embed(
            title="Approval Request — PENDING",
            description="A task is blocked waiting for authorization.",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Task ID", value=f"`{task_id}`", inline=False)
        embed.add_field(name="Approval ID", value=f"`{approval_id}`", inline=False)
        embed.add_field(name="Title", value=task_title, inline=False)
        if task_description:
            embed.add_field(name="Description", value=task_description, inline=False)
        embed.add_field(name="Priority", value=str(task_priority), inline=True)

        bot = self.bot
        view = ApprovalView(
            approval_id=str(approval_id),
            owner_ids=bot.settings.discord.owner_ids,
            session_factory=bot.session_factory,
            event_gateway=bot.event_gateway,
        )

        return await self.post_message("approvals", embed=embed, view=view)
