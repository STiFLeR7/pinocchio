"""Planner — turns a conversation turn into a typed :class:`ChatAction`.

Responsibility boundary: the planner decides *what* to do (action type + parameters) using the LLM,
then stamps governance requirements from a **trusted server-side policy table**. It never executes
anything and never trusts the model to set ``requires_owner`` / ``requires_approval``.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

from nexus.communication.chat.contracts import ChatAction, ChatActionType

logger = structlog.get_logger("nexus.communication.chat.planner")

# Deterministic email-intent detection. The free-tier LLM is unreliable at choosing the
# send_email action (it sometimes returns a conversational refusal instead), so when the
# operator's text clearly asks to mail/email something we force the SEND_EMAIL action
# regardless of the model — the model's prose, if any, becomes the email body. Owner
# governance is still enforced downstream by the Validator; this only fixes action SELECTION.
_EMAIL_INTENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:e-?mail|mail)\s+(?:me|it|this|that|them?)\b"),
    re.compile(r"\b(?:send|shoot|drop|fire|forward)\s+(?:me\s+)?(?:an?\s+)?(?:e-?mail|mail)\b"),
    re.compile(r"\bdrop\s+(?:me\s+)?a\s+(?:e-?mail|mail)\b"),
    re.compile(r"\b(?:can|could|please|pls|plz)\s+you\s+(?:e-?mail|mail)\b"),
)
# Phrases that introduce the subject of the requested email, tried in order:
#   1. an explicit topic marker — "… about/regarding/re/for/with <subject>"
#   2. the object of "… me <subject>"     — "mail me the build status" → "build status"
_SUBJECT_HINTS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:about|regarding|re|for|with)\s+(.+)$", re.IGNORECASE),
    re.compile(r"\b(?:e-?mail|mail|send|drop|shoot|forward)\b.*?\bme\b\s+(.+)$", re.IGNORECASE),
)
_LEADING_ARTICLE = re.compile(r"^(?:a|an|the)\s+", re.IGNORECASE)
# Degenerate subjects that carry no real topic (the verb/object collapsed to the channel itself).
_EMPTY_SUBJECTS = frozenset({"", "mail", "email", "e-mail", "a mail", "an email", "message"})


def looks_like_email_request(text: str) -> bool:
    """True when the operator's text is unambiguously a request to send an email."""
    lowered = (text or "").lower()
    return any(pattern.search(lowered) for pattern in _EMAIL_INTENT_PATTERNS)


def _derive_subject(text: str) -> str:
    """Best-effort subject from an email request (topic marker, else the object of '… me …')."""
    for pattern in _SUBJECT_HINTS:
        match = pattern.search(text or "")
        if not match:
            continue
        subject = _LEADING_ARTICLE.sub("", match.group(1).strip(" .!?\"'").strip()).strip()
        if subject.lower() not in _EMPTY_SUBJECTS:
            return subject[:120]
    return "Message from Nexus"


# Trusted governance policy per action type: (requires_owner, requires_approval).
# This is the ONLY place these flags are set — the LLM cannot influence them.
_ACTION_POLICY: dict[ChatActionType, tuple[bool, bool]] = {
    ChatActionType.REPLY: (False, False),
    ChatActionType.SEND_EMAIL: (True, False),  # owner-only, low-risk
    ChatActionType.CREATE_TASK: (True, False),
    ChatActionType.RUN_RESEARCH: (True, False),
    ChatActionType.SHOW_STATUS: (False, False),
    ChatActionType.APPROVAL_REQUEST: (True, True),
}

_SYSTEM_PROMPT = (
    "You are Nexus (call-sign 'Dex'), an AI Orchestration Control Plane assistant for your operator. "
    "Use the prior turns for context. Decide the single best action and reply with ONE JSON object "
    "and nothing else, using this schema:\n"
    '  {"type": "reply", "message": "<conversational answer>"}\n'
    '  {"type": "send_email", "subject": "<short>", "body": "<email body>"}\n'
    '  {"type": "create_task", "title": "<title>", "description": "<desc>", "priority": 2}\n'
    '  {"type": "run_research", "topic": "<topic>"}\n'
    '  {"type": "show_status"}\n'
    "You CAN send email to the operator via the send_email action — never claim you are unable "
    "to send email. Choose send_email whenever asked to email/mail/drop/send a message (it goes to "
    'the operator\'s configured address); put the useful content in "body". Choose create_task / '
    "run_research only when explicitly asked to. Otherwise use reply. Optionally include a numeric "
    '"confidence" between 0 and 1.'
)

