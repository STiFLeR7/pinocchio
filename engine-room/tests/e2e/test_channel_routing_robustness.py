"""E2E tests for decoration-tolerant channel routing.

Discord channels are frequently named with emoji/separators ("💬│general") or suffixes
("general-chat"). The router normalizes names and falls back to whole-token containment so the
operator's chat channel resolves to the CHAT role (reply-without-mention) without false-matching
unrelated channels.
"""

from __future__ import annotations

import pytest

from nexus.communication.channels import ChannelRole, ChannelRouter
from nexus.config import DiscordChannels


def _router() -> ChannelRouter:
    return ChannelRouter(
        DiscordChannels(
            general="general",
            console="console",
            priority_feed="priority-feed",
            reminders="reminders",
            summaries="nexus-reports",
            approvals="nexus-approvals",
            research="nexus-research",
        )
    )


@pytest.mark.parametrize(
    "name",
    ["general", "💬│general", "general-chat", "GENERAL", "💬-general-💬", "general chat"],
)
def test_decorated_general_resolves_to_chat(name: str) -> None:
    router = _router()
    assert router.role_for_channel_name(name) is ChannelRole.CHAT
    assert router.respond_without_mention(name) is True


@pytest.mark.parametrize("name", ["console", "📋│console", "console-logs"])
def test_decorated_console_resolves_to_system(name: str) -> None:
    router = _router()
    assert router.role_for_channel_name(name) is ChannelRole.SYSTEM
    # SYSTEM is post-only — Dex must NOT free-chat in the console channel.
    assert router.respond_without_mention(name) is False


@pytest.mark.parametrize("name", ["nexus-research", "random-channel", "announcements", None, ""])
def test_unrelated_channels_do_not_match_chat(name: str | None) -> None:
    router = _router()
    assert router.role_for_channel_name(name) is not ChannelRole.CHAT
    assert router.respond_without_mention(name) is False


def test_exact_match_still_works() -> None:
    router = _router()
    assert router.role_for_channel_name("priority-feed") is ChannelRole.PRIORITY_FEED
    assert router.role_for_channel_name("reminders") is ChannelRole.NOTIFICATION
