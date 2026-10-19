"""E2E tests for the chat pipeline: Conversation → Planner → Validator → Executor.

Uses an in-memory fake LLM and fake email service so the whole pipeline is exercised end-to-end,
deterministically, without network or Discord.
"""

from __future__ import annotations

from typing import Any

from nexus.communication.channels import ChannelRole
from nexus.communication.chat import (
    ChatActionType,
    ChatService,
    Executor,
    Planner,
    Validator,
)


class FakeLLM:
    """Deterministic LLM stub that records calls and returns scripted JSON plans."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        self.calls.append({"prompt": prompt, "history": list(history or [])})
        return self._responses.pop(0) if self._responses else '{"type": "reply", "message": "ok"}'


class FakeEmail:
    """Captures emails instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_briefing_email(self, subject: str, text: str, html: str) -> None:
        self.sent.append({"subject": subject, "text": text, "html": html})


def _service(responses: list[str], email: FakeEmail | None = None) -> ChatService:
    return ChatService.build(
        llm_client=FakeLLM(responses),
        email_service=email or FakeEmail(),
        owner_email="owner@example.com",
    )


async def test_reply_path_does_not_touch_services() -> None:
    email = FakeEmail()
    svc = _service(['{"type": "reply", "message": "Hello operator"}'], email)
    resp = await svc.handle_text(conversation_id="c1", text="hi", is_owner=True)
    assert resp.action_type is ChatActionType.REPLY
    assert resp.executed is True
    assert resp.reply == "Hello operator"
    assert email.sent == []


async def test_owner_can_send_email_end_to_end() -> None:
    email = FakeEmail()
    svc = _service(
        ['{"type": "send_email", "subject": "Claude Login", "body": "https://claude.ai/login"}'],
        email,
    )
    resp = await svc.handle_text(conversation_id="c1", text="mail me the claude login url", is_owner=True)

    assert resp.action_type is ChatActionType.SEND_EMAIL
    assert resp.executed is True
    assert len(email.sent) == 1
    assert email.sent[0]["subject"] == "Claude Login"
    assert "claude.ai/login" in email.sent[0]["text"]
    # A SYSTEM status card is emitted for the side-effecting action.
    assert any(p.role is ChannelRole.SYSTEM and p.card and p.card["verification"] == "sent" for p in resp.posts)


async def test_non_owner_email_is_denied_by_governance() -> None:
    email = FakeEmail()
    svc = _service(
        ['{"type": "send_email", "subject": "x", "body": "secret"}'],
        email,
    )
    resp = await svc.handle_text(conversation_id="c1", text="email me", is_owner=False)

    assert resp.executed is False
    assert email.sent == []  # never reached the executor
    assert "owner" in (resp.reply or "").lower()


async def test_missing_required_field_fails_schema_validation() -> None:
    email = FakeEmail()
    # send_email with no body — must fail schema before execution.
    svc = _service(['{"type": "send_email", "subject": "only subject"}'], email)
    resp = await svc.handle_text(conversation_id="c1", text="mail me", is_owner=True)

    assert resp.executed is False
    assert email.sent == []
    assert "missing" in (resp.reply or "").lower()


async def test_conversation_memory_is_passed_on_next_turn() -> None:
    llm = FakeLLM(
        [
            '{"type": "reply", "message": "Sure, I will remember Claude login is at claude.ai."}',
            '{"type": "reply", "message": "It is claude.ai/login."}',
        ]
    )
    svc = ChatService(planner=Planner(llm), validator=Validator(), executor=Executor())
    await svc.handle_text(conversation_id="c9", text="remember the claude login", is_owner=True)
    await svc.handle_text(conversation_id="c9", text="yah share", is_owner=True)

    # The 2nd planner call must have received the prior turns as history (the "yah share" fix).
    second_history = llm.calls[1]["history"]
    assert any(h["role"] == "user" and "remember" in h["content"] for h in second_history)
    assert any(h["role"] == "assistant" for h in second_history)


async def test_governance_flags_are_stamped_server_side_not_by_llm() -> None:
    # Even if the model omits governance flags, the planner stamps them from the trusted table.
    planner = Planner(FakeLLM(['{"type": "send_email", "subject": "s", "body": "b"}']))
    action = await planner.plan("mail me", history=[])
    assert action.requires_owner is True
    assert action.requires_approval is False

    planner2 = Planner(FakeLLM(['{"type": "reply", "message": "hi"}']))
    reply_action = await planner2.plan("hi", history=[])
    assert reply_action.requires_owner is False
