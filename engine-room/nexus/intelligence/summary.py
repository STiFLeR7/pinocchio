"""Task summary generator engine.

Leverages OpenRouter LLM connection to generate high-level execution reports
from database task and execution records.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from nexus.core.exceptions import ModelRouterError
from nexus.memory.models import ExecutionRecord, TaskRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from nexus.intelligence.openrouter import OpenRouterClient


class SummaryEngine:
    """Retrieves logs from database execution records and compiles structured summaries."""

    def __init__(self, db_session: AsyncSession, openrouter_client: OpenRouterClient) -> None:
        """Initialize with session and OpenRouter client reference."""
        self.session = db_session
        self.openrouter = openrouter_client

    async def generate_task_summary(self, task_id: uuid.UUID) -> str:
        """Compile a concise completion summary using OpenRouter completions."""
        # 1. Fetch Task details
        task_stmt = select(TaskRecord).where(TaskRecord.id == task_id)
        task_res = await self.session.execute(task_stmt)
        task = task_res.scalar_one_or_none()

        if not task:
            raise ModelRouterError(f"Task with ID {task_id} not found in database.")

        # 2. Fetch latest Execution details
        exec_stmt = (
            select(ExecutionRecord)
            .where(ExecutionRecord.task_id == task_id)
            .order_by(ExecutionRecord.created_at.desc())
            .limit(1)
        )
        exec_res = await self.session.execute(exec_stmt)
        execution = exec_res.scalar_one_or_none()

        if not execution:
            raise ModelRouterError(f"No execution logs found for Task {task_id}.")

        # 3. Build Prompt
        prompt_parts = [
            "You are the Nexus Control Plane Summarizer. Summarize the outcome of this run.",
            "",
            f"Task Title: {task.title}",
            f"Task Description: {task.description or 'None'}",
            f"Exit Status: {execution.exit_status}",
            f"Runner Backend: {execution.runner}",
            "",
            "Execution Logs:",
            "```",
            f"{execution.logs or 'No output recorded.'}",
            "```",
        ]

        if execution.result:
            try:
                result_data = json.loads(execution.result)
                prompt_parts.append(f"Execution Result Data: {json.dumps(result_data, indent=2)}")
            except ValueError:
                prompt_parts.append(f"Execution Result Data: {execution.result}")

        prompt_parts.extend(
            [
                "",
                "Summary Guidelines:",
                "- Focus on what actions were taken, whether they succeeded, and main findings.",
                "- Be concise, professional, and keep it under 150 words.",
                "- Use standard bullet points.",
            ]
        )

        prompt = "\n".join(prompt_parts)
        system_prompt = "You are a precise and objective AI operation auditor."

        # 4. Generate LLM completion
        summary_text = await self.openrouter.complete(prompt, system_prompt)
        return summary_text.strip()
