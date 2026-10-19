"""E2E tests for deterministic email-intent handling in the chat Planner.

The free-tier LLM is unreliable at choosing the ``send_email`` action and has been observed to
reply "I'm not capable of sending emails" instead. The Planner therefore deterministically forces
``SEND_EMAIL`` whenever the operator's text clearly asks to mail/email something — preserving any
useful prose the model produced as the body — while leaving owner governance to the Validator.
"""

from __future__ import annotations

import pytest

from nexus.communication.chat import ChatActionType
from nexus.communication.chat.planner import Planner, looks_like_email_request


class FakeLLM:
    """Returns one scripted response (or raises) for the single complete() call."""

    def __init__(self, response: str = "", *, raises: Exception | None = None) -> None:
        self._response = response
        self._raises = raises

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        if self._raises is not None:
            raise self._raises
        return self._response


@pytest.mark.parametrize(
    "text",
    [
        "drop me a mail for Claude Login URL",
        "mail me the report",
        "email me about the outage",
        "can you email this to me",
        "send me an email with the summary",
        "shoot me a mail",
        "forward me an email please",
    ],
)
def test_email_intent_detected(text: str) -> None:
    assert looks_like_email_request(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "what's my email address?",
        "check my mailbox status",
        "tell me a joke",
        "create a task to ship the feed",
        "",
    ],
)
def test_non_email_intent_not_detected(text: str) -> None:
    assert looks_like_email_request(text) is False


async def test_reply_is_coerced_to_send_email_on_clear_request() -> None:
    # The model wrongly answers conversationally; the Planner must still send.
    planner = Planner(
        FakeLLM('{"type": "reply", "message": "Here is the Claude login URL: https://claude.ai"}')
    )
    action = await planner.plan("drop me a mail for Claude Login URL")
    assert action.type is ChatActionType.SEND_EMAIL
    assert action.requires_owner is True  # governance preserved
    assert "claude" in action.payload["body"].lower()  # model prose carried into the body
    assert action.payload["subject"] == "Claude Login URL"  # derived from "for <subject>"


async def test_plain_text_refusal_is_coerced_to_send_email() -> None:
    # Non-JSON conversational refusal — exactly the observed failure — is overridden.
    planner = Planner(FakeLLM("I'm not capable of sending emails directly."))
    action = await planner.plan("email me the weekly digest")
    assert action.type is ChatActionType.SEND_EMAIL
    assert action.payload["body"]  # body is non-empty
    assert action.payload["subject"] == "weekly digest"


async def test_no_llm_still_honours_email_request() -> None:
    planner = Planner(None)
    action = await planner.plan("mail me the build status")
    assert action.type is ChatActionType.SEND_EMAIL
    assert action.payload["subject"] == "build status"


async def test_llm_error_still_honours_email_request() -> None:
    planner = Planner(FakeLLM(raises=RuntimeError("gateway down")))
    action = await planner.plan("please email me the logs")
    assert action.type is ChatActionType.SEND_EMAIL


async def test_explicit_send_email_json_is_respected() -> None:
    planner = Planner(FakeLLM('{"type": "send_email", "subject": "Status", "body": "All green."}'))
    action = await planner.plan("mail me the status")
    assert action.type is ChatActionType.SEND_EMAIL
    assert action.payload["subject"] == "Status"
    assert action.payload["body"] == "All green."


async def test_non_email_reply_stays_reply() -> None:
    planner = Planner(FakeLLM('{"type": "reply", "message": "Hello!"}'))
    action = await planner.plan("hi there")
    assert action.type is ChatActionType.REPLY
    assert action.requires_owner is False


async def test_non_email_create_task_not_overridden() -> None:
    planner = Planner(FakeLLM('{"type": "create_task", "title": "Ship feed"}'))
    action = await planner.plan("create a task to ship the feed")
    assert action.type is ChatActionType.CREATE_TASK
