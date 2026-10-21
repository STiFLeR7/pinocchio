"""Discord bot interface for the Nexus Control Plane.

Implements commands to create, list, and check task status, alongside
interactive message views for approvals.
"""

from __future__ import annotations

import contextlib
import uuid
from typing import Any

import discord
import structlog
from discord import app_commands
from discord.ext import commands
from sqlalchemy.ext.asyncio import async_sessionmaker

from nexus.approvals.service import ApprovalService
from nexus.communication.channels import ChannelMessage, ChannelRole, ChannelRouter
from nexus.communication.chat import ChatResponse, OutboundPost
from nexus.config import get_settings
from nexus.core.types import ApprovalStatus, TaskStatus
from nexus.database import get_session
from nexus.memory.models import TaskRecord
from nexus.memory.service import MemoryService
from nexus.memory.task_service import TaskService

logger = structlog.get_logger("nexus.communication.discord.bot")


def _build_card_embed(card: dict[str, Any]) -> discord.Embed:
    """Render a transport-neutral status-card payload into a Discord embed."""
    verification = str(card.get("verification", ""))
    color = (
        discord.Color.green()
        if verification == "sent"
        else discord.Color.red()
        if verification == "failed"
        else discord.Color.blurple()
    )
    embed = discord.Embed(title=str(card.get("title", "Dex • Action")), color=color)
    embed.add_field(name="Risk Level", value=str(card.get("risk", "LOW")), inline=True)
    if verification:
        embed.add_field(name="Verification", value=verification, inline=True)
    embed.add_field(name="Execution Plan", value=str(card.get("plan", "None"))[:1000], inline=False)
    embed.add_field(name="Tools Used", value=str(card.get("tools", "None")), inline=True)
    return embed


class ApprovalView(discord.ui.View):
    """Interactive view for manual approval gates containing Approve/Reject buttons."""

    def __init__(
        self,
        approval_id: str,
        owner_ids: list[int],
        session_factory: Any,
        event_gateway: Any = None,
    ) -> None:
        """Initialize the view with custom id mappings and security keys."""
        super().__init__(timeout=None)
        self.approval_id = approval_id
        self.owner_ids = owner_ids
        self.session_factory = session_factory
        self.event_gateway = event_gateway

    async def handle_decision(
        self,
        interaction: discord.Interaction,
        decision: ApprovalStatus,
    ) -> None:
        """Verify owner credentials and transition approval record state."""
        # 1. Credentials Check
        if self.owner_ids and interaction.user.id not in self.owner_ids:
            await interaction.response.send_message(
                "Unauthorized: Only designated owners can authorize task execution.",
                ephemeral=True,
            )
            return

        # Disable buttons
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        await interaction.response.defer()

        if interaction.message is None:
            return

        try:
            # 2. Database update
            async with get_session(self.session_factory) as session:
                memory_service = MemoryService(session)
                approval_service = ApprovalService(
                    session, memory_service, self.owner_ids, self.event_gateway
                )
                await approval_service.evaluate_approval(
                    approval_id=uuid.UUID(self.approval_id),
                    decision=decision,
                    decided_by=str(interaction.user.id),
                    reason=f"Approved via Discord click by {interaction.user.name}",
                )

            # Update embed to completed state
            embed = interaction.message.embeds[0]
            if decision == ApprovalStatus.APPROVED:
                embed.color = discord.Color.green()
                embed.title = "Approval Gate — APPROVED"
            else:
                embed.color = discord.Color.red()
                embed.title = "Approval Gate — REJECTED"

            embed.add_field(
                name="Decision Log",
                value=f"{decision.value.capitalize()} by {interaction.user.mention}",
                inline=False,
            )
            await interaction.message.edit(embed=embed, view=None)

        except Exception as e:
            logger.error("discord_approval_button_failed", error=str(e))
            await interaction.followup.send(f"Error executing decision: {e!s}", ephemeral=True)

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        custom_id="approve_btn",
    )
    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[Any],
    ) -> None:
        """Handle execution approval action."""
        await self.handle_decision(interaction, ApprovalStatus.APPROVED)

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.danger,
        custom_id="reject_btn",
    )
    async def reject(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button[Any],
    ) -> None:
        """Handle execution rejection action."""
        await self.handle_decision(interaction, ApprovalStatus.REJECTED)