# Map JSON "type" strings to enum, tolerant of synonyms.
_TYPE_ALIASES: dict[str, ChatActionType] = {
    "reply": ChatActionType.REPLY,
    "send_email": ChatActionType.SEND_EMAIL,
    "email": ChatActionType.SEND_EMAIL,
    "create_task": ChatActionType.CREATE_TASK,
    "task": ChatActionType.CREATE_TASK,
    "run_research": ChatActionType.RUN_RESEARCH,
    "research": ChatActionType.RUN_RESEARCH,
    "show_status": ChatActionType.SHOW_STATUS,
    "status": ChatActionType.SHOW_STATUS,
    "approval_request": ChatActionType.APPROVAL_REQUEST,
}


class Planner:
    """Plans a :class:`ChatAction` from a message + history using the LLM gateway."""

    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client

    async def plan(self, text: str, history: list[dict[str, str]] | None = None) -> ChatAction:
        """Produce a governance-stamped ChatAction; degrade to a plain REPLY on any failure."""
        email_intent = looks_like_email_request(text)
        if self.llm_client is None:
            if email_intent:
                # No LLM, but the request is unambiguous — still honour it deterministically.
                return self._email_action(text, body=text)
            return self._reply(
                "⚠️ Chat is unavailable: no LLM gateway is configured.", confidence=1.0
            )
        try:
            raw = await self.llm_client.complete(
                text, system_prompt=_SYSTEM_PROMPT, history=history or []
            )
        except Exception as e:  # propagate as a reply; never crash the pipeline
            logger.error("planner_llm_failed", error=str(e))
            if email_intent:
                return self._email_action(text, body=text)
            return self._reply(f"❌ Chat error: {e!s}", confidence=1.0)

        data = self._extract_json(raw)
        if data is None:
            # Not structured. If the operator clearly asked to email, coerce to SEND_EMAIL and
            # carry the model's prose as the body; otherwise treat the text as a plain reply.
            if email_intent:
                return self._email_action(text, body=(raw or "").strip() or text)
            return self._reply((raw or "").strip() or "(no response)")

        action_type = _TYPE_ALIASES.get(
            str(data.get("type", "reply")).lower(), ChatActionType.REPLY
        )
        payload = {k: v for k, v in data.items() if k not in ("type", "confidence")}

        # Deterministic override: a clear email request always sends, even if the (free, flaky)
        # model selected REPLY. Preserve any useful prose the model produced as the email body.
        if email_intent and action_type is not ChatActionType.SEND_EMAIL:
            body = str(payload.get("message") or "").strip() or (raw or "").strip() or text
            return self._email_action(text, body=body)

        if action_type is ChatActionType.REPLY and not payload.get("message"):
            payload["message"] = (raw or "").strip() or "(no response)"
        confidence = self._as_float(data.get("confidence"), default=0.9)
        requires_owner, requires_approval = _ACTION_POLICY[action_type]
        return ChatAction(
            type=action_type,
            payload=payload,
            confidence=confidence,
            requires_owner=requires_owner,
            requires_approval=requires_approval,
        )

    @staticmethod
    def _email_action(text: str, *, body: str) -> ChatAction:
        """Build a governance-stamped SEND_EMAIL action with a derived subject and the given body."""
        owner, approval = _ACTION_POLICY[ChatActionType.SEND_EMAIL]
        return ChatAction(
            type=ChatActionType.SEND_EMAIL,
            payload={"subject": _derive_subject(text), "body": body.strip() or text},
            confidence=1.0,
            requires_owner=owner,
            requires_approval=approval,
        )

    @staticmethod
    def _reply(message: str, confidence: float = 0.9) -> ChatAction:
        owner, approval = _ACTION_POLICY[ChatActionType.REPLY]
        return ChatAction(
            type=ChatActionType.REPLY,
            payload={"message": message},
            confidence=confidence,
            requires_owner=owner,
            requires_approval=approval,
        )

    @staticmethod
    def _extract_json(raw: str) -> dict[str, Any] | None:
        text = (raw or "").strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            return None
        return data if isinstance(data, dict) and "type" in data else None

    @staticmethod
    def _as_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
