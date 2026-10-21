"""The Constitutional Scheduler (P16/A) — the sole owner of *when* an execution begins.

:class:`Scheduler` owns execution *timing* and nothing else. It registers durable schedules, detects which
occurrences are due at an injected ``now`` (never a wall clock), and dispatches each **once** — a Goal
through the Policy-mediated Autonomous Execution Coordinator (which drives the Constitutional Pipeline), a
platform operation through Scheduled Operations. It records its timing + autonomy provenance as durable
``scheduler.*`` facts and manages the schedule lifecycle (cancel / pause / resume / expire / complete).

It never reasons, plans, executes, validates, recovers, reflects, or evaluates policy — those remain their
owners'. It invokes no engine directly; a Goal reaches the platform only through the Constitutional
Pipeline. Replay reconstructs the scheduling history exactly, and a restart re-detects due occurrences from
the log and skips any already fired — so a resumed Scheduler never double-dispatches (INV-13/14/18).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event
from nexus_infra import InfrastructureContext, content_hash
from nexus_scheduler import events as sevents
from nexus_scheduler.dispatcher import Dispatcher
from nexus_scheduler.model import (
    GOAL_TARGET,
    OPERATION_TARGET,
    AutonomyMode,
    DispatchOutcome,
    Schedule,
    SchedulerHealth,
    ScheduleStatus,
    ScheduleTrigger,
)
from nexus_scheduler.observability import SchedulerObservability
from nexus_scheduler.registry import (
    reconstruct_schedule,
    reconstruct_schedules,
    request_payload_for,
)
from nexus_scheduler.timing import due_occurrences, is_exhausted
from nexus_workflows.spine import SpineRequest, dump_spine_request, load_spine_request


class Scheduler:
    """Owns execution timing: register / tick (due-detection + dispatch) / lifecycle, all over the log."""

    def __init__(
        self,
        dispatcher: Dispatcher,
        infrastructure: InfrastructureContext,
        *,
        now: Callable[[], str] | None = None,
        observability: SchedulerObservability | None = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._infra = infrastructure
        self._now = now or sevents.system_now
        self._obs = observability or SchedulerObservability(infrastructure.observability)

    # -- registration -------------------------------------------------------- #

    def schedule_goal(
        self,
        *,
        identity: str,
        request: SpineRequest,
        trigger: ScheduleTrigger,
        autonomy: AutonomyMode = AutonomyMode.GOVERNED,
        correlation: str = "",
    ) -> Schedule:
        """Register a durable schedule that dispatches a Goal through the pipeline when due."""
        self._register(
            identity,
            trigger,
            autonomy=autonomy,
            target_kind=GOAL_TARGET,
            operation=None,
            request=dump_spine_request(request),
            correlation=correlation or f"cor-{identity}",
        )
        return self._require(identity)

    def schedule_operation(
        self,
        *,
        identity: str,
        operation: str,
        trigger: ScheduleTrigger,
        correlation: str = "",
    ) -> Schedule:
        """Register a durable schedule that runs a platform operation (not a Goal) when due."""
        self._register(
            identity,
            trigger,
            autonomy=AutonomyMode.GOVERNED,
            target_kind=OPERATION_TARGET,
            operation=operation,
            request=None,
            correlation=correlation or f"cor-{identity}",
        )
        return self._require(identity)

    # -- lifecycle ----------------------------------------------------------- #

    def cancel(self, identity: str) -> Schedule:
        """Cancel a schedule — it never fires again."""
        return self._transition(identity, sevents.SCHEDULER_CANCELLED)

    def pause(self, identity: str) -> Schedule:
        """Pause a schedule — it stops firing until resumed (no occurrences are lost)."""
        return self._transition(identity, sevents.SCHEDULER_PAUSED)

    def resume(self, identity: str) -> Schedule:
        """Resume a paused schedule — a subsequent tick fires any occurrences that came due while paused."""
        return self._transition(identity, sevents.SCHEDULER_RESUMED)

    def expire(self, identity: str) -> Schedule:
        """Expire a schedule — a terminal, deadline-driven end (it never fires again)."""
        return self._transition(identity, sevents.SCHEDULER_EXPIRED)

    # -- the tick (due detection + dispatch) --------------------------------- #

    def tick(self, now: str) -> tuple[DispatchOutcome, ...]:
        """Detect and dispatch every due, not-yet-fired occurrence at ``now`` (deterministic, no dupes)."""
        outcomes: list[DispatchOutcome] = []
        for schedule in reconstruct_schedules(self._history()):
            if not schedule.is_active:
                continue
            fired = set(schedule.dispatched)
            newly_fired = 0
            for index, occurrence_at in due_occurrences(schedule.trigger, now):
                if index in fired:
                    continue  # already dispatched (idempotent across restart — INV-18)
                outcomes.append(self._dispatch(schedule, index, occurrence_at, now))
                newly_fired += 1
            self._maybe_complete(schedule, newly_fired, now)
        return tuple(outcomes)

    def _dispatch(
        self, schedule: Schedule, index: int, occurrence_at: str, now: str
    ) -> DispatchOutcome:
        if schedule.target_kind == OPERATION_TARGET and schedule.operation is not None:
            outcome = self._dispatcher.dispatch_operation(
                schedule.operation,
                occurrence=index,
                occurrence_at=occurrence_at,
                schedule_id=schedule.identity,
            )
            self._record(schedule.identity, sevents.SCHEDULER_OPERATION_RAN, outcome, now)
            self._obs.operation_ran()
            return outcome

        payload = request_payload_for(self._history(), schedule.identity)
        assert payload is not None, "a goal schedule must carry a persisted request"
        request = load_spine_request(payload)
        request = replace(
            request,
            identity=f"{schedule.identity}-{index}",
            correlation_identifier=schedule.correlation_identifier or f"cor-{schedule.identity}",
        )
        outcome = self._dispatcher.dispatch_goal(
            request,
            autonomy=schedule.autonomy,
            occurrence=index,
            occurrence_at=occurrence_at,
            correlation=request.correlation_identifier,
            schedule_id=schedule.identity,
        )
        self._record(
            schedule.identity, self._dispatch_type(outcome, schedule.autonomy), outcome, now
        )
        return outcome

    @staticmethod
    def _dispatch_type(outcome: DispatchOutcome, autonomy: AutonomyMode) -> str:
        if outcome.executed:
            return sevents.SCHEDULER_DISPATCHED
        if autonomy is AutonomyMode.MANUAL:
            return sevents.SCHEDULER_DISPATCH_REQUESTED
        return sevents.SCHEDULER_DISPATCH_DENIED

    def _maybe_complete(self, schedule: Schedule, newly_fired: int, now: str) -> None:
        """Complete ``schedule`` if this tick exhausted it — reuses the caller's already-reconstructed
        schedule and the occurrences it just fired, rather than re-fetching and re-reconstructing the
        entire schedule set a second time per schedule (the O(n^2) cost `tick()` used to pay)."""
        total_dispatched = len(schedule.dispatched) + newly_fired
        if is_exhausted(schedule.trigger, now, total_dispatched):
            self._transition(schedule.identity, sevents.SCHEDULER_COMPLETED)

    # -- read-only projections (the log is truth) ---------------------------- #

    def schedules(self) -> tuple[Schedule, ...]:
        """Every registered schedule, in registration order."""
        return reconstruct_schedules(self._history())

    def schedule(self, identity: str) -> Schedule | None:
        """One schedule, or ``None`` if never registered."""
        return reconstruct_schedule(self._history(), identity)

    def active(self) -> tuple[Schedule, ...]:
        """Schedules currently eligible to fire."""
        return tuple(s for s in self.schedules() if s.status is ScheduleStatus.ACTIVE)

    def paused(self) -> tuple[Schedule, ...]:
        """Schedules currently paused."""
        return tuple(s for s in self.schedules() if s.status is ScheduleStatus.PAUSED)

    def completed(self) -> tuple[Schedule, ...]:
        """Schedules that have fired every occurrence."""
        return tuple(s for s in self.schedules() if s.status is ScheduleStatus.COMPLETED)

    def upcoming(self, now: str) -> tuple[Schedule, ...]:
        """Active schedules that still have occurrences to fire at or after ``now``."""
        return tuple(
            s for s in self.active() if not is_exhausted(s.trigger, now, len(s.dispatched))
        )

    def health(self, now: str) -> SchedulerHealth:
        """The read-only scheduler health summary (instrumentation only)."""
        schedules = self.schedules()
        events = self._history()

        def count(status: ScheduleStatus) -> int:
            return sum(1 for s in schedules if s.status is status)

        return SchedulerHealth(
            active=count(ScheduleStatus.ACTIVE),
            paused=count(ScheduleStatus.PAUSED),
            completed=count(ScheduleStatus.COMPLETED),
            cancelled=count(ScheduleStatus.CANCELLED),
            expired=count(ScheduleStatus.EXPIRED),
            dispatched_total=sum(1 for e in events if e.type == sevents.SCHEDULER_DISPATCHED),
            denied_total=sum(1 for e in events if e.type == sevents.SCHEDULER_DISPATCH_DENIED),
            upcoming=tuple(s.identity for s in self.upcoming(now)),
        )

    # -- internals ----------------------------------------------------------- #

    def _register(
        self,
        identity: str,
        trigger: ScheduleTrigger,
        *,
        autonomy: AutonomyMode,
        target_kind: str,
        operation: str | None,
        request: Struct | None,
        correlation: str,
    ) -> None:
        anchor = trigger.anchor or self._now()
        payload: Struct = {
            "session": identity,
            "schedule_id": identity,
            "kind": trigger.kind.value,
            "autonomy": autonomy.value,
            "target_kind": target_kind,
            "operation": operation,
            "anchor": anchor,
            "run_at": trigger.run_at,
            "delay_seconds": trigger.delay_seconds,
            "interval_seconds": trigger.interval_seconds,
            "cron": trigger.cron,
            "max_occurrences": trigger.max_occurrences,
            "expires_at": trigger.expires_at,
            "request": request,
            "correlation": correlation,
        }
        self._emit(
            identity, "registered", sevents.SCHEDULER_REGISTERED, payload, discriminator="reg"
        )
        self._obs.registered()

    def _transition(self, identity: str, event_type: str) -> Schedule:
        suffix = event_type.split(".")[-1]
        seq = sum(
            1
            for event in self._history()
            if event.producer == sevents.SCHEDULER_PRODUCER
            and str(event.payload.get("schedule_id", "")) == identity
        )
        self._emit(
            identity,
            suffix,
            event_type,
            {"session": identity, "schedule_id": identity},
            discriminator=str(seq),
        )
        return self._require(identity)

    def _record(self, identity: str, event_type: str, outcome: DispatchOutcome, now: str) -> None:
        suffix = event_type.split(".")[-1]
        payload: Struct = {
            "session": identity,
            "schedule_id": identity,
            "occurrence": outcome.occurrence,
            "occurrence_at": outcome.occurrence_at,
            "autonomy": outcome.autonomy.value,
            "executed": outcome.executed,
            "policy_allowed": outcome.policy_allowed,
            "policy_decision": outcome.policy_decision,
            "reasoning": list(outcome.reasoning),
            "pipeline_status": outcome.pipeline_status,
            "session_id": outcome.session_id,
            "auto_granted": list(outcome.auto_granted),
            "operation": outcome.operation,
            "note": outcome.note,
            "dispatched_at": now,
        }
        self._emit(identity, suffix, event_type, payload, discriminator=str(outcome.occurrence))
        if event_type == sevents.SCHEDULER_DISPATCHED:
            self._obs.dispatched()
        elif event_type == sevents.SCHEDULER_DISPATCH_DENIED:
            self._obs.denied()
        elif event_type == sevents.SCHEDULER_DISPATCH_REQUESTED:
            self._obs.requested()

    def _require(self, identity: str) -> Schedule:
        schedule = reconstruct_schedule(self._history(), identity)
        assert schedule is not None, f"schedule {identity!r} is not on the log"
        return schedule

    def _history(self) -> tuple[Event, ...]:
        return tuple(self._infra.event_store.read_all())

    def _emit(
        self, identity: str, suffix: str, event_type: str, payload: Struct, *, discriminator: str
    ) -> None:
        correlation = str(payload.get("correlation") or f"cor-{identity}")
        identifier = f"evt-{identity}-{suffix}-{discriminator}-{content_hash(payload)[:12]}"
        self._infra.emit(
            sevents.build_event(identifier, event_type, correlation, payload, self._now())
        )