class NexusBot(commands.Bot):
    """The Nexus Control Plane Discord Bot adapter client."""

    def __init__(
        self,
        settings: Any = None,
        session_factory: async_sessionmaker[Any] | None = None,
        event_gateway: Any = None,
        llm_client: Any = None,
        chat_service: Any = None,
    ) -> None:
        """Set intents and command configurations."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        super().__init__(command_prefix="/", intents=intents)
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        self.event_gateway = event_gateway
        self.llm_client = llm_client
        # Chat orchestration (core logic) + channel harness (routing). The adapter stays thin.
        self.chat_service = chat_service
        self.router = ChannelRouter(self.settings.discord.channels)
        self.guild_obj: discord.Guild | None = None

    async def setup_hook(self) -> None:
        """Register application command tree on startup."""
        self.tree.add_command(task_create)
        self.tree.add_command(task_list)
        self.tree.add_command(task_status)

        # Sync slash commands to target guild for fast local dev testing
        guild_id = self.settings.discord.guild_id
        if guild_id:
            guild_obj = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)
            logger.info("discord_slash_commands_synced", guild_id=guild_id)
        else:
            await self.tree.sync()
            logger.info("discord_slash_commands_synced_globally")

    async def on_ready(self) -> None:
        """Resolve guild object on startup connection."""
        bot_user_id = self.user.id if self.user else None
        logger.info("discord_bot_connected", user=self.user, bot_id=bot_user_id)
        guild_id = self.settings.discord.guild_id
        if guild_id:
            self.guild_obj = self.get_guild(guild_id)
            if self.guild_obj:
                logger.info(
                    "discord_bot_guild_resolved",
                    guild_name=self.guild_obj.name,
                    guild_id=self.guild_obj.id,
                )
            else:
                logger.warning("discord_bot_guild_not_found", guild_id=guild_id)
        else:
            logger.warning("discord_bot_no_guild_id_configured")

    async def on_message(self, message: discord.Message) -> None:
        """Thin adapter: normalize → ChatService.handle() → render. No business logic here.

        Responds to a DM, an explicit @mention, or any message in a channel whose role allows
        replies without a mention (the CHAT role). Slash commands are handled by the application
        command tree, so we never call ``process_commands``.
        """
        if message.author.bot or (self.user is not None and message.author.id == self.user.id):
            return

        is_dm = message.guild is None
        is_mention = self.user is not None and self.user in message.mentions
        channel_name = getattr(message.channel, "name", None)
        in_chat_channel = self.router.respond_without_mention(channel_name)
        if not (is_dm or is_mention or in_chat_channel):
            return
        if self.chat_service is None:
            return

        text = self._normalize_text(message)
        if not text:
            await message.channel.send(
                "Hi — I'm **Nexus** (Dex). Chat with me in the chat channel (no @ needed), ask me "
                "to `mail me ...`, or use `/task_create`, `/task_list`, `/task_status`."
            )
            return

        channel_msg = ChannelMessage(
            role=ChannelRole.CHAT,
            author=str(message.author.id),
            channel_id=str(message.channel.id),
            conversation_id=str(message.channel.id),
            message=text,
            metadata={"is_owner": self._is_owner(message.author.id), "is_dm": is_dm},
        )
        async with message.channel.typing():
            response = await self.chat_service.handle(channel_msg)
        await self._render(message, response)

    def _normalize_text(self, message: discord.Message) -> str:
        """Strip the bot's mention tokens so only the operator's text remains."""
        content = message.content or ""
        if self.user is not None:
            for token in (f"<@{self.user.id}>", f"<@!{self.user.id}>"):
                content = content.replace(token, "")
        return content.strip()

    def _is_owner(self, user_id: int) -> bool:
        return user_id in (self.settings.discord.owner_ids or [])

    async def _render(self, message: discord.Message, response: ChatResponse) -> None:
        """Render a transport-neutral ChatResponse onto Discord (the only place with Discord I/O)."""
        if response.reply:
            for start in range(0, len(response.reply), 1900):
                await message.channel.send(response.reply[start : start + 1900])
        for post in response.posts:
            await self._render_post(post)

    async def _render_post(self, post: OutboundPost) -> None:
        """Route an outbound post to the channel bound to its semantic role (best-effort)."""
        key = self.router.channel_key(post.role)
        channel = self.get_channel_by_config(key) if key else None
        if channel is None:
            return
        with contextlib.suppress(Exception):
            if post.card is not None:
                await channel.send(embed=_build_card_embed(post.card))
            elif post.content:
                await channel.send(post.content)

    def get_channel_by_config(self, channel_key: str) -> discord.TextChannel | None:
        """Resolve a text channel by configured channel ID or name."""
        if not self.guild_obj:
            return None

        # Standard settings mapping
        channels_map = self.settings.discord.channels
        val = getattr(channels_map, channel_key, None)

        if not val:
            # Check direct fallback names
            val = channel_key

        # 1. Try resolving as channel ID integer
        try:
            channel_id = int(val)
            ch = self.guild_obj.get_channel(channel_id)
            if ch and isinstance(ch, discord.TextChannel):
                return ch
        except (ValueError, TypeError):
            pass

        # 2. Try resolving by channel name search
        for ch in self.guild_obj.text_channels:
            if ch.name == val:
                return ch

        # 3. Fallback to first text channel if nothing else matches
        if self.guild_obj.text_channels:
            return self.guild_obj.text_channels[0]

        return None


# ---------------------------------------------------------------------------
# Command Tree Definitions
# ---------------------------------------------------------------------------


@app_commands.command(name="task_create", description="Create a new task in Nexus")
async def task_create(
    interaction: discord.Interaction,
    title: str,
    description: str | None = None,
    priority: int = 2,
) -> None:
    """Ingest a new task command from Discord."""
    bot: NexusBot = interaction.client  # type: ignore[assignment]
    await interaction.response.defer()

    try:
        async with get_session(bot.session_factory) as session:
            memory_service = MemoryService(session)
            task_service = TaskService(session, memory_service, bot.event_gateway)

            # Ingest task
            task = await task_service.create_task(
                title=title,
                description=description,
                priority=priority,
            )

            # Automatically transition task to QUEUED status
            await task_service.change_status(task.id, TaskStatus.QUEUED)

        await interaction.followup.send(
            f"✅ **Task Ingested & Enqueued**\n"
            f"**ID**: `{task.id}`\n"
            f"**Title**: {task.title}\n"
            f"**Priority**: {task.priority}\n"
            f"**Status**: `{task.status}`"
        )
    except Exception as e:
        logger.error("discord_command_task_create_failed", error=str(e))
        await interaction.followup.send(f"❌ Failed to create task: {e!s}", ephemeral=True)


@app_commands.command(name="task_list", description="List active tasks in Nexus")
async def task_list(interaction: discord.Interaction) -> None:
    """Query and return active tasks in database."""
    bot: NexusBot = interaction.client  # type: ignore[assignment]
    await interaction.response.defer()

    try:
        from sqlalchemy import select

        async with get_session(bot.session_factory) as session:
            stmt = (
                select(TaskRecord)
                .where(TaskRecord.is_archived.is_(False))
                .order_by(TaskRecord.created_at.desc())
            )
            res = await session.execute(stmt)
            tasks = res.scalars().all()

        if not tasks:
            await interaction.followup.send("No tasks found in Nexus database.")
            return

        lines = ["**Nexus Active Tasks:**"]
        for t in tasks[:10]:  # limit to latest 10
            lines.append(
                f"• `{t.id}` | **{t.title}** | Status: `{t.status}` | Priority: {t.priority}"
            )

        await interaction.followup.send("\n".join(lines))
    except Exception as e:
        logger.error("discord_command_task_list_failed", error=str(e))
        await interaction.followup.send(f"❌ Failed to list tasks: {e!s}", ephemeral=True)


@app_commands.command(name="task_status", description="Query specific task details by ID")
async def task_status(interaction: discord.Interaction, task_id: str) -> None:
    """Fetch status and trace log metadata of a single task."""
    bot: NexusBot = interaction.client  # type: ignore[assignment]
    await interaction.response.defer()

    try:
        uid = uuid.UUID(task_id)
        async with get_session(bot.session_factory) as session:
            memory_service = MemoryService(session)
            task_service = TaskService(session, memory_service, bot.event_gateway)
            task = await task_service.get_task(uid)

        if not task:
            await interaction.followup.send(f"Task with ID `{task_id}` not found.")
            return

        lines = [
            "**Task Details:**",
            f"• **ID**: `{task.id}`",
            f"• **Title**: {task.title}",
            f"• **Description**: {task.description}",
            f"• **Status**: `{task.status}`",
            f"• **Priority**: {task.priority}",
            f"• **Created At**: {task.created_at.isoformat()}",
        ]
        await interaction.followup.send("\n".join(lines))
    except ValueError:
        await interaction.followup.send("❌ Invalid UUID format.", ephemeral=True)
    except Exception as e:
        logger.error("discord_command_task_status_failed", error=str(e))
        await interaction.followup.send(f"❌ Failed to get status: {e!s}", ephemeral=True)
