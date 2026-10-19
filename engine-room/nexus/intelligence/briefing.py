"""AP-307 Daily Briefing Engine.

Aggregates operational state, metrics, research findings, and audit history,
compiling them into structured morning/operational briefings, and delivering
them via Discord, SMTP, and internal memory storage. Supports checkpoint recovery.
"""

from __future__ import annotations

import enum
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from nexus.core.events import NexusEvent
from nexus.core.health import get_health_reason, is_healthy
from nexus.core.metrics import get_metrics_summary
from nexus.core.types import EventType
from nexus.gateway.communication_outbox import flush_outbox_synchronously
from nexus.memory.models import (
    ApprovalRecord,
    AuditLogRecord,
    BriefingRecord,
    ExecutionRecord,
    KnowledgeItemRecord,
    ResearchFindingRecord,
    SystemOutboxRecord,
    TaskRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from nexus.communication.discord.service import DiscordService
    from nexus.communication.email.service import EmailService
    from nexus.memory.service import MemoryService

logger = structlog.get_logger("nexus.intelligence.briefing")


class BriefingType(enum.StrEnum):
    """Available operational briefing scopes (AP-307)."""

    MORNING = "morning"
    OPERATIONAL = "operational"
    RESEARCH = "research"
    FAILURE = "failure"
    HEALTH = "health"
    CUSTOM = "custom"


class BriefingService:
    """Orchestrates aggregation, formatting, persistence, and multi-channel briefing dispatch."""

    def __init__(
        self,
        db_session: AsyncSession,
        memory_service: MemoryService,
        discord_service: DiscordService | None = None,
        email_service: EmailService | None = None,
        sync_outbox_flush: bool = True,
    ) -> None:
        self.session = db_session
        self.memory_service = memory_service
        self.discord_service = discord_service
        self.email_service = email_service
        self.sync_outbox_flush = sync_outbox_flush


    async def generate_and_dispatch_briefing(
        self,
        briefing_type: BriefingType = BriefingType.MORNING,
        channels: list[str] | None = None,
        workflow_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Fetch, aggregate, compile, save, and deliver the operational briefing.

        Supports checkpoint recovery.
        """
        import time
        start_time = time.perf_counter()
        run_id = workflow_id or uuid.uuid4()
        target_channels = channels or ["memory", "discord", "email"]
        logger.info(
            "starting_briefing_generation",
            run_id=str(run_id),
            briefing_type=briefing_type.value,
        )

        # Initialize checkpoint
        checkpoint_state = {
            "run_id": str(run_id),
            "step": "initialized",
            "briefing_type": briefing_type.value,
            "channels": target_channels,
            "delivered_channels": [],
            "briefing_id": None,
        }
        await self.memory_service.create_checkpoint(run_id, "initialized", checkpoint_state)

        # 1. Aggregate Data
        data = await self._aggregate_operational_data()

        # 2. Render summary
        markdown_body = self._render_markdown(briefing_type, data)
        html_body = self._render_html(briefing_type, data)

        content_hash = hashlib.sha256(markdown_body.encode("utf-8")).hexdigest()
        finding_count = len(data["findings"])

        # Check for duplication (hash check)
        dup_stmt = select(BriefingRecord).where(BriefingRecord.content_hash == content_hash)
        dup_res = await self.session.execute(dup_stmt)
        if dup_res.scalar_one_or_none():
            logger.info("briefing_content_unchanged_skipping_persistence", run_id=str(run_id))
            return run_id

        # 3. Persist Briefing Record
        briefing_rec = BriefingRecord(
            id=uuid.uuid4(),
            briefing_type=briefing_type.value,
            generated_at=datetime.now(UTC),
            delivery_channels=[],
            content_hash=content_hash,
            finding_count=finding_count,
            status="pending",
            summary=markdown_body,
        )
        self.session.add(briefing_rec)
        await self.session.flush()

        checkpoint_state["step"] = "persisted"
        checkpoint_state["briefing_id"] = str(briefing_rec.id)
        await self.memory_service.create_checkpoint(run_id, "persisted", checkpoint_state)

        # 4. Deliver Channels
        delivered: list[str] = []

        # Memory persistence delivery
        if "memory" in target_channels:
            try:
                knowledge_rec = KnowledgeItemRecord(
                    id=uuid.uuid4(),
                    title=f"Nexus {briefing_type.value.capitalize()} Briefing - {datetime.now().strftime('%Y-%m-%d')}",
                    source="briefing_engine",
                    summary=markdown_body,
                    tags=["briefing", briefing_type.value],
                )
                self.session.add(knowledge_rec)
                delivered.append("memory")
            except Exception as e:
                logger.error("memory_briefing_delivery_failed", error=str(e))

        # Checkpoint before network operations
        checkpoint_state["step"] = "local_delivered"
        checkpoint_state["delivered_channels"] = delivered
        await self.memory_service.create_checkpoint(run_id, "local_delivered", checkpoint_state)

        # Decoupled outbox insertion for Discord & Email
        if "discord" in target_channels:
            outbox_discord = SystemOutboxRecord(
                id=uuid.uuid4(),
                channel="discord",
                payload={"content": markdown_body},
                status="pending",
                correlation_id=run_id,
                source_type="briefing",
                source_id=briefing_rec.id,
            )
            self.session.add(outbox_discord)

        if "email" in target_channels:
            subject = f"Nexus {briefing_type.value.capitalize()} Operational digest"
            outbox_email = SystemOutboxRecord(
                id=uuid.uuid4(),
                channel="email",
                payload={
                    "subject": subject,
                    "markdown_body": markdown_body,
                    "html_body": html_body,
                },
                status="pending",
                correlation_id=run_id,
                source_type="briefing",
                source_id=briefing_rec.id,
            )
            self.session.add(outbox_email)

        await self.session.flush()

        # Checkpoint: Outbox Queued
        checkpoint_state["step"] = "outbox_queued"
        checkpoint_state["delivered_channels"] = delivered
        await self.memory_service.create_checkpoint(run_id, "outbox_queued", checkpoint_state)

        # Synchronous flush if required (e.g. in tests)
        if getattr(self, "sync_outbox_flush", True):
            await flush_outbox_synchronously(
                self.session,
                run_id,
                self.discord_service,
                self.email_service,
            )
            # Re-fetch briefing record status and delivered channels
            await self.session.refresh(briefing_rec)
            delivered = briefing_rec.delivery_channels or []
        else:
            briefing_rec.delivery_channels = delivered
            briefing_rec.status = "pending"
            await self.session.flush()


        # Checkpoint: Completed
        checkpoint_state["step"] = "completed"
        checkpoint_state["delivered_channels"] = delivered
        await self.memory_service.create_checkpoint(run_id, "completed", checkpoint_state)

        # Emit audit event
        report_event = NexusEvent(
            event_type=EventType.REPORT_GENERATED,
            entity_type="briefing",
            entity_id=briefing_rec.id,
            data={
                "briefing_id": str(briefing_rec.id),
                "briefing_type": briefing_type.value,
                "channels_attempted": target_channels,
                "channels_delivered": delivered,
                "status": briefing_rec.status,
            },
            source="briefing_engine",
        )
        await self.memory_service.log_event(report_event)

        duration = (time.perf_counter() - start_time) * 1000.0
        from nexus.core.metrics import record_metric
        record_metric("briefing_generation_duration_ms", duration)

        logger.info(
            "briefing_generation_completed",
            briefing_id=str(briefing_rec.id),
            status=briefing_rec.status,
            duration_ms=round(duration, 2),
        )
        return briefing_rec.id

    async def resume_briefing_run(self, workflow_id: uuid.UUID) -> uuid.UUID:
        """Resume briefing generation and retry failed deliveries from checkpoints."""
        state = await self.memory_service.restore_checkpoint(workflow_id)
        if not state:
            raise ValueError(f"No checkpoint state found for briefing run: {workflow_id}")

        step = state.get("step")
        briefing_id_str = state.get("briefing_id")
        delivered = state.get("delivered_channels", [])
        target_channels = state.get("channels", [])
        briefing_type_val = state.get("briefing_type", "morning")

        logger.info(
            "resuming_briefing_generation",
            run_id=str(workflow_id),
            step=step,
            briefing_id=briefing_id_str,
        )

        if step == "initialized" or not briefing_id_str:
            # Restart generation completely
            return await self.generate_and_dispatch_briefing(
                BriefingType(briefing_type_val),
                target_channels,
                workflow_id,
            )

        # Retrieve existing BriefingRecord
        briefing_id = uuid.UUID(briefing_id_str)
        stmt = select(BriefingRecord).where(BriefingRecord.id == briefing_id)
        res = await self.session.execute(stmt)
        briefing_rec = res.scalar_one_or_none()
        if not briefing_rec:
            raise ValueError(f"Briefing record {briefing_id} not found in database.")

        markdown_body = briefing_rec.summary
        html_body = self._render_html(BriefingType(briefing_type_val), await self._aggregate_operational_data())

        # Process deliveries not yet successful
        # Verify or create outbox items for missing channels
        if "discord" in target_channels and "discord" not in delivered:
            stmt_o = select(SystemOutboxRecord).where(
                SystemOutboxRecord.source_id == briefing_id,
                SystemOutboxRecord.channel == "discord",
            )
            res_o = await self.session.execute(stmt_o)
            if not res_o.scalar_one_or_none():
                outbox_discord = SystemOutboxRecord(
                    id=uuid.uuid4(),
                    channel="discord",
                    payload={"content": markdown_body},
                    status="pending",
                    correlation_id=workflow_id,
                    source_type="briefing",
                    source_id=briefing_id,
                )
                self.session.add(outbox_discord)

        if "email" in target_channels and "email" not in delivered:
            stmt_o = select(SystemOutboxRecord).where(
                SystemOutboxRecord.source_id == briefing_id,
                SystemOutboxRecord.channel == "email",
            )
            res_o = await self.session.execute(stmt_o)
            if not res_o.scalar_one_or_none():
                subject = f"Nexus {briefing_type_val.capitalize()} Operational digest"
                outbox_email = SystemOutboxRecord(
                    id=uuid.uuid4(),
                    channel="email",
                    payload={
                        "subject": subject,
                        "markdown_body": markdown_body,
                        "html_body": html_body,
                    },
                    status="pending",
                    correlation_id=workflow_id,
                    source_type="briefing",
                    source_id=briefing_id,
                )
                self.session.add(outbox_email)

        await self.session.flush()

        if getattr(self, "sync_outbox_flush", True):
            await flush_outbox_synchronously(
                self.session,
                workflow_id,
                self.discord_service,
                self.email_service,
            )
            await self.session.refresh(briefing_rec)
            delivered = briefing_rec.delivery_channels
        else:
            briefing_rec.delivery_channels = delivered
            briefing_rec.status = "pending"
            await self.session.flush()


        # Checkpoint completed
        state["step"] = "completed"
        state["delivered_channels"] = delivered
        await self.memory_service.create_checkpoint(workflow_id, "completed", state)

        # Emit audit log event
        report_event = NexusEvent(
            event_type=EventType.REPORT_GENERATED,
            entity_type="briefing",
            entity_id=briefing_rec.id,
            data={
                "briefing_id": str(briefing_rec.id),
                "briefing_type": briefing_type_val,
                "channels_attempted": target_channels,
                "channels_delivered": delivered,
                "status": briefing_rec.status,
                "resumed": True,
            },
            source="briefing_engine",
        )
        await self.memory_service.log_event(report_event)

        return briefing_rec.id

    async def _deliver_discord(self, content: str) -> None:
        """Deliver briefing contents to Discord summaries channel with chunking controls."""
        if not self.discord_service:
            return

        # Discord limit is 2000 chars. We split safely at double newlines or single newlines
        max_chunk = 1900
        text = content
        chunks = []

        while len(text) > max_chunk:
            # find last double newline in the chunk window
            split_idx = text.rfind("\n\n", 0, max_chunk)
            if split_idx == -1:
                # try single newline
                split_idx = text.rfind("\n", 0, max_chunk)
            if split_idx == -1:
                # hard cutoff
                split_idx = max_chunk
            chunks.append(text[:split_idx].strip())
            text = text[split_idx:].strip()

        if text:
            chunks.append(text)

        # Deliver each chunk
        for chunk in chunks:
            await self.discord_service.post_message("summaries", content=chunk)

    async def _aggregate_operational_data(self) -> dict[str, Any]:
        """Query various database tables to compile structured operational context."""
        now = datetime.now(UTC)
        past_24h = now - timedelta(hours=24)

        # 1. Research findings (past 24h, sorted by score)
        stmt_find = (
            select(ResearchFindingRecord)
            .where(ResearchFindingRecord.discovered_at >= past_24h)
            .order_by(ResearchFindingRecord.importance_score.desc())
        )
        res_find = await self.session.execute(stmt_find)
        findings = res_find.scalars().all()

        # 2. Open Tasks
        stmt_tasks = select(TaskRecord).where(
            TaskRecord.status.in_(["created", "queued", "active", "blocked"])
        )
        res_tasks = await self.session.execute(stmt_tasks)
        open_tasks = res_tasks.scalars().all()

        # 3. Pending Approvals
        stmt_app = select(ApprovalRecord).where(ApprovalRecord.status == "pending")
        res_app = await self.session.execute(stmt_app)
        pending_approvals = res_app.scalars().all()

        # 4. Failed Executions (past 24h)
        stmt_fail = (
            select(ExecutionRecord)
            .where(ExecutionRecord.started_at >= past_24h)
            .where(ExecutionRecord.exit_status.in_(["failure", "error", "timeout"]))
        )
        res_fail = await self.session.execute(stmt_fail)
        failures = res_fail.scalars().all()

        # 5. Recent Executions (past 24h)
        stmt_exec = select(ExecutionRecord).where(ExecutionRecord.started_at >= past_24h)
        res_exec = await self.session.execute(stmt_exec)
        executions = res_exec.scalars().all()

        # 6. Audit details (policy violations, checkpoint recoveries)
        stmt_policy = (
            select(AuditLogRecord)
            .where(AuditLogRecord.created_at >= past_24h)
            .where(AuditLogRecord.event_type.in_(["RepositoryGovernanceError", "SystemUnhealthy"]))
        )
        res_policy = await self.session.execute(stmt_policy)
        policy_violations = res_policy.scalars().all()

        stmt_rec = (
            select(AuditLogRecord)
            .where(AuditLogRecord.created_at >= past_24h)
            .where(AuditLogRecord.event_type == EventType.WORKFLOW_RESUMED.value)
        )
        res_rec = await self.session.execute(stmt_rec)
        checkpoint_recoveries = res_rec.scalars().all()

        return {
            "findings": findings,
            "open_tasks": open_tasks,
            "pending_approvals": pending_approvals,
            "failures": failures,
            "executions": executions,
            "policy_violations": policy_violations,
            "checkpoint_recoveries": checkpoint_recoveries,
            "health": {
                "healthy": is_healthy(),
                "reason": get_health_reason(),
            },
            "metrics": get_metrics_summary(),
        }

    def _render_markdown(self, briefing_type: BriefingType, data: dict[str, Any]) -> str:
        """Compile aggregated statistics into Markdown output (for Discord and archive)."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        health_status = "🟢 HEALTHY" if data["health"]["healthy"] else f"🔴 UNHEALTHY ({data['health']['reason']})"

        parts = [
            f"# Nexus {briefing_type.value.capitalize()} Briefing - {now_str}",
            "---",
            f"**System Liveness**: {health_status}",
            "",
            "## 📊 Operational Performance Metrics (Past 24 Hours)",
        ]

        metrics = data["metrics"]
        for key, val in metrics.items():
            parts.append(
                f"- **{key}**: Avg `{val['avg']:.1f}ms` | Max `{val['max']:.1f}ms` | Count `{val['count']}`"
            )

        parts.extend([
            "",
            f"## ⏳ Active Queue: {len(data['open_tasks'])} Tasks | {len(data['pending_approvals'])} Approvals",
        ])
        for task in data["open_tasks"][:5]:
            parts.append(f"- `[{task.status.upper()}]` {task.title} (Priority: {task.priority})")
        if len(data["open_tasks"]) > 5:
            parts.append(f"... and {len(data['open_tasks']) - 5} more.")

        if data["failures"]:
            parts.extend(["", "## ⚠️ Execution Failures (Past 24 Hours)"])
            for fail in data["failures"]:
                parts.append(f"- **Task ID**: `{fail.task_id}` | Runner: `{fail.runner}` | Status: `{fail.exit_status}`")

        if data["policy_violations"]:
            parts.extend(["", "## 🔒 Security & Policy Violations"])
            for pv in data["policy_violations"]:
                parts.append(f"- `[{pv.event_type}]` {pv.data.get('reason') or pv.data}")

        parts.extend(["", f"## 🔬 Technical Research: {len(data['findings'])} New Findings"])
        for finding in data["findings"]:
            parts.append(
                f"### {finding.title} (Score: **{finding.importance_score}/5**)\n"
                f"*Source: {finding.source}* | [Link]({finding.url})\n"
                f"{finding.summary}\n"
            )
        if not data["findings"]:
            parts.append("*No new technical research items compiled in the past 24 hours.*")

        return "\n".join(parts)

    def _render_html(self, briefing_type: BriefingType, data: dict[str, Any]) -> str:
        """Compile aggregated statistics into HTML layout for email clients."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        health_color = "#15803d" if data["health"]["healthy"] else "#b91c1c"
        health_status = "HEALTHY" if data["health"]["healthy"] else f"UNHEALTHY ({data['health']['reason']})"

        metrics_rows = ""
        for key, val in data["metrics"].items():
            metrics_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;"><strong>{key}</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: right;">{val['avg']:.1f} ms</td>
                <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: right;">{val['max']:.1f} ms</td>
                <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: right;">{val['count']}</td>
            </tr>
            """

        findings_html = ""
        for finding in data["findings"]:
            findings_html += f"""
            <div style="margin-bottom: 16px; padding: 12px; border-left: 4px solid #3b82f6; background-color: #f8fafc;">
                <h4 style="margin: 0 0 4px 0; color: #1e293b;">{finding.title} (Score: {finding.importance_score}/5)</h4>
                <div style="font-size: 12px; color: #64748b; margin-bottom: 8px;">Source: {finding.source} | <a href="{finding.url}" style="color: #3b82f6;">Link</a></div>
                <div style="font-size: 14px; line-height: 1.5;">{finding.summary}</div>
            </div>
            """
        if not findings_html:
            findings_html = "<p style='color: #64748b; font-style: italic;'>No new technical research items compiled in the past 24 hours.</p>"

        tasks_rows = ""
        for task in data["open_tasks"][:5]:
            tasks_rows += f"<li><strong>[{task.status.upper()}]</strong> {task.title} (Priority: {task.priority})</li>"
        if len(data["open_tasks"]) > 5:
            tasks_rows += f"<li>... and {len(data['open_tasks']) - 5} more.</li>"

        failures_html = ""
        if data["failures"]:
            failures_html = "<h3>⚠️ Failures (Past 24h)</h3><ul>"
            for fail in data["failures"]:
                failures_html += f"<li>Task <code>{fail.task_id}</code> | Runner: {fail.runner} | Exit: {fail.exit_status}</li>"
            failures_html += "</ul>"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Nexus digest</title>
        </head>
        <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #334155; line-height: 1.6; background-color: #f1f5f9; padding: 20px; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid #e2e8f0;">
                <div style="background-color: #0f172a; padding: 24px; text-align: center; color: #ffffff;">
                    <h2 style="margin: 0; font-weight: 500;">Nexus {briefing_type.value.capitalize()} Operational Summary</h2>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">{now_str}</div>
                </div>
                <div style="padding: 24px;">
                    <div style="margin-bottom: 20px; padding: 12px; border-radius: 6px; background-color: {health_color}1a; border: 1px solid {health_color}33; color: {health_color}; font-weight: bold; text-align: center;">
                        Liveness Status: {health_status}
                    </div>

                    <h3 style="border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; color: #0f172a;">📊 Performance Metrics</h3>
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 20px;">
                        <thead>
                            <tr style="background-color: #f8fafc; text-align: left;">
                                <th style="padding: 8px; border-bottom: 2px solid #cbd5e1;">Metric</th>
                                <th style="padding: 8px; border-bottom: 2px solid #cbd5e1; text-align: right;">Avg</th>
                                <th style="padding: 8px; border-bottom: 2px solid #cbd5e1; text-align: right;">Max</th>
                                <th style="padding: 8px; border-bottom: 2px solid #cbd5e1; text-align: right;">Count</th>
                            </tr>
                        </thead>
                        <tbody>
                            {metrics_rows}
                        </tbody>
                    </table>

                    <h3 style="border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; color: #0f172a;">⏳ Active Queues</h3>
                    <ul style="padding-left: 20px; font-size: 14px; margin-bottom: 20px;">
                        {tasks_rows}
                    </ul>

                    {failures_html}

                    <h3 style="border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; color: #0f172a;">🔬 Research findings ({len(data['findings'])})</h3>
                    {findings_html}
                </div>
                <div style="background-color: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0;">
                    Nexus Orchestration Control Plane - Autonomous Briefing Engine
                </div>
            </div>
        </body>
        </html>
        """
