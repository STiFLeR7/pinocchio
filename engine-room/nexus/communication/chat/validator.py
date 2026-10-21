"""Validator — enforces governance and schema on a planned :class:`ChatAction`.

Responsibility boundary: the validator decides *whether* an action may run. It reads the governance
requirements already encoded in the action (``requires_owner`` / ``requires_approval``) plus the
caller's context, and checks the payload has the fields the executor needs. It performs no LLM calls
and no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus.communication.channels import ChannelMessage
from nexus.communication.chat.contracts import ChatAction, ChatActionType

# Required payload keys per action type (schema check).
_REQUIRED_FIELDS: dict[ChatActionType, tuple[str, ...]] = {
    ChatActionType.REPLY: ("message",),
    ChatActionType.SEND_EMAIL: ("body",),
    ChatActionType.CREATE_TASK: ("title",),
    ChatActionType.RUN_RESEARCH: ("topic",),
    ChatActionType.SHOW_STATUS: (),
    ChatActionType.APPROVAL_REQUEST: (),
}


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validation. ``reason`` is operator-facing when ``ok`` is False."""

    ok: bool
    reason: str = ""
    needs_approval: bool = False


class Validator:
    """Validates governance (owner/approval) and schema for a ChatAction."""

    def validate(self, action: ChatAction, message: ChannelMessage) -> ValidationResult:
        """Return whether the action may execute given the caller context."""
        # 1. Owner gate (encoded in the contract).
        if action.requires_owner and not bool(message.metadata.get("is_owner")):
            return ValidationResult(False, "Sorry — only the owner can authorize that action.")

        # 2. Schema gate.
        missing = [f for f in _REQUIRED_FIELDS.get(action.type, ()) if not action.payload.get(f)]
        if missing:
            return ValidationResult(
                False, f"I couldn't action that — missing: {', '.join(missing)}."
            )

        # 3. Approval gate (encoded in the contract) — surfaced to the executor/caller.
        if action.requires_approval:
            return ValidationResult(True, needs_approval=True)

        return ValidationResult(True)
