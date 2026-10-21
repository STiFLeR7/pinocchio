"""E2E tests for the transport-independent channel harness (roles, routing, policy)."""

from __future__ import annotations

from nexus.communication.channels import (
    ChannelMessage,
    ChannelRole,
    ChannelRouter,
)
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
        )
    )


def test_chat_channel_responds_without_mention() -> None:
    router = _router()
    assert router.respond_without_mention("general") is True
    assert router.respond_without_mention("random-channel") is False
    assert router.respond_without_mention(None) is False


def test_inbound_name_maps_to_semantic_role() -> None:
    router = _router()
    assert router.role_for_channel_name("general") is ChannelRole.CHAT
    assert router.role_for_channel_name("priority-feed") is ChannelRole.PRIORITY_FEED
    assert router.role_for_channel_name("console") is ChannelRole.SYSTEM
    assert router.role_for_channel_name("unmapped") is None


def test_outbound_role_resolves_to_bound_channel() -> None:
    router = _router()
    assert router.channel_name(ChannelRole.SYSTEM) == "console"
    assert router.channel_name(ChannelRole.PRIORITY_FEED) == "priority-feed"
    assert router.channel_name(ChannelRole.BRIEFING) == "nexus-reports"
    assert router.channel_key(ChannelRole.CHAT) == "general"


def test_priority_and_notification_mention_owner_but_chat_does_not() -> None:
    router = _router()
    assert router.policy(ChannelRole.PRIORITY_FEED).mention_owner is True
    assert router.policy(ChannelRole.NOTIFICATION).mention_owner is True
    assert router.policy(ChannelRole.CHAT).mention_owner is False
    assert router.policy(ChannelRole.CHAT).respond_without_mention is True
    assert router.policy(ChannelRole.SYSTEM).post_only is True


def test_channel_message_is_transport_neutral() -> None:
    msg = ChannelMessage(
        author="42",
        channel_id="100",
        conversation_id="100",
        message="hello",
    )
    assert msg.role is ChannelRole.CHAT  # default
    assert msg.metadata == {}
    # Round-trips as plain data (no platform types).
    assert msg.model_dump()["message"] == "hello"
