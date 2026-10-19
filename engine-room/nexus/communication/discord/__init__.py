"""Discord communication provider and bot interface."""

from __future__ import annotations

from nexus.communication.discord.bot import NexusBot
from nexus.communication.discord.service import DiscordService, get_bot, set_bot

__all__ = ["DiscordService", "NexusBot", "get_bot", "set_bot"]
