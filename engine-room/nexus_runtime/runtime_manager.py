"""The Runtime Manager — prepares runtimes and owns Runtime Sessions (never executes).

Receives a deterministic :class:`PreparationRequest` (the ``nexus_core``-projected intakes
for a batch of Execution Packages) and drives each through the Phase 8A **preparation
pipeline** — create session → resolve candidates → match capabilities → select → allocate
→ configure → ready — persisting Sessions and Allocations through Phase 2 repositories,
emitting ``runtime.*`` events, and returning an immutable :class:`PreparationResult`. It
also accepts runtime **registrations** into the Registry view and **releases** allocations
at teardown.

It prepares only. It never invokes a provider, launches a process, runs a Work Package,
streams output, validates an outcome, or performs recovery (doc 00 §5, doc 01 §3). The
pipeline stops at ``Ready`` — the handoff artifact for the Execution Engine (a later phase).
Preparation is deterministic (doc 01 §5): the same intakes against the same Registry
snapshot yield the same sessions, allocations, and event stream. A failure emits
``runtime.failed``, releases any reservation (capacity is never leaked — doc 07 §6), rolls
back earlier reservations in the batch, and raises.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass

from nexus_core.contracts.base import Struct, ValueObject
from nexus_core.events.interfaces import EventEmitter
from nexus_core.registries.interfaces import HarnessDescriptor
from nexus_infra.errors import DuplicateEventError
from nexus_runtime import events, ids
from nexus_runtime.allocation import Allocation, AllocationLedger, RuntimeSelector, SelectionResult
from nexus_runtime.events import SystemTimestampSource, TimestampSource
from nexus_runtime.observability import RuntimeObservability
from nexus_runtime.persistence import RuntimeRepositories
from nexus_runtime.requests import PreparationRequest, RuntimeIntake
from nexus_runtime.runtime_registry import RuntimeRegistry
from nexus_runtime.runtime_session import RuntimeSession, RuntimeSessionBuilder
from nexus_runtime.validators import RuntimeManagerError, validate_intake, validate_outputs
from nexus_runtime.vocabulary import RuntimeLifecycleState


class PreparationResult(ValueObject):
    """The complete output of a preparation cycle — Ready sessions + their allocations."""

    sessions: tuple[RuntimeSession, ...] = ()
    allocations: tuple[Allocation, ...] = ()


@dataclass(frozen=True, slots=True)
class _Prepared:
    """One successfully prepared (session, allocation) plus its final event sequence."""

    session: RuntimeSession
    allocation: Allocation
    sequence: int


class RuntimeManager:
    """Prepares a batch of intakes into persisted, emitted Runtime Sessions + Allocations."""

    def __init__(
        self,
        registry: RuntimeRegistry,
        repositories: RuntimeRepositories,
        emitter: EventEmitter,
        *,
        observability: RuntimeObservability | None = None,
        timestamps: TimestampSource | None = None,
    ) -> None:
        self._registry = registry
        self._repos = repositories
        self._emitter = emitter
        self._obs = observability or RuntimeObservability()
        self._timestamps = timestamps or SystemTimestampSource()
        self._selector = RuntimeSelector(registry)
        self._session_builder = RuntimeSessionBuilder()
        self._ledger = AllocationLedger()

    # -- registration (doc 04 §3) -------------------------------------------- #

    def register_runtime(self, descriptor: HarnessDescriptor) -> HarnessDescriptor:
        """Register a ``RUNTIME`` descriptor into the Registry view and announce it.

        The announce event's identifier is ``ids.event_id(identity, "registered", 0)`` — a pure
        function of ``identity`` alone, so a collision on it can only mean "this identity was
        already announced" (a fresh ``RuntimeManager``/registry built for a later actuation in
        the same process, or a restart over a reopened durable log — the registry itself is
        in-memory and carries no history across either). Under a real, advancing clock this
        re-announcement is *not* byte-identical (``Event.timestamp`` differs), so the durable
        store correctly raises ``DuplicateEventError`` rather than silently absorbing it — which
        made every second actuation sharing a runtime identity in the same process fail. Caught
        here as the safe no-op it already is: identity determines the payload, so a second
        announcement for the same identity carries the same category/version/capabilities.
        """
        registered = self._registry.register(descriptor)
        correlation = ids.correlation_id(registered.identity)
        with suppress(DuplicateEventError):
            self._emit(
                registered.identity,
                events.RUNTIME_REGISTERED,
                "registered",
                0,
                correlation,
                {
                    "runtime": registered.identity,
                    "category": registered.category.value,
                    "version": registered.version,
                    "capabilities": [c.identifier for c in registered.advertised_capabilities],
                },
            )
        self._obs.registered()
        return registered

    # -- preparation (doc 01 §4) --------------------------------------------- #

    def prepare(self, request: PreparationRequest) -> PreparationResult:
        """Prepare, persist, and announce a batch of Runtime Sessions and Allocations."""
        correlation = self._correlation(request)
        prepared: list[_Prepared] = []
        try:
            for intake in request.intakes:
                prepared.append(self._prepare_one(intake, correlation))
        except RuntimeManagerError:
            self._rollback(prepared, correlation)
            raise
        sessions = tuple(item.session for item in prepared)
        allocations = tuple(item.allocation for item in prepared)
        validate_outputs(len(sessions), len(allocations), len(request.intakes))
        self._persist(sessions, allocations)
        return PreparationResult(sessions=sessions, allocations=allocations)

    def _prepare_one(self, intake: RuntimeIntake, correlation: str) -> _Prepared:
        validate_intake(intake)
        session = self._session_builder.build(intake, correlation_identifier=correlation)
        scope = session.identity
        allocation: Allocation | None = None
        sequence = 0
        try:
            sequence = self._emit(
                scope,
                events.RUNTIME_SESSION_CREATED,
                "created",
                sequence,
                correlation,
                {
                    "node": intake.node,
                    "package": intake.package_identity,
                    "attempt": intake.attempt,
                },
            )
            self._obs.session_created()

            resolved = self._registry.resolve_candidates(intake.candidate_harness_refs)
            sequence = self._emit(
                scope,
                events.RUNTIME_DISCOVERED,
                "discovered",
                sequence,
                correlation,
                {
                    "node": intake.node,
                    "candidates": [r.identifier for r in intake.candidate_harness_refs],
                    "resolved": [d.identity for d in resolved],
                },
            )
            self._obs.discovered(len(resolved))

            excluded = self._ledger.at_capacity_ids(resolved)
            selection = self._selector.select(
                resolved,
                intake.required_capability_refs,
                intake.runtime_policy,
                excluded_ids=excluded,
            )
            chosen_match = selection.chosen_match
            sequence = self._emit(
                scope,
                events.RUNTIME_CAPABILITIES_MATCHED,
                "matched",
                sequence,
                correlation,
                {
                    "node": intake.node,
                    "required": list(selection.required),
                    "satisfied": list(chosen_match.satisfied),
                    "unsupported": list(chosen_match.unsupported),
                    "chosen": selection.chosen.identity,
                },
            )
            session = session.transitioned_to(RuntimeLifecycleState.REGISTERED)

            reservation = self._ledger.reserve(
                session.reference(), selection.chosen, correlation=session.correlation
            )
            allocation = self._ledger.allocate(reservation)
            session = session.bound_to(
                runtime_ref=allocation.runtime_ref, allocation_ref=allocation.reference()
            ).transitioned_to(RuntimeLifecycleState.ALLOCATED)
            sequence = self._emit(
                scope,
                events.RUNTIME_ALLOCATED,
                "allocated",
                sequence,
                correlation,
                {
                    "node": intake.node,
                    "runtime": selection.chosen.identity,
                    "allocation": allocation.identity,
                    "state": allocation.allocation_state.value,
                },
            )
            self._obs.allocated()

            session = session.transitioned_to(RuntimeLifecycleState.PREPARED)
            sequence = self._emit(
                scope,
                events.RUNTIME_PREPARED,
                "prepared",
                sequence,
                correlation,
                {"node": intake.node, "runtime": selection.chosen.identity},
            )

            session = session.transitioned_to(RuntimeLifecycleState.READY)
            sequence = self._emit(
                scope, events.RUNTIME_READY, "ready", sequence, correlation, {"node": intake.node}
            )
            self._obs.session_ready()
        except RuntimeManagerError as exc:
            self._fail(session, allocation, scope, sequence, correlation, exc)
            raise
        return _Prepared(session=session, allocation=allocation, sequence=sequence)

    # -- teardown (doc 07 §6) ------------------------------------------------ #

    def release(
        self, session: RuntimeSession, allocation: Allocation
    ) -> tuple[RuntimeSession, Allocation]:
        """Release an allocation and move its session to ``Released`` (capacity returned)."""
        released_allocation = self._ledger.release(allocation)
        released_session = session.transitioned_to(RuntimeLifecycleState.RELEASED)
        self._emit(
            session.identity,
            events.RUNTIME_RELEASED,
            "released",
            _RELEASE_SEQUENCE,
            session.correlation.correlation_identifier,
            {
                "node": session.node,
                "runtime": released_allocation.runtime_ref.identifier,
                "allocation": released_allocation.identity,
            },
        )
        self._obs.released()
        self._persist((released_session,), (released_allocation,))
        return released_session, released_allocation

    # -- failure & rollback -------------------------------------------------- #

    def _fail(
        self,
        session: RuntimeSession,
        allocation: Allocation | None,
        scope: str,
        sequence: int,
        correlation: str,
        exc: RuntimeManagerError,
    ) -> None:
        failed = session.transitioned_to(RuntimeLifecycleState.FAILED)
        sequence = self._emit(
            scope,
            events.RUNTIME_FAILED,
            "failed",
            sequence,
            correlation,
            {"node": failed.node, "error": str(exc), "reason": type(exc).__name__},
        )
        self._obs.failed()
        if allocation is not None:
            released = self._ledger.release(allocation)
            self._emit(
                scope,
                events.RUNTIME_RELEASED,
                "released",
                sequence,
                correlation,
                {
                    "node": failed.node,
                    "runtime": released.runtime_ref.identifier,
                    "allocation": released.identity,
                },
            )
            self._obs.released()

    def _rollback(self, prepared: list[_Prepared], correlation: str) -> None:
        """Release every already-successful allocation in an aborted batch (no leak)."""
        for item in prepared:
            released_allocation = self._ledger.release(item.allocation)
            self._emit(
                item.session.identity,
                events.RUNTIME_RELEASED,
                "released",
                item.sequence,
                correlation,
                {
                    "node": item.session.node,
                    "runtime": released_allocation.runtime_ref.identifier,
                    "allocation": released_allocation.identity,
                    "rollback": True,
                },
            )
            self._obs.released()

    # -- persistence --------------------------------------------------------- #

    def _persist(
        self, sessions: tuple[RuntimeSession, ...], allocations: tuple[Allocation, ...]
    ) -> None:
        for session in sessions:
            self._repos.sessions.add(session)
        for allocation in allocations:
            self._repos.allocations.add(allocation)

    # -- events -------------------------------------------------------------- #

    def _emit(
        self,
        scope: str,
        event_type: str,
        kind: str,
        sequence: int,
        correlation: str,
        payload: Struct,
    ) -> int:
        # ``sequence_position`` is intentionally left unset: the event store treats it as an
        # optimistic-concurrency *expected stream version*, but the per-session sequence
        # resets per session while a batch shares one correlation stream. The ordered,
        # dedup-keyed sequence already lives in the event id (INV-16); the store manages
        # stream versioning itself (mirrors the Harness emit).
        self._emitter.emit(
            events.build_event(
                ids.event_id(scope, kind, sequence),
                event_type,
                correlation,
                payload,
                self._timestamps.now(),
            )
        )
        return sequence + 1

    # -- derivations --------------------------------------------------------- #

    def _correlation(self, request: PreparationRequest) -> str:
        if request.correlation_identifier is not None:
            return request.correlation_identifier
        if request.intakes:
            first = request.intakes[0]
            if first.correlation is not None:
                return first.correlation.correlation_identifier
            return ids.correlation_id(first.session_ref.identifier)
        return ids.correlation_id("runtime")


# Standalone ``release`` emits the one ``runtime.released`` a session can carry; the kind
# tag already makes the event id unique within the session, so a stable sequence suffices.
_RELEASE_SEQUENCE = 99


__all__ = [
    "PreparationRequest",
    "PreparationResult",
    "RuntimeManager",
    "RuntimeRepositories",
    "SelectionResult",
]
