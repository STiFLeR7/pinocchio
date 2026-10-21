"""The Execution Engine — drives a Ready Runtime Session to a terminal, destroyed state.

Milestone 3 of the Runtime vertical slice: the *minimal* engine that PERFORMS what RM
prepared (doc 00 §1/§8 — "RM prepares; the engine performs"). Given a ``Ready`` session and
a :class:`~nexus_execution.adapter.RuntimeAdapter`, it:

* **starts** the runtime (``Ready → Running``, ``runtime.started``);
* **consumes** the adapter's ordered signals, recording each as a canonical ``runtime.*``
  event — output (doc 08), progress (doc 12), artifacts by reference (doc 13);
* **honors** cooperative cancellation (doc 09) and a deterministic timeout bound (doc 10);
* **maps** failures onto the doc-11 error model and records ``{error_class, owner, detail}``;
* **finalizes** the terminal execution state (``Completed`` / ``Cancelled`` / ``Failed``);
* runs adapter **cleanup** and reaches ``Destroyed`` (doc 07 §6, ``runtime.destroyed``);
* returns an immutable :class:`ExecutionResult`.

It does exactly this and no more (Milestone-3 constraints): no scheduling, no retries, no
recovery, no validation. It is **generic** — it imports no provider and branches on none;
the only object that knows a provider exists is the injected adapter. Event ids reuse RM's
deterministic ``ids.event_id(scope, kind, sequence)`` scheme, so a run replays identically
against a :class:`~nexus_runtime.events.FixedTimestampSource` (the deterministic-stream
guarantee the program requires).
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, Struct
from nexus_core.domain.work_package import WorkPackage
from nexus_core.events.interfaces import EventEmitter
from nexus_execution.adapter import ExecutionControl, RuntimeAdapter
from nexus_execution.errors import (
    ExecutionError,
    ExecutionStartupError,
    ProviderError,
    RuntimeTimeoutError,
)
from nexus_execution.observability import ExecutionObservability
from nexus_execution.results import ExecutionResult
from nexus_execution.signals import (
    ArtifactSignal,
    OutputSignal,
    ProgressSignal,
    RuntimeSignal,
    StreamChannel,
    TerminalOutcome,
    TerminalSignal,
)
from nexus_runtime import events, ids
from nexus_runtime.events import SystemTimestampSource, TimestampSource
from nexus_runtime.runtime_session import RuntimeSession
from nexus_runtime.vocabulary import RuntimeLifecycleState

_ARTIFACT_TARGET_TYPE = "artifact"


class ExecutionEngine:
    """Drives one Ready session through the adapter to a terminal, destroyed state."""

    def __init__(
        self,
        emitter: EventEmitter,
        *,
        observability: ExecutionObservability | None = None,
        timestamps: TimestampSource | None = None,
    ) -> None:
        self._emitter = emitter
        self._obs = observability or ExecutionObservability()
        self._timestamps = timestamps or SystemTimestampSource()

    # -- public entry point -------------------------------------------------- #

    def execute(
        self,
        session: RuntimeSession,
        adapter: RuntimeAdapter,
        work_package: WorkPackage,
        *,
        control: ExecutionControl | None = None,
    ) -> ExecutionResult:
        """Perform the Work Package inside ``session`` via ``adapter``; return the outcome."""
        control = control or ExecutionControl()
        if session.lifecycle_state is not RuntimeLifecycleState.READY:
            raise ExecutionStartupError(
                f"session {session.identity} is not Ready (is {session.lifecycle_state.value})"
            )

        scope = session.identity
        correlation = session.correlation.correlation_identifier
        runtime_ref = session.runtime_ref
        emitted: list[str] = []
        seq = 0

        # C — start: Ready → Running
        session = session.transitioned_to(RuntimeLifecycleState.RUNNING)
        seq = self._emit(
            emitted,
            scope,
            events.RUNTIME_STARTED,
            "started",
            seq,
            correlation,
            {
                "runtime": runtime_ref.identifier if runtime_ref else None,
                "work_package": work_package.identifier,
            },
        )
        self._obs.started()

        run = _RunState()
        try:
            seq = self._drive(
                adapter, session, work_package, control, run, emitted, scope, correlation, seq
            )
        except ExecutionError as exc:
            run.terminal = TerminalSignal(
                TerminalOutcome.FAILED, detail=exc.detail, error_class=exc.error_class
            )
            run.error = exc
        except Exception as exc:
            provider_fault = ProviderError(f"adapter raised {type(exc).__name__}: {exc}")
            run.terminal = TerminalSignal(
                TerminalOutcome.FAILED,
                detail=provider_fault.detail,
                error_class=provider_fault.error_class,
            )
            run.error = provider_fault

        terminal = run.terminal or self._default_terminal(control)

        # F — synthesize a captured-output artifact (evidence by reference, doc 13)
        capture_ref = self._capture_artifact(run, scope)
        if capture_ref is not None:
            run.artifact_refs.append(capture_ref)
            seq = self._emit(
                emitted,
                scope,
                events.RUNTIME_ARTIFACT_EMITTED,
                "artifact",
                seq,
                correlation,
                {"artifact": capture_ref.identifier, "kind": "captured_output"},
            )
            self._obs.artifact()

        # H — finalize terminal execution state
        session, seq = self._finalize(session, terminal, run, emitted, scope, correlation, seq)

        # I — cleanup + teardown to Destroyed
        session, seq, cleanup_ok = self._teardown(
            session, adapter, terminal, emitted, scope, correlation, seq
        )

        return self._result(session, work_package, runtime_ref, terminal, run, emitted, cleanup_ok)

    # -- the signal loop (D/E/F + G/timeout) --------------------------------- #

    def _drive(
        self,
        adapter: RuntimeAdapter,
        session: RuntimeSession,
        work_package: WorkPackage,
        control: ExecutionControl,
        run: _RunState,
        emitted: list[str],
        scope: str,
        correlation: str,
        seq: int,
    ) -> int:
        for consumed, signal in enumerate(
            adapter.execute(
                session_ref=session.reference(), work_package=work_package, control=control
            ),
            start=1,
        ):
            if control.deadline_steps is not None and consumed > control.deadline_steps:
                seq = self._emit(
                    emitted,
                    scope,
                    events.RUNTIME_TIMED_OUT,
                    "timed_out",
                    seq,
                    correlation,
                    {"consumed": consumed, "deadline": control.deadline_steps},
                )
                self._obs.timed_out()
                timeout = RuntimeTimeoutError(
                    f"exceeded deadline of {control.deadline_steps} signals"
                )
                run.terminal = TerminalSignal(
                    TerminalOutcome.FAILED, detail=timeout.detail, error_class=timeout.error_class
                )
                run.error = timeout
                return seq

            seq = self._record(signal, run, emitted, scope, correlation, seq)
            if isinstance(signal, TerminalSignal):
                run.terminal = signal
                return seq

            if control.cancelled:
                run.terminal = TerminalSignal(
                    TerminalOutcome.CANCELLED, detail="engine-enforced cancellation"
                )
                return seq
        return seq

    def _record(
        self,
        signal: RuntimeSignal,
        run: _RunState,
        emitted: list[str],
        scope: str,
        correlation: str,
        seq: int,
    ) -> int:
        if isinstance(signal, OutputSignal):
            run.capture(signal)
            return self._emit(
                emitted,
                scope,
                events.RUNTIME_OUTPUT,
                "output",
                seq,
                correlation,
                {
                    "channel": signal.channel.value,
                    "sequence": run.output_count,
                    "length": len(signal.text),
                },
            )
        if isinstance(signal, ProgressSignal):
            self._obs.progress()
            return self._emit(
                emitted,
                scope,
                events.RUNTIME_PROGRESS,
                "progress",
                seq,
                correlation,
                {
                    "phase": signal.phase,
                    "fraction": "unknown" if signal.fraction is None else signal.fraction,
                    "milestone": signal.milestone,
                },
            )
        if isinstance(signal, ArtifactSignal):
            run.artifact_refs.append(signal.artifact_ref)
            self._obs.artifact()
            return self._emit(
                emitted,
                scope,
                events.RUNTIME_ARTIFACT_EMITTED,
                "artifact",
                seq,
                correlation,
                {"artifact": signal.artifact_ref.identifier, "kind": signal.kind},
            )
        # TerminalSignal carries no incremental event; it drives the finalize step.
        return seq

    # -- finalize + teardown ------------------------------------------------- #

    def _finalize(
        self,
        session: RuntimeSession,
        terminal: TerminalSignal,
        run: _RunState,
        emitted: list[str],
        scope: str,
        correlation: str,
        seq: int,
    ) -> tuple[RuntimeSession, int]:
        if terminal.outcome is TerminalOutcome.COMPLETED:
            session = session.transitioned_to(RuntimeLifecycleState.COMPLETED)
            seq = self._emit(
                emitted,
                scope,
                events.RUNTIME_COMPLETED,
                "completed",
                seq,
                correlation,
                {
                    "exit_status": terminal.exit_status,
                    "artifacts": [r.identifier for r in run.artifact_refs],
                },
            )
            self._obs.completed()
        elif terminal.outcome is TerminalOutcome.CANCELLED:
            session = session.transitioned_to(RuntimeLifecycleState.CANCELLED)
            seq = self._emit(
                emitted,
                scope,
                events.RUNTIME_CANCELLED,
                "cancelled",
                seq,
                correlation,
                {"mode": "forced", "reason": terminal.detail},
            )
            self._obs.cancelled()
        else:
            session = session.transitioned_to(RuntimeLifecycleState.FAILED)
            owner = run.error.owner if run.error else "runtime"
            seq = self._emit(
                emitted,
                scope,
                events.RUNTIME_FAILED,
                "failed",
                seq,
                correlation,
                {"error_class": terminal.error_class, "owner": owner, "detail": terminal.detail},
            )
            self._obs.failed()
        return session, seq

    def _teardown(
        self,
        session: RuntimeSession,
        adapter: RuntimeAdapter,
        terminal: TerminalSignal,
        emitted: list[str],
        scope: str,
        correlation: str,
        seq: int,
    ) -> tuple[RuntimeSession, int, bool]:
        try:
            report = adapter.cleanup()
            cleanup_ok = report.ok
            cleanup_detail = report.detail
        except Exception as exc:
            cleanup_ok = False
            cleanup_detail = f"cleanup raised {type(exc).__name__}: {exc}"

        session = session.transitioned_to(RuntimeLifecycleState.DESTROYED)
        seq = self._emit(
            emitted,
            scope,
            events.RUNTIME_DESTROYED,
            "destroyed",
            seq,
            correlation,
            {
                "outcome": terminal.outcome.value,
                "cleanup_ok": cleanup_ok,
                "cleanup_detail": cleanup_detail,
            },
        )
        self._obs.destroyed()
        return session, seq, cleanup_ok

    # -- helpers ------------------------------------------------------------- #

    def _default_terminal(self, control: ExecutionControl) -> TerminalSignal:
        """A stream that ended without a terminal: cancelled if requested, else completed."""
        if control.cancelled:
            return TerminalSignal(TerminalOutcome.CANCELLED, detail="stream ended after cancel")
        return TerminalSignal(TerminalOutcome.COMPLETED)

    def _capture_artifact(self, run: _RunState, scope: str) -> Reference | None:
        if not run.stdout_parts and not run.stderr_parts:
            return None
        return Reference(target_type=_ARTIFACT_TARGET_TYPE, identifier=f"{scope}-captured-output")

    def _result(
        self,
        session: RuntimeSession,
        work_package: WorkPackage,
        runtime_ref: Reference | None,
        terminal: TerminalSignal,
        run: _RunState,
        emitted: list[str],
        cleanup_ok: bool,
    ) -> ExecutionResult:
        error_owner = run.error.owner if run.error else None
        return ExecutionResult(
            session_ref=session.reference(),
            work_package_ref=session.work_package_ref,
            runtime_ref=runtime_ref,
            outcome=terminal.outcome,
            final_state=session.lifecycle_state,
            exit_status=terminal.exit_status,
            artifact_refs=tuple(run.artifact_refs),
            event_ids=tuple(emitted),
            cleanup_ok=cleanup_ok,
            error_class=terminal.error_class,
            error_owner=error_owner,
            error_detail=terminal.detail,
            stdout="".join(run.stdout_parts),
            stderr="".join(run.stderr_parts),
            structured=tuple(run.structured_parts),
            metrics={
                "output_chunks": run.output_count,
                "artifact_count": len(run.artifact_refs),
                "event_count": len(emitted),
            },
        )

    def _emit(
        self,
        emitted: list[str],
        scope: str,
        event_type: str,
        kind: str,
        seq: int,
        correlation: str,
        payload: Struct,
    ) -> int:
        identifier = ids.event_id(scope, kind, seq)
        self._emitter.emit(
            events.build_event(identifier, event_type, correlation, payload, self._timestamps.now())
        )
        emitted.append(identifier)
        return seq + 1


class _RunState:
    """Mutable per-run accumulators (captured output, artifact refs, terminal, error)."""

    def __init__(self) -> None:
        self.stdout_parts: list[str] = []
        self.stderr_parts: list[str] = []
        self.structured_parts: list[str] = []
        self.artifact_refs: list[Reference] = []
        self.output_count = 0
        self.terminal: TerminalSignal | None = None
        self.error: ExecutionError | None = None

    def capture(self, signal: OutputSignal) -> None:
        self.output_count += 1
        if signal.channel is StreamChannel.STDOUT:
            self.stdout_parts.append(signal.text)
        elif signal.channel is StreamChannel.STDERR:
            self.stderr_parts.append(signal.text)
        else:
            self.structured_parts.append(signal.text)
