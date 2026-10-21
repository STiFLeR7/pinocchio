"""Channel Harness — transport-independent message model and declarative routing.

This module is the meta-level routing layer for the control plane. It defines:

* :class:`ChannelRole` — *semantic* roles (chat, notification, priority feed, …) that are
  independent of any platform (Discord/Slack/CLI/REST).
* :class:`ChannelMessage` — a transport-independent inbound message. Every adapter converts its
  native event into a ``ChannelMessage`` so the orchestration layer never knows the platform.
* :class:`ChannelRouter` — declarative mapping ``ChannelRole`` ⇄ a concrete channel, plus the
  behavioural policy of each role (reply-without-mention, post-only, mention-owner).

It contains **no platform API calls and no business logic** — pure, deterministic mapping that is
unit/E2E testable in isolation and reused by adapters, schedulers, and the proactive feed alike.

Example (research never mentions Discord)::

    research → importance=HIGH → ChannelRouter(role=PRIORITY_FEED) → adapter → Discord
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from nexus.config import DiscordChannels


def _normalize_channel_name(name: str | None) -> str:
    """Lower-case and strip decoration (emoji, separators) to bare alphanumeric tokens.

    Discord channel names are frequently decorated ("💬│general", "general-chat"), which would
    otherwise defeat an exact-name match. Normalizing both the configured and the live name to
    space-separated lowercase tokens makes routing tolerant of that cosmetic naming.
    """
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


class ChannelRole(enum.StrEnum):
    """Semantic, transport-independent role of a channel."""

    CHAT = "chat"  # free-form operator conversation
    NOTIFICATION = "notification"  # reminders / TODOs / nudges (mention owner)
    PRIORITY_FEED = "priority_feed"  # high-importance briefs (mention owner)
    BRIEFING = "briefing"  # scheduled digests / summaries
    APPROVAL = "approval"  # approval cards
    SYSTEM = "system"  # Dex status / action cards / system logs


class ChannelMessage(BaseModel):
    """Transport-independent inbound message. Adapters normalize native events into this."""

    role: ChannelRole = ChannelRole.CHAT
    author: str  # platform-agnostic author id (e.g. discord user id as str)
    channel_id: str
    conversation_id: str  # stable key for conversation memory
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)  # e.g. {"is_owner": bool, "is_dm": bool}


@dataclass(frozen=True)
class ChannelPolicy:
    """Behavioural policy for a channel role."""

    role: ChannelRole
    respond_without_mention: bool = False  # reply to plain (un-mentioned) messages here
    post_only: bool = False  # Dex posts here but does not converse
    mention_owner: bool = False  # prepend an owner mention to posts


_POLICIES: dict[ChannelRole, ChannelPolicy] = {
    ChannelRole.CHAT: ChannelPolicy(ChannelRole.CHAT, respond_without_mention=True),
    ChannelRole.NOTIFICATION: ChannelPolicy(
        ChannelRole.NOTIFICATION, post_only=True, mention_owner=True
    ),
    ChannelRole.PRIORITY_FEED: ChannelPolicy(
        ChannelRole.PRIORITY_FEED, post_only=True, mention_owner=True
    ),
    ChannelRole.BRIEFING: ChannelPolicy(ChannelRole.BRIEFING, post_only=True),
    ChannelRole.APPROVAL: ChannelPolicy(ChannelRole.APPROVAL, post_only=True),
    ChannelRole.SYSTEM: ChannelPolicy(ChannelRole.SYSTEM, post_only=True),
}

# Declarative binding: semantic role -> DiscordChannels attribute that resolves the concrete name.
# A future Slack/REST adapter would supply its own binding; the roles stay identical.
_DEFAULT_DISCORD_BINDING: dict[ChannelRole, str] = {
    ChannelRole.CHAT: "general",
    ChannelRole.NOTIFICATION: "reminders",
    ChannelRole.PRIORITY_FEED: "priority_feed",
    ChannelRole.BRIEFING: "summaries",
    ChannelRole.APPROVAL: "approvals",
    ChannelRole.SYSTEM: "console",
}


class ChannelRouter:
    """Resolves semantic roles ⇄ concrete channels and exposes per-role policy."""

    def __init__(
        self,
        channels: DiscordChannels,
        binding: dict[ChannelRole, str] | None = None,
    ) -> None:
        self._channels = channels
        self._binding = binding or _DEFAULT_DISCORD_BINDING
        # Reverse map normalized concrete-name -> role for inbound routing. Keys are normalized
        # (decoration-stripped, lower-cased) so a live "💬│general" still resolves to CHAT.
        self._name_to_role: dict[str, ChannelRole] = {}
        # Token-set fallback: every configured name's token set, for whole-token containment.
        self._tokens_to_role: list[tuple[frozenset[str], ChannelRole]] = []
        for role, key in self._binding.items():
            name = getattr(channels, key, None)
            normalized = _normalize_channel_name(name) if name else ""
            if normalized:
                self._name_to_role[normalized] = role
                self._tokens_to_role.append((frozenset(normalized.split()), role))

    def policy(self, role: ChannelRole) -> ChannelPolicy:
        """Return the behavioural policy for a role."""
        return _POLICIES[role]

    def channel_key(self, role: ChannelRole) -> str | None:
        """Return the DiscordChannels attribute name bound to this role."""
        return self._binding.get(role)

    def channel_name(self, role: ChannelRole) -> str | None:
        """Return the concrete channel name bound to a role."""
        key = self._binding.get(role)
        return getattr(self._channels, key, None) if key else None

    def role_for_channel_name(self, name: str | None) -> ChannelRole | None:
        """Map an inbound concrete channel name to its semantic role (None if unmapped).

        Tries an exact normalized match first, then a whole-token containment fallback so a
        decorated/suffixed channel (e.g. "💬│general", "general-chat") still resolves to the
        configured role. Containment requires every configured token to be present, so
        "general" never matches "nexus-research" but does match "general chat".
        """
        normalized = _normalize_channel_name(name)
        if not normalized:
            return None
        exact = self._name_to_role.get(normalized)
        if exact is not None:
            return exact
        live_tokens = set(normalized.split())
        for config_tokens, role in self._tokens_to_role:
            if config_tokens <= live_tokens:
                return role
        return None

    def respond_without_mention(self, channel_name: str | None) -> bool:
        """True if Dex should reply to plain (un-mentioned) messages in this channel."""
        role = self.role_for_channel_name(channel_name)
        return role is not None and self.policy(role).respond_without_mention
