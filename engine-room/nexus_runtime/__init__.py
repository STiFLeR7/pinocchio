"""``nexus_runtime`` — Phase 8A Runtime Core for Nexus v2.

The Runtime Manager *prepares*; it never executes. Given the ``nexus_core``-projected
inputs of a batch of Execution Packages (:class:`RuntimeIntake`), it discovers runtimes
through the ``RUNTIME``-category Registry view, matches capabilities, filters health,
applies declarative policy, **allocates** exactly one runtime deterministically, and
creates a **Runtime Session** bound to it — driving the session to ``Ready``, the handoff
artifact for the Execution Engine::

    … → Harness → Execution Package → Runtime Manager → Runtime Session → Execution Engine

It never invokes a provider, launches a process, runs a Work Package, streams output,
validates an outcome, or performs recovery (doc 00 §5). The Runtime Manager is the
permanent preparation boundary between compilation and execution.

Determinism is a hard requirement: given identical intakes and an identical Registry
snapshot, RM always produces identical Runtime Sessions, Allocations, and event streams.
There is no AI and no randomness; identifiers are pure functions of the Execution Package
identity and the attempt ordinal (no timestamps in identifiers).

Dependency direction is one-way and strict: ``nexus_runtime → {nexus_core, nexus_infra}``
(doc 00 §4). It never imports ``nexus_planning``, ``nexus_context``,
``nexus_orchestration``, or ``nexus_harness``; it consumes their outputs by value/reference
through the :class:`RuntimeIntake` projection, and reuses the Phase 2 persistence mechanism
without modifying it.
"""

from __future__ import annotations

from nexus_runtime.allocation import (
    Allocation,
    AllocationLedger,
    CandidateMatch,
    RuntimeSelector,
    SelectionResult,
)
from nexus_runtime.composition import RuntimeContext, build_runtime
from nexus_runtime.events import (
    FixedTimestampSource,
    SystemTimestampSource,
    TimestampSource,
)
from nexus_runtime.lifecycle import (
    TERMINAL_STATES,
    IllegalTransitionError,
    is_legal,
    is_terminal,
    legal_transitions,
    project_state,
    validate_transition,
)
from nexus_runtime.observability import RuntimeObservability
from nexus_runtime.persistence import RuntimeRepositories, build_runtime_repositories
from nexus_runtime.requests import PreparationRequest, RuntimeIntake
from nexus_runtime.runtime_manager import PreparationResult, RuntimeManager
from nexus_runtime.runtime_registry import InMemoryHarnessRegistry, RuntimeRegistry
from nexus_runtime.runtime_session import RuntimeSession, RuntimeSessionBuilder
from nexus_runtime.validators import (
    AllocationError,
    CapabilityMismatchError,
    InvalidRuntimeIntakeError,
    NoEligibleRuntimeError,
    RuntimeManagerError,
    UnresolvedRuntimeError,
    validate_intake,
    validate_outputs,
)
from nexus_runtime.vocabulary import RuntimeLifecycleState

__version__ = "2.5.0"

__all__ = [
    "TERMINAL_STATES",
    "Allocation",
    "AllocationError",
    "AllocationLedger",
    "CandidateMatch",
    "CapabilityMismatchError",
    "FixedTimestampSource",
    "IllegalTransitionError",
    "InMemoryHarnessRegistry",
    "InvalidRuntimeIntakeError",
    "NoEligibleRuntimeError",
    "PreparationRequest",
    "PreparationResult",
    "RuntimeContext",
    "RuntimeIntake",
    "RuntimeLifecycleState",
    "RuntimeManager",
    "RuntimeManagerError",
    "RuntimeObservability",
    "RuntimeRegistry",
    "RuntimeRepositories",
    "RuntimeSelector",
    "RuntimeSession",
    "RuntimeSessionBuilder",
    "SelectionResult",
    "SystemTimestampSource",
    "TimestampSource",
    "UnresolvedRuntimeError",
    "build_runtime",
    "build_runtime_repositories",
    "is_legal",
    "is_terminal",
    "legal_transitions",
    "project_state",
    "validate_intake",
    "validate_outputs",
    "validate_transition",
]
