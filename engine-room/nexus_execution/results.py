"""Execution result — the immutable outcome the engine returns after driving one session.

An :class:`ExecutionResult` is the engine→caller handoff, mirroring how RM returns a
``PreparationResult``. It reports *what happened to the process* (outcome + final lifecycle
state, INV-20 — never a validation verdict), the Evidence-Candidate artifacts **by
reference** (INV-12, ADR-003), the ids of the ``runtime.*`` events the run emitted (so the
E2E can capture every event/transition), and — for the caller's convenience only, never as
an event payload — the captured stdout/stderr the Execution Bridge collected.

The result is a Runtime *output* value object (like the Runtime Session), so it is defined
here rather than in a frozen core contract (doc 02 §1 pattern).
"""

from __future__ import annotations

from pydantic import Field

from nexus_core.contracts.base import Reference, Struct, ValueObject
from nexus_execution.signals import TerminalOutcome
from nexus_runtime.vocabulary import RuntimeLifecycleState


class ExecutionResult(ValueObject):
    """The immutable outcome of driving one Ready session to a terminal, destroyed state."""

    session_ref: Reference
    work_package_ref: Reference
    runtime_ref: Reference | None
    outcome: TerminalOutcome
    final_state: RuntimeLifecycleState
    exit_status: int | None = None
    artifact_refs: tuple[Reference, ...] = ()
    event_ids: tuple[str, ...] = ()
    cleanup_ok: bool = True
    error_class: str | None = None
    error_owner: str | None = None
    error_detail: str | None = None
    # Caller-facing capture (never embedded in an event/evidence payload — doc 03 F).
    stdout: str = ""
    stderr: str = ""
    structured: tuple[str, ...] = ()
    metrics: Struct = Field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        """Whether the *process* completed normally (NOT a validation verdict — INV-20)."""
        return self.outcome is TerminalOutcome.COMPLETED
