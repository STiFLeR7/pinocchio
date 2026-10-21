"""ChatService — composes the Conversation → Planner → Validator → Executor pipeline.

This is the single entry point the (thin) adapters call. It owns conversation memory and wires the
three responsibilities together; it holds no platform types and performs no I/O beyond delegating to
the injected planner/validator/executor.

    ChannelMessage → [memory] → Planner → ChatAction → Validator → Executor → ChatResponse
"""

from __future__ import annotations

from typing import Any

import structlog

from nexus.communication.channels import ChannelMessage
from nexus.communication.chat.contracts import ChatActionType, ChatResponse
from nexus.communication.chat.executor import Executor
from nexus.communication.chat.planner import Planner
from nexus.communication.chat.validator import Validator

logger = structlog.get_logger("nexus.communication.chat.service")

MAX_CHAT_HISTORY = 12  # user+assistant messages retained per conversation


class ChatService:
    """Orchestrates the chat pipeline and conversation memory."""

    def __init__(
        self,
        planner: Planner,
        validator: Validator,
        executor: Executor,
    ) -> None:
        self.planner = planner
        self.validator = validator
        self.executor = executor
        self._history: dict[str, list[dict[str, str]]] = {}

    @classmethod
    def build(
        cls,
        llm_client: Any,
        email_service: Any = None,
        owner_email: str = "",
        session_factory: Any = None,
        event_gateway: Any = None,
    ) -> ChatService:
        """Convenience constructor wiring the default pipeline from services."""
        return cls(
            planner=Planner(llm_client),
            validator=Validator(),
            executor=Executor(
                email_service=email_service,
                owner_email=owner_email,
                session_factory=session_factory,
                event_gateway=event_gateway,
            ),
        )

    def history_for(self, conversation_id: str) -> list[dict[str, str]]:
        """Expose a conversation's rolling history (for tests/inspection)."""
        return self._history.setdefault(conversation_id, [])

    async def handle(self, message: ChannelMessage) -> ChatResponse:
        """Run the full pipeline for one inbound message, updating conversation memory."""
        history = self._history.setdefault(message.conversation_id, [])

        action = await self.planner.plan(message.message, history[-MAX_CHAT_HISTORY:])
        verdict = self.validator.validate(action, message)

        if not verdict.ok:
            response = ChatResponse(reply=verdict.reason, action_type=action.type, executed=False)
        elif verdict.needs_approval:
            # Governance: action requires human approval before execution (not auto-run here).
            response = ChatResponse(
                reply="That action needs approval — I've flagged it for the owner.",
                action_type=action.type,
                executed=False,
            )
            logger.info("chat_action_requires_approval", action=action.type.value)
        else:
            response = await self.executor.execute(action)

        # Update rolling memory with a compact assistant note.
        note = response.reply or f"({action.type.value})"
        history.append({"role": "user", "content": message.message})
        history.append({"role": "assistant", "content": note[:1500]})
        del history[:-MAX_CHAT_HISTORY]

        logger.info(
            "chat_handled",
            action=action.type.value,
            executed=response.executed,
            conversation=message.conversation_id,
        )
        return response

    # Convenience for callers that only have raw text (e.g. unit harnesses).
    async def handle_text(
        self, *, conversation_id: str, text: str, author: str = "unknown", is_owner: bool = False
    ) -> ChatResponse:
        """Build a CHAT ChannelMessage from raw fields and run the pipeline."""
        msg = ChannelMessage(
            author=author,
            channel_id=conversation_id,
            conversation_id=conversation_id,
            message=text,
            metadata={"is_owner": is_owner},
        )
        return await self.handle(msg)


__all__ = [
    "ChatActionType",
    "ChatResponse",
    "ChatService",
    "Executor",
    "Planner",
    "Validator",
]
