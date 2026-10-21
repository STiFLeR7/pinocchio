"""Executor — performs a validated :class:`ChatAction` via injected services.

Responsibility boundary: the executor decides *how* to carry out an action. It calls domain services
(EmailService, TaskService, ResearchService, …) that are injected or constructed per-operation from
an injected ``session_factory``, emits a SYSTEM status card for side-effecting actions, and returns a
transport-neutral :class:`ChatResponse`. It performs no governance decisions (the Validator already
approved) and no LLM calls.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select

from nexus.communication.channels import ChannelRole
from nexus.communication.chat.contracts import (
    ChatAction,
    ChatActionType,
    ChatResponse,
    OutboundPost,
)

logger = structlog.get_logger("nexus.communication.chat.executor")

# Runtime the research task is routed to (the Nexus agent has search/research tools).
_RESEARCH_RUNTIME_ID = "nexus"


class Executor:
    """Executes validated actions against injected domain services."""

    def __init__(
        self,
        email_service: Any = None,
        owner_email: str = "",
        session_factory: Any = None,
        event_gateway: Any = None,
    ) -> None:
        self.email_service = email_service
        self.owner_email = owner_email
        self.session_factory = session_factory
        self.event_gateway = event_gateway

    async def execute(self, action: ChatAction) -> ChatResponse:
        """Dispatch the action; return a transport-neutral response."""
        if action.type is ChatActionType.REPLY:
            return ChatResponse(
                reply=str(action.payload.get("message") or "(no response)"),
                action_type=action.type,
                executed=True,
            )
        if action.type is ChatActionType.SEND_EMAIL:
            return await self._send_email(action)
        if action.type is ChatActionType.CREATE_TASK:
            return await self._create_task(action)
        if action.type is ChatActionType.RUN_RESEARCH:
            return await self._run_research(action)
        if action.type is ChatActionType.SHOW_STATUS:
            return await self._show_status(action)
        # Anything still unmapped (e.g. approval_request is handled upstream) — honest, non-crashing.
        return ChatResponse(
            reply=f"That action (`{action.type.value}`) is recognized but not wired up yet.",
            action_type=action.type,
            executed=False,
        )

    # ------------------------------------------------------------------ email
    async def _send_email(self, action: ChatAction) -> ChatResponse:
        subject = str(action.payload.get("subject") or "Message from Nexus").strip()
        body = str(action.payload.get("body") or "").strip()
        recipient = self.owner_email or "operator"

        if self.email_service is None:
            return ChatResponse(
                reply="⚠️ Email is not configured.",
                action_type=ChatActionType.SEND_EMAIL,
                executed=False,
                posts=[_email_card(subject, "failed")],
            )
        try:
            html = (
                "<div style='font-family:sans-serif;line-height:1.5;white-space:pre-wrap'>"
                f"{body}</div>"
            )
            await self.email_service.send_briefing_email(subject, body, html)
        except Exception as e:  # surface failure; never crash
            logger.error("executor_send_email_failed", error=str(e))
            return ChatResponse(
                reply=f"❌ Email failed: {e!s}",
                action_type=ChatActionType.SEND_EMAIL,
                executed=False,
                posts=[_email_card(subject, "failed")],
            )
        logger.info("executor_email_sent", recipient=recipient, subject=subject)
        return ChatResponse(
            reply=f"📧 Sent to **{recipient}** — *{subject}*",
            action_type=ChatActionType.SEND_EMAIL,
            executed=True,
            posts=[_email_card(subject, "sent")],
        )

    # ------------------------------------------------------------- create_task
    async def _create_task(self, action: ChatAction) -> ChatResponse:
        title = str(action.payload.get("title") or "").strip()
        description = action.payload.get("description")
        priority = _as_int(action.payload.get("priority"), default=2)

        if self.session_factory is None:
            return ChatResponse(
                reply="⚠️ Task creation is not configured.",
                action_type=ChatActionType.CREATE_TASK,
                executed=False,
                posts=[_task_card(title, "create_task", "failed")],
            )
        try:
            task_id, status = await self._persist_task(title, description, priority)
        except Exception as e:
            logger.error("executor_create_task_failed", error=str(e))
            return ChatResponse(
                reply=f"❌ Couldn't create the task: {e!s}",
                action_type=ChatActionType.CREATE_TASK,
                executed=False,
                posts=[_task_card(title, "create_task", "failed")],
            )
        logger.info("executor_task_created", task_id=str(task_id), title=title)
        return ChatResponse(
            reply=f"✅ Task created & queued — **{title}**\n`{task_id}` · status `{status}`",
            action_type=ChatActionType.CREATE_TASK,
            executed=True,
            posts=[_task_card(title, "create_task", "queued")],
        )

    # ------------------------------------------------------------ run_research
    async def _run_research(self, action: ChatAction) -> ChatResponse:
        topic = str(action.payload.get("topic") or "").strip()

        if self.session_factory is None:
            return ChatResponse(
                reply="⚠️ Research is not configured.",
                action_type=ChatActionType.RUN_RESEARCH,
                executed=False,
                posts=[_task_card(topic, "run_research", "failed")],
            )
        try:
            task_id, status = await self._persist_task(
                title=f"Research: {topic}",
                description=topic,
                priority=2,
                runtime_id=_RESEARCH_RUNTIME_ID,
            )
        except Exception as e:
            logger.error("executor_run_research_failed", error=str(e))
            return ChatResponse(
                reply=f"❌ Couldn't queue research: {e!s}",
                action_type=ChatActionType.RUN_RESEARCH,
                executed=False,
                posts=[_task_card(topic, "run_research", "failed")],
            )
        logger.info("executor_research_queued", task_id=str(task_id), topic=topic)
        return ChatResponse(
            reply=f"🔬 Queued a research task on **{topic}** for the agent.\n`{task_id}` · status `{status}`",
            action_type=ChatActionType.RUN_RESEARCH,
            executed=True,
            posts=[_task_card(topic, "run_research", "queued")],
        )

    # ------------------------------------------------------------- show_status
    async def _show_status(self, action: ChatAction) -> ChatResponse:
        from nexus.core.health import get_health_reason, is_healthy

        healthy = is_healthy()
        liveness = "🟢 HEALTHY" if healthy else f"🔴 UNHEALTHY ({get_health_reason()})"
        open_tasks = pending_approvals = findings_24h = 0

        if self.session_factory is not None:
            try:
                open_tasks, pending_approvals, findings_24h = await self._status_counts()
            except Exception as e:  # status must never crash the chat
                logger.error("executor_show_status_failed", error=str(e))

        reply = (
            f"**Nexus status** — {liveness}\n"
            f"• Open tasks: `{open_tasks}`\n"
            f"• Pending approvals: `{pending_approvals}`\n"
            f"• Research findings (24h): `{findings_24h}`"
        )
        card = OutboundPost(
            role=ChannelRole.SYSTEM,
            card={
                "title": "Dex • Status",
                "risk": "LOW",
                "plan": f"Liveness {('OK' if healthy else 'DEGRADED')} · "
                f"{open_tasks} tasks · {pending_approvals} approvals · {findings_24h} findings/24h",
                "tools": "show_status",
                "verification": "sent" if healthy else "failed",
            },
        )
        return ChatResponse(
            reply=reply,
            action_type=ChatActionType.SHOW_STATUS,
            executed=True,
            posts=[card],
        )

    # ----------------------------------------------------------------- helpers
    async def _persist_task(
        self,
        title: str,
        description: Any = None,
        priority: int = 2,
        runtime_id: str = "gemini",
    ) -> tuple[Any, str]:
        """Create and enqueue a task via TaskService; return (id, status). Same path as /task_create."""
        from nexus.core.types import TaskStatus
        from nexus.database import get_session
        from nexus.memory.service import MemoryService
        from nexus.memory.task_service import TaskService

        async with get_session(self.session_factory) as session:
            memory_service = MemoryService(session)
            task_service = TaskService(session, memory_service, self.event_gateway)
            task = await task_service.create_task(
                title=title,
                description=str(description) if description is not None else None,
                priority=priority,
                runtime_id=runtime_id,
            )
            updated = await task_service.change_status(task.id, TaskStatus.QUEUED)
            return updated.id, updated.status

    async def _status_counts(self) -> tuple[int, int, int]:
        """Return (open_tasks, pending_approvals, research_findings_24h)."""
        from nexus.database import get_session
        from nexus.memory.models import (
            ApprovalRecord,
            ResearchFindingRecord,
            TaskRecord,
        )

        past_24h = datetime.now(UTC) - timedelta(hours=24)
        async with get_session(self.session_factory) as session:
            open_tasks = await session.scalar(
                select(func.count())
                .select_from(TaskRecord)
                .where(TaskRecord.status.in_(["created", "queued", "active", "blocked"]))
            )
            pending_approvals = await session.scalar(
                select(func.count())
                .select_from(ApprovalRecord)
                .where(ApprovalRecord.status == "pending")
            )
            findings_24h = await session.scalar(
                select(func.count())
                .select_from(ResearchFindingRecord)
                .where(ResearchFindingRecord.discovered_at >= past_24h)
            )
        return int(open_tasks or 0), int(pending_approvals or 0), int(findings_24h or 0)


def _email_card(subject: str, verification: str) -> OutboundPost:
    """Build a SYSTEM-channel status card for an email action."""
    return OutboundPost(
        role=ChannelRole.SYSTEM,
        card={
            "title": "Dex • Email Action",
            "risk": "LOW",
            "plan": f"Email operator: {subject}",
            "tools": "send_email",
            "verification": verification,
        },
    )


def _task_card(subject: str, tool: str, verification: str) -> OutboundPost:
    """Build a SYSTEM-channel status card for a task/research action."""
    return OutboundPost(
        role=ChannelRole.SYSTEM,
        card={
            "title": "Dex • Task Action",
            "risk": "LOW",
            "plan": f"{tool}: {subject}"[:1000],
            "tools": tool,
            "verification": verification,
        },
    )


def _as_int(value: Any, default: int) -> int:
    """Coerce an LLM-provided value to int, falling back to a default."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
