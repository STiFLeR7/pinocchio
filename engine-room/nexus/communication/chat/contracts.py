"""Chat pipeline contracts — the typed boundary between Planner, Validator, and Executor.

Governance is **encoded into the contract** (``requires_owner`` / ``requires_approval``) rather than
inferred downstream, so the Validator enforces policy from data, not from heuristics. These flags are
stamped server-side by the Planner from a trusted policy table — never taken from the LLM.
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field

from nexus.communication.channels import ChannelRole


class ChatActionType(enum.StrEnum):
    """The set of actions the planner may select."""

    REPLY = "reply"
    SEND_EMAIL = "send_email"
    CREATE_TASK = "create_task"
    RUN_RESEARCH = "run_research"
    SHOW_STATUS = "show_status"
    APPROVAL_REQUEST = "approval_request"


class ChatAction(BaseModel):
    """A planned action with its parameters and governance requirements."""

    type: ChatActionType
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    requires_owner: bool = False
    requires_approval: bool = False


class OutboundPost(BaseModel):
    """A message the orchestration layer wants routed to a (non-origin) semantic channel."""

    role: ChannelRole
    content: str | None = None
    card: dict[str, Any] | None = None  # structured status-card payload (adapter renders it)


class ChatResponse(BaseModel):
    """Structured result the adapter renders. Contains no platform types."""

    reply: str | None = None  # text back to the originating conversation
    posts: list[OutboundPost] = Field(default_factory=list)  # routed elsewhere (e.g. SYSTEM card)
    action_type: ChatActionType = ChatActionType.REPLY
    executed: bool = False
