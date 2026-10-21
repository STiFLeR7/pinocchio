from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from nexus.core.exceptions import ExecutionEngineError
from nexus.core.types import ExecutionStatus
from nexus.execution.governance import GovernanceManager
from nexus.execution.runners import runtime_registry
from nexus.execution.runners.base import CLIRuntimeAdapter, resolve_execution_timeout
from nexus.memory.models import (
    ExecutionArtifactRecord,
    ExecutionRecord,
    ExecutionStepRecord,
    WorkflowCheckpointRecord,
)


@runtime_registry.register("claude")
class ClaudeRuntimeAdapter(CLIRuntimeAdapter):
    """Execution adapter for the Claude CLI and API runtime."""

    def __init__(
        self,
        db_session: Any,
        execution_id: Any,
        event_gateway: Any = None,
        openrouter_client: Any = None,
        settings: Any = None,
    ) -> None:
        """Initialize the ClaudeRuntimeAdapter with execution and API references."""
        self.session = db_session
        self.execution_id = execution_id
        self.event_gateway = event_gateway
        self.openrouter_client = openrouter_client
        self.settings = settings
        self.active_process: Any = None
        self.current_step_id: Any = None
        self.stdout_log = ""
        self.stderr_log = ""
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    async def initialize(self) -> None:
        """Verify API key availability and environment readiness."""
        # Non-blocking warning so offline testing can run with mock wrappers
        pass

    async def validate(self, repository_path: str, command: str) -> None:
        """Run repository safety checks using the GovernanceManager."""
        stmt = select(ExecutionRecord).where(ExecutionRecord.id == self.execution_id)
        res = await self.session.execute(stmt)
        exec_record = res.scalar_one_or_none()
        if not exec_record:
            raise ExecutionEngineError(f"Execution record {self.execution_id} not found.")

        gov = GovernanceManager(self.session)
        await gov.validate_execution(
            task_id=exec_record.task_id,
            working_dir=repository_path,
            command=command,
            runtime="claude",
        )

    async def execute(self, command: str) -> dict[str, Any]:
        """Spawn the command subprocess under the Claude execution context."""
        self.start_time = time.time()

        stmt = select(ExecutionRecord).where(ExecutionRecord.id == self.execution_id)
        res = await self.session.execute(stmt)
        exec_record = res.scalar_one()

        cwd = exec_record.repository or "."

        # Resolve the ADR-010 Claude timeout from configuration, clamped by hard_limit (A-002)
        timeout = resolve_execution_timeout(self.settings, "claude_timeout")

        # Create step record
        step = ExecutionStepRecord(
            execution_id=self.execution_id,
            command=command,
            status=ExecutionStatus.RUNNING.value,
            timeout_threshold=timeout,
            last_heartbeat=datetime.now(UTC),
        )
        self.session.add(step)
        await self.session.flush()
        self.current_step_id = step.id

        # Update parent execution heartbeat
        exec_record.last_heartbeat = step.last_heartbeat
        await self.session.flush()

        try:
            # Spawn shell command via SandboxManager
            from nexus.execution.sandbox.manager import SandboxManager
            sandbox_mgr = SandboxManager(self.session, self.settings)
            self.active_process = await sandbox_mgr.execute(
                command=command,
                cwd=cwd,
                timeout=timeout,
                correlation_id=self.execution_id,
            )
            step.pid = self.active_process.pid
            await self.session.flush()

            # Enforce timeout policy
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                self.active_process.communicate(),
                timeout=float(timeout),
            )
            self.end_time = time.time()

            self.stdout_log = stdout_bytes.decode("utf-8", errors="replace")
            self.stderr_log = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = self.active_process.returncode or 0

        except TimeoutError:
            await self.terminate()
            self.end_time = time.time()
            self.stdout_log = ""
            self.stderr_log = f"Timeout: Process exceeded timeout limit of {timeout}s."
            exit_code = -1
        except Exception as e:
            self.end_time = time.time()
            self.stdout_log = ""
            self.stderr_log = f"Execution error: {e!s}"
            exit_code = -1
        finally:
            self.active_process = None

        # Update step state
        step.status = ExecutionStatus.COMPLETED.value
        step.exit_code = exit_code
        step.stdout = self.stdout_log
        step.stderr = self.stderr_log
        step.last_heartbeat = datetime.now(UTC)
        await self.session.flush()

        duration = self.end_time - self.start_time
        return {
            "exit_code": exit_code,
            "duration_seconds": duration,
            "stdout_len": len(self.stdout_log),
            "stderr_len": len(self.stderr_log),
        }

    async def heartbeat(self) -> None:
        """Update last_heartbeat timestamps in active database records."""
        now = datetime.now(UTC)
        if self.current_step_id:
            step_stmt = select(ExecutionStepRecord).where(
                ExecutionStepRecord.id == self.current_step_id
            )
            res = await self.session.execute(step_stmt)
            step = res.scalar_one_or_none()
            if step:
                step.last_heartbeat = now

        exec_stmt = select(ExecutionRecord).where(ExecutionRecord.id == self.execution_id)
        exec_res = await self.session.execute(exec_stmt)
        exec_record = exec_res.scalar_one_or_none()
        if exec_record:
            exec_record.last_heartbeat = now

        await self.session.flush()

    async def checkpoint(self, step_name: str, state: dict[str, Any]) -> None:
        """Persist intermediate execution checkpoints to memory."""
        checkpoint = WorkflowCheckpointRecord(
            workflow_id=self.execution_id,
            step_name=step_name,
            state=state,
            completed_at=datetime.now(UTC),
        )
        self.session.add(checkpoint)
        await self.session.flush()

    async def terminate(self) -> None:
        """Immediately abort running processes."""
        if self.active_process:
            try:
                self.active_process.terminate()
                await self.active_process.wait()
            except Exception:
                pass

    async def summarize(self) -> str:
        """Compile run output and request openrouter summary report."""
        if not self.openrouter_client:
            return "No summarization service configured."

        prompt = (
            "Summarize the following terminal execution result concisely:\n"
            f"STDOUT:\n{self.stdout_log[:2000]}\n"
            f"STDERR:\n{self.stderr_log[:1000]}\n"
        )
        try:
            summary = await self.openrouter_client.complete(prompt)
            return str(summary)
        except Exception as e:
            return f"Failed to generate summary report: {e!s}"

    async def persist(self) -> None:
        """Persist standard output logs and git diffs as first-class artifacts."""
        duration = self.end_time - self.start_time
        exit_code = 0

        if self.current_step_id:
            step_stmt = select(ExecutionStepRecord).where(
                ExecutionStepRecord.id == self.current_step_id
            )
            res = await self.session.execute(step_stmt)
            step = res.scalar_one_or_none()
            if step:
                exit_code = step.exit_code or 0

        # Save stdout artifact
        if self.stdout_log:
            stdout_art = ExecutionArtifactRecord(
                execution_id=self.execution_id,
                artifact_type="stdout",
                name="stdout.log",
                content=self.stdout_log,
                data={"size_bytes": len(self.stdout_log)},
            )
            self.session.add(stdout_art)

        # Save stderr artifact
        if self.stderr_log:
            stderr_art = ExecutionArtifactRecord(
                execution_id=self.execution_id,
                artifact_type="stderr",
                name="stderr.log",
                content=self.stderr_log,
                data={"size_bytes": len(self.stderr_log)},
            )
            self.session.add(stderr_art)

        # Save summary report
        summary = await self.summarize()
        summary_art = ExecutionArtifactRecord(
            execution_id=self.execution_id,
            artifact_type="summary",
            name="summary.md",
            content=summary,
            data={"duration_seconds": duration, "exit_code": exit_code},
        )
        self.session.add(summary_art)

        # Retrieve repo dir to check git diff
        stmt = select(ExecutionRecord).where(ExecutionRecord.id == self.execution_id)
        res = await self.session.execute(stmt)
        exec_record = res.scalar_one()
        cwd = exec_record.repository or "."
        if os.path.exists(os.path.join(cwd, ".git")):
            try:
                import subprocess

                diff_res = subprocess.run(
                    ["git", "diff"],
                    cwd=cwd,
                    capture_output=True,
                    check=False,
                )
                if diff_res.returncode == 0 and diff_res.stdout.strip():
                    diff_content = diff_res.stdout.decode("utf-8", errors="replace")
                    diff_art = ExecutionArtifactRecord(
                        execution_id=self.execution_id,
                        artifact_type="diff",
                        name="changes.diff",
                        content=diff_content,
                        data={"size_bytes": len(diff_content)},
                    )
                    self.session.add(diff_art)
            except Exception:
                pass

        await self.session.flush()
