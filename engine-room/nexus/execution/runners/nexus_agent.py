from __future__ import annotations

import contextlib
import json
import os
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from nexus.core.exceptions import ConfigurationError, ExecutionEngineError
from nexus.core.types import ExecutionStatus, ExitStatus
from nexus.execution.governance import GovernanceManager
from nexus.execution.runners import runtime_registry
from nexus.execution.runners.base import AgentRuntimeAdapter, resolve_execution_timeout
from nexus.execution.runners.nexus_agent_tools import (
    ToolCallParseError,
    extract_json_block,
    parse_tool_call,
)
from nexus.execution.sandbox.confinement import resolve_in_workspace
from nexus.memory.models import (
    AgentStepRecord,
    ExecutionArtifactRecord,
    ExecutionRecord,
    WorkflowCheckpointRecord,
)


@runtime_registry.register("nexus")
class NexusRuntimeAdapter(AgentRuntimeAdapter):
    """Execution adapter for the Nexus autonomous planning and research agent.

    Formerly developed under the internal codename "Hermes"; the registry retains a
    ``hermes`` → ``nexus`` alias so historical ``runner="hermes"`` records still resolve.
    """

    def __init__(
        self,
        db_session: Any,
        execution_id: Any,
        event_gateway: Any = None,
        openrouter_client: Any = None,
        settings: Any = None,
        search_provider: Any = None,
    ) -> None:
        """Initialize the NexusRuntimeAdapter with database and LLM gateway references."""
        self.session = db_session
        self.execution_id = execution_id
        self.event_gateway = event_gateway
        self.openrouter_client = openrouter_client
        self.settings = settings
        self.search_provider = search_provider
        self.trajectory: list[dict[str, Any]] = []
        self.plan: list[dict[str, Any]] = []
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.exit_code: int = 0
        self.status: str = ""
        # Cooperative cancellation (H-4): set by terminate(), observed at loop boundaries.
        self._cancel_requested: bool = False
        self._active_process: Any = None

    async def initialize(self) -> None:
        """Verify the runtime can run before execution — fail-fast on an unusable configuration.

        The Nexus agent requires an LLM capability: either an injected client or a usable API key (env or
        settings). If neither is present the run cannot make real decisions, so initialization
        **fails closed** rather than proceeding into a guaranteed failure (H-4 / Cap 17).
        """
        if self.openrouter_client is not None:
            return

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key and self.settings and self.settings.openrouter:
            api_key = self.settings.openrouter.api_key

        if not api_key:
            raise ConfigurationError(
                "Nexus agent initialization failed: no LLM client and no usable API key "
                "(GEMINI_API_KEY or settings.openrouter.api_key). Refusing to start "
                "(fail-closed)."
            )

    async def validate_goal(self, goal: str) -> None:
        """Run repository safety and task approval checks using GovernanceManager."""
        stmt = select(ExecutionRecord).where(ExecutionRecord.id == self.execution_id)
        res = await self.session.execute(stmt)
        exec_record = res.scalar_one_or_none()
        if not exec_record:
            raise ExecutionEngineError(f"Execution record {self.execution_id} not found.")

        gov = GovernanceManager(self.session)
        cwd = exec_record.repository or "."
        await gov.validate_execution(
            task_id=exec_record.task_id,
            working_dir=cwd,
            command=goal,
            runtime="nexus",
        )

    async def _workspace_cwd(self) -> str:
        """Return the execution's approved workspace directory (repository) for confinement (R-05)."""
        stmt = select(ExecutionRecord).where(ExecutionRecord.id == self.execution_id)
        res = await self.session.execute(stmt)
        exec_record = res.scalar_one_or_none()
        return exec_record.repository if exec_record and exec_record.repository else "."

    async def _execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute local or external tools and return string outcomes."""
        if name == "web_search":
            query = arguments.get("query", "")
            if self.search_provider is None:
                # Honest failure: no canned results when no provider is configured.
                return (
                    f"Error: no search provider is configured; cannot search for '{query}'."
                )
            try:
                return str(await self.search_provider.search(query))
            except Exception as e:
                return f"Error performing search: {e!s}"

        elif name == "read_file":
            path = arguments.get("path", "")
            try:
                # R-05: confine file access to the approved workspace (fail-closed on escape).
                resolved = resolve_in_workspace(await self._workspace_cwd(), path)
                with open(resolved, encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"Error reading file: {e!s}"

        elif name == "write_file":
            path = arguments.get("path", "")
            content = arguments.get("content", "")
            try:
                # R-05: confine file access to the approved workspace (fail-closed on escape).
                resolved = resolve_in_workspace(await self._workspace_cwd(), path)
                os.makedirs(os.path.dirname(str(resolved)), exist_ok=True)
                with open(resolved, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"File written successfully to {path}"
            except Exception as e:
                return f"Error writing file: {e!s}"

        elif name == "execute_command":
            cmd = arguments.get("command", "")
            try:
                # Resolve repository path
                stmt = select(ExecutionRecord).where(ExecutionRecord.id == self.execution_id)
                res = await self.session.execute(stmt)
                exec_record = res.scalar_one()
                cwd = exec_record.repository or "."

                from nexus.execution.sandbox.manager import SandboxManager
                sandbox_mgr = SandboxManager(self.session, self.settings)
                # Resolve the ADR-010 research/agent timeout, clamped by hard_limit (A-002)
                timeout = resolve_execution_timeout(self.settings, "research_timeout")
                proc = await sandbox_mgr.execute(
                    command=cmd,
                    cwd=cwd,
                    timeout=timeout,
                    correlation_id=self.execution_id,
                )
                # Track the in-flight process so terminate() can kill it (H-4).
                self._active_process = proc
                try:
                    stdout, stderr = await proc.communicate()
                finally:
                    self._active_process = None
                out = stdout.decode("utf-8", errors="replace")
                err = stderr.decode("utf-8", errors="replace")
                return f"Exit Code: {proc.returncode}\nSTDOUT:\n{out}\nSTDERR:\n{err}"
            except Exception as e:
                return f"Error executing command: {e!s}"

        else:
            return f"Unknown tool: '{name}'"

    async def _generate_plan(self, goal: str) -> list[dict[str, Any]]:
        """Derive an advisory plan from the goal (no decorative literal).

        Uses the model when available; otherwise falls back to a minimal goal-derived plan. Either
        way the plan is generated from the goal, never a fixed script.
        """
        fallback = [{"step": 1, "description": f"Work toward goal: {goal}"}]
        if not self.openrouter_client:
            return fallback
        prompt = (
            f"Goal: {goal}\n\n"
            "Produce a short ordered plan to achieve the goal as a JSON array of step "
            "description strings. Return only the JSON array."
        )
        try:
            completion = await self.openrouter_client.complete(prompt)
            data = json.loads(extract_json_block(completion))
            if not isinstance(data, list) or not data:
                return fallback
            plan: list[dict[str, Any]] = []
            for i, step in enumerate(data, start=1):
                if isinstance(step, dict):
                    plan.append(
                        {
                            "step": step.get("step", i),
                            "description": str(step.get("description", step)),
                        }
                    )
                else:
                    plan.append({"step": i, "description": str(step)})
            return plan
        except Exception:
            return fallback

    def _max_steps(self) -> int:
        """Resolve the operator-configurable step budget, defaulting to 5 (H-4 / Cap 19)."""
        raw = getattr(getattr(self.settings, "execution", None), "agent_max_steps", None)
        if isinstance(raw, int) and raw > 0:
            return raw
        return 5

    async def execute_goal(self, goal: str) -> dict[str, Any]:
        """Run the autonomous tool loop to achieve the specified goal.

        Decisions come from a real model completion parsed as a structured tool-call; the outcome
        (``exit_code``/``status``) reflects whether the run genuinely completed, failed, or did not
        finish within budget. There is no mock branch and no always-zero exit.
        """
        self.start_time = time.time()
        self.trajectory = []

        # Goal-derived advisory plan (replaces the decorative literal).
        self.plan = await self._generate_plan(goal)

        return await self._run_loop(goal, 0)

    async def _run_loop(self, goal: str, step_index: int) -> dict[str, Any]:
        """Drive the decision/tool loop from ``step_index`` to a terminal state.

        Shared by ``execute_goal`` (fresh) and ``resume_goal`` (reconstructed). ``self.trajectory``
        and ``self.plan`` must already be set; ``self.start_time`` bounds the wall-clock budget.
        """
        max_steps = self._max_steps()
        # ADR-010 wall-clock budget (clamped by hard_limit via A-002) — a real ceiling.
        timeout_seconds = resolve_execution_timeout(self.settings, "research_timeout")
        finished = False
        failed = False
        cancelled = False
        timed_out = False

        while step_index < max_steps and not finished:
            # Cooperative cancellation observed at the loop boundary (H-4 / Cap 14).
            if await self._is_cancelled():
                await self._record_terminal_marker(
                    step_index,
                    tool_name="cancelled",
                    thought="Cancellation requested.",
                    result="Run cancelled cooperatively (terminate()).",
                    status=ExecutionStatus.CANCELLED.value,
                )
                cancelled = True
                finished = True
                break

            # Wall-clock timeout → distinct TIMED_OUT terminal (H-4 / Cap 18 lifecycle).
            if time.time() - self.start_time > timeout_seconds:
                await self._record_terminal_marker(
                    step_index,
                    tool_name="timed_out",
                    thought="Execution timed out.",
                    result=f"Run exceeded the {timeout_seconds}s execution budget.",
                    status=ExecutionStatus.TIMED_OUT.value,
                )
                timed_out = True
                finished = True
                break

            await self.heartbeat()

            trajectory_str = "\n".join(
                [
                    f"Step {s['step_index']}: Thought: {s['thought']}\n"
                    f"Action: {s['tool_name']}({s['tool_arguments']}) -> {s['tool_result'][:100]}"
                    for s in self.trajectory
                ]
            )

            prompt = (
                f"Goal: {goal}\n\n"
                f"Trajectory History:\n{trajectory_str}\n\n"
                "Determine the next action. Select one of:\n"
                "- web_search(query: str)\n"
                "- read_file(path: str)\n"
                "- write_file(path: str, content: str)\n"
                "- execute_command(command: str)\n"
                "- finish()\n\n"
                "Return JSON with keys: 'thought', 'tool_name', 'tool_arguments'."
            )

            thought = ""
            tool_name = ""
            tool_args: dict[str, Any] = {}
            step_status = ExecutionStatus.COMPLETED.value

            try:
                completion = await self.openrouter_client.complete(prompt)
                call = parse_tool_call(completion)
                thought = call.thought
                tool_name = call.tool_name
                tool_args = call.tool_arguments

                if tool_name == "finish":
                    finished = True
                    tool_result = "Agent completed execution."
                else:
                    tool_result = await self._execute_tool(tool_name, tool_args)
            except ToolCallParseError as e:
                # A malformed/unrecognized tool call is an explicit failure — never a silent finish.
                thought = "Malformed tool call."
                tool_name = "error"
                tool_args = {}
                tool_result = f"Tool-call parse error: {e!s}"
                step_status = ExecutionStatus.FAILED.value
                failed = True
                finished = True
            except Exception as e:
                thought = "Execution loop error."
                tool_name = "error"
                tool_args = {}
                tool_result = f"Error: {e!s}"
                step_status = ExecutionStatus.FAILED.value
                failed = True
                finished = True

            # Save AgentStepRecord to SQLite DB
            step_record = AgentStepRecord(
                execution_id=self.execution_id,
                step_index=step_index,
                thought=thought,
                tool_name=tool_name,
                tool_arguments=tool_args,
                tool_result=tool_result,
                status=step_status,
                last_heartbeat=datetime.now(UTC),
            )
            self.session.add(step_record)
            await self.session.flush()

            # Append to internal memory trajectory
            step_data = {
                "step_index": step_index,
                "thought": thought,
                "tool_name": tool_name,
                "tool_arguments": tool_args,
                "tool_result": tool_result,
            }
            self.trajectory.append(step_data)

            # Checkpoint intermediate state
            await self.checkpoint(
                step_name=f"agent_step_{step_index}",
                state={"step": step_data, "plan": self.plan},
            )

            step_index += 1

        # A run that exhausts its step budget without a genuine finish is a TIMED_OUT, not a failure.
        if not finished:
            await self._record_terminal_marker(
                step_index,
                tool_name="timed_out",
                thought="Step budget exhausted.",
                result=f"Run exhausted its step budget ({max_steps} steps) without finishing.",
                status=ExecutionStatus.TIMED_OUT.value,
            )
            timed_out = True

        if cancelled:
            self.status = "cancelled"
        elif timed_out:
            self.status = "timed_out"
        elif failed:
            self.status = "failed"
        else:
            self.status = "completed"
        self.exit_code = 0 if self.status == "completed" else 1

        self.end_time = time.time()
        duration = self.end_time - self.start_time

        return {
            "exit_code": self.exit_code,
            "status": self.status,
            "duration_seconds": duration,
            "steps_executed": step_index,
            "trajectory_len": len(self.trajectory),
        }

    async def resume_goal(self, goal: str) -> dict[str, Any]:
        """Resume an interrupted run from its persisted state (H-4 / Cap 12).

        Reconstructs the trajectory from ``agent_steps`` and the plan/cursor from the latest
        checkpoint, re-validates the goal through governance (no bypass), then continues the loop.
        Fails closed if there is no prior step state or no usable checkpoint — never silently
        restarts from zero, which would mask data loss.
        """
        steps_stmt = (
            select(AgentStepRecord)
            .where(AgentStepRecord.execution_id == self.execution_id)
            .order_by(AgentStepRecord.step_index)
        )
        steps = (await self.session.execute(steps_stmt)).scalars().all()
        if not steps:
            raise ExecutionEngineError(
                f"Cannot resume execution {self.execution_id}: no prior agent steps "
                "(fail-closed)."
            )

        cp_stmt = (
            select(WorkflowCheckpointRecord)
            .where(WorkflowCheckpointRecord.workflow_id == self.execution_id)
            .order_by(WorkflowCheckpointRecord.completed_at.desc())
        )
        checkpoint = (await self.session.execute(cp_stmt)).scalars().first()
        if checkpoint is None or not isinstance(checkpoint.state, dict):
            raise ExecutionEngineError(
                f"Cannot resume execution {self.execution_id}: no usable checkpoint state "
                "(fail-closed)."
            )

        # Re-validate the goal through governance before continuing (no bypass of Rule 5).
        await self.validate_goal(goal)

        # Reconstruct in-memory state from the persisted record (read-only over existing schema).
        self.plan = checkpoint.state.get("plan") or []
        self.trajectory = [
            {
                "step_index": s.step_index,
                "thought": s.thought,
                "tool_name": s.tool_name,
                "tool_arguments": s.tool_arguments,
                "tool_result": s.tool_result,
            }
            for s in steps
        ]
        cursor = max(s.step_index for s in steps) + 1

        self.start_time = time.time()
        return await self._run_loop(goal, cursor)

    async def heartbeat(self) -> None:
        """Update last_heartbeat timestamps in active database records."""
        now = datetime.now(UTC)
        exec_stmt = select(ExecutionRecord).where(ExecutionRecord.id == self.execution_id)
        exec_res = await self.session.execute(exec_stmt)
        exec_record = exec_res.scalar_one_or_none()
        if exec_record:
            exec_record.last_heartbeat = now
        await self.session.flush()

    async def checkpoint(self, step_name: str, state: dict[str, Any]) -> None:
        """Persist intermediate execution checkpoints to workflow_checkpoints."""
        checkpoint = WorkflowCheckpointRecord(
            workflow_id=self.execution_id,
            step_name=step_name,
            state=state,
            completed_at=datetime.now(UTC),
        )
        self.session.add(checkpoint)
        await self.session.flush()

    async def terminate(self) -> None:
        """Request cooperative cancellation of the run (H-4 / Cap 14).

        Sets the cancel signal observed at loop boundaries and kills any in-flight sandbox process.
        Cancellation is cooperative — the loop transitions to CANCELLED at its next boundary; the
        async task itself is never force-killed.
        """
        self._cancel_requested = True
        proc = self._active_process
        if proc is not None:
            with contextlib.suppress(Exception):
                proc.terminate()

    async def _is_cancelled(self) -> bool:
        """Whether cancellation was requested — in-process (terminate()) or DB-observable (H-4).

        The DB signal (``ExecutionRecord.exit_status == cancelled``) lets an operator or the
        orchestration path request cancellation without holding the adapter instance, consistent
        with the DB-backed approval model.
        """
        if self._cancel_requested:
            return True
        stmt = select(ExecutionRecord).where(ExecutionRecord.id == self.execution_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        return bool(rec is not None and rec.exit_status == ExitStatus.CANCELLED.value)

    async def _record_terminal_marker(
        self, step_index: int, *, tool_name: str, thought: str, result: str, status: str
    ) -> None:
        """Persist a terminal lifecycle marker step (cancelled/timed_out) — audit-observable."""
        step_record = AgentStepRecord(
            execution_id=self.execution_id,
            step_index=step_index,
            thought=thought,
            tool_name=tool_name,
            tool_arguments={},
            tool_result=result,
            status=status,
            last_heartbeat=datetime.now(UTC),
        )
        self.session.add(step_record)
        await self.session.flush()
        self.trajectory.append(
            {
                "step_index": step_index,
                "thought": thought,
                "tool_name": tool_name,
                "tool_arguments": {},
                "tool_result": result,
            }
        )
        await self.checkpoint(
            step_name=f"agent_step_{step_index}_{tool_name}",
            state={"terminal": tool_name, "plan": self.plan},
        )

    async def summarize(self) -> str:
        """Request OpenRouter to summarize reasoning steps trajectory."""
        if not self.openrouter_client:
            return "No summarization service configured."

        traj_summary = "\n".join(
            [
                f"Step {s['step_index']}: Thought: {s['thought']} -> Tool {s['tool_name']}"
                for s in self.trajectory
            ]
        )

        prompt = (
            "Summarize the following agent execution reasoning trajectory into a report:\n"
            f"TRAJECTORY:\n{traj_summary[:2000]}\n"
        )
        try:
            summary = await self.openrouter_client.complete(prompt)
            return str(summary)
        except Exception as e:
            return f"Failed to generate summary report: {e!s}"

    async def persist(self) -> None:
        """Commit structural plans, trajectories, and report summaries as first-class artifacts."""
        duration = self.end_time - self.start_time

        # 1. Save plan artifact
        if self.plan:
            plan_art = ExecutionArtifactRecord(
                execution_id=self.execution_id,
                artifact_type="agent_plan",
                name="plan.json",
                content=json.dumps(self.plan, indent=2),
                data={"steps_count": len(self.plan)},
            )
            self.session.add(plan_art)

        # 2. Save trajectory artifact
        if self.trajectory:
            traj_art = ExecutionArtifactRecord(
                execution_id=self.execution_id,
                artifact_type="agent_trajectory",
                name="trajectory.json",
                content=json.dumps(self.trajectory, indent=2),
                data={"steps_count": len(self.trajectory)},
            )
            self.session.add(traj_art)

        # 3. Save synthesis report brief
        summary = await self.summarize()
        summary_art = ExecutionArtifactRecord(
            execution_id=self.execution_id,
            artifact_type="summary",
            name="summary.md",
            content=summary,
            data={"duration_seconds": duration, "exit_code": self.exit_code},
        )
        self.session.add(summary_art)

        # 4. Fetch git diff changes
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


# Back-compat alias: the runtime was developed under the codename "Hermes" (H-2…H-4).
# Existing imports of ``HermesRuntimeAdapter`` continue to resolve to the renamed class.
HermesRuntimeAdapter = NexusRuntimeAdapter
