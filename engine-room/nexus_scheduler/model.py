"""Scheduler value models — schedule kinds, the durable schedule projection, and dispatch outcomes.

The Scheduler owns *when* a Goal (or platform operation) enters the platform, and nothing else. Its durable
facts are the ``scheduler.*`` events; :class:`Schedule` is a ``ValueObject`` projection of that stream
(INV-13/14), never a new frozen domain object (INV-07). :class:`ScheduleTrigger` is the deterministic
timing spec; :class:`AutonomyMode` selects how a due Goal is dispatched (always mediated by Policy);
:class:`DispatchOutcome` / :class:`SchedulerHealth` are read-only formatted projections.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from nexus_core.contracts.base import ValueObject

GOAL_TARGET = "goal"
OPERATION_TARGET = "operation"


class ScheduleKind(StrEnum):
    """The deterministic schedule kinds (all a pure function of injected time)."""

    IMMEDIATE = "immediate"  # one occurrence at registration time
    ONE_TIME = "one_time"  # one occurrence at ``run_at``
    DELAYED = "delayed"  # one occurrence at ``anchor + delay_seconds``
    INTERVAL = "interval"  # recurring at ``anchor + k*interval_seconds``
    CRON = "cron"  # recurring at a cron alias cadence (mapped to an interval)


class ScheduleStatus(StrEnum):
    """The projected lifecycle state of one schedule."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"  # every occurrence dispatched (one-shot or capped recurring)
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AutonomyMode(StrEnum):
    """How a due Goal is dispatched — always mediated by Policy (INV-28)."""

    MANUAL = "manual"  # timing only: record a request a human must run (no autonomous execution)
    GOVERNED = (
        "governed"  # auto-run through the pipeline; approval gates pause for a human decision
    )
    FULLY_AUTOMATIC = (
        "fully_automatic"  # auto-run and auto-approve gates — only when Policy permits
    )


# Cron aliases the CRON kind supports (mapped to a deterministic interval in seconds).
CRON_ALIASES: dict[str, int] = {
    "@minutely": 60,
    "@hourly": 3600,
    "@daily": 86400,
    "@weekly": 604800,
}


@dataclass(frozen=True, slots=True)
class ScheduleTrigger:
    """The deterministic timing spec for a schedule (all times are injected ISO-8601 data)."""

    kind: ScheduleKind
    anchor: str = ""  # first occurrence / reference time; the registration ``now`` when empty
    run_at: str | None = None  # ONE_TIME
    delay_seconds: int | None = None  # DELAYED
    interval_seconds: int | None = None  # INTERVAL
    cron: str | None = None  # CRON alias
    max_occurrences: int | None = None  # recurring cap
    expires_at: str | None = None  # recurring stop time

    @classmethod
    def immediate(cls) -> ScheduleTrigger:
        return cls(kind=ScheduleKind.IMMEDIATE)

    @classmethod
    def one_time(cls, run_at: str) -> ScheduleTrigger:
        return cls(kind=ScheduleKind.ONE_TIME, run_at=run_at)

    @classmethod
    def delayed(cls, delay_seconds: int) -> ScheduleTrigger:
        return cls(kind=ScheduleKind.DELAYED, delay_seconds=delay_seconds)

    @classmethod
    def interval(
        cls,
        interval_seconds: int,
        *,
        anchor: str = "",
        max_occurrences: int | None = None,
        expires_at: str | None = None,
    ) -> ScheduleTrigger:
        return cls(
            kind=ScheduleKind.INTERVAL,
            anchor=anchor,
            interval_seconds=interval_seconds,
            max_occurrences=max_occurrences,
            expires_at=expires_at,
        )

    @classmethod
    def from_cron(
        cls, alias: str, *, anchor: str = "", max_occurrences: int | None = None
    ) -> ScheduleTrigger:
        """A cron-like recurring trigger from a supported alias (``@minutely``/``@hourly``/``@daily``/``@weekly``)."""
        return cls(
            kind=ScheduleKind.CRON, cron=alias, anchor=anchor, max_occurrences=max_occurrences
        )


class Schedule(ValueObject):
    """The immutable schedule projection — a deterministic read of the ``scheduler.*`` stream.

    Records the schedule's timing spec, autonomy mode, target (a Goal or a platform operation), current
    lifecycle state, and which occurrence indices have already been dispatched. Rebuildable from the log
    (INV-13/14), so a reopened durable file reconstructs the schedule and never re-dispatches a done
    occurrence (INV-18). The Goal request itself is stored on the ``scheduler.registered`` fact (durable),
    not in this projection.
    """

    identity: str
    kind: ScheduleKind
    status: ScheduleStatus
    autonomy: AutonomyMode
    target_kind: str  # GOAL_TARGET | OPERATION_TARGET
    operation: str | None
    anchor: str
    run_at: str | None
    delay_seconds: int | None
    interval_seconds: int | None
    cron: str | None
    max_occurrences: int | None
    expires_at: str | None
    dispatched: tuple[int, ...]  # occurrence indices already dispatched (idempotency + view)
    correlation_identifier: str = ""

    @property
    def is_active(self) -> bool:
        """Whether the schedule is eligible to fire (active, not paused/terminal)."""
        return self.status is ScheduleStatus.ACTIVE

    @property
    def trigger(self) -> ScheduleTrigger:
        """The timing spec reconstructed from the projection."""
        return ScheduleTrigger(
            kind=self.kind,
            anchor=self.anchor,
            run_at=self.run_at,
            delay_seconds=self.delay_seconds,
            interval_seconds=self.interval_seconds,
            cron=self.cron,
            max_occurrences=self.max_occurrences,
            expires_at=self.expires_at,
        )


@dataclass(frozen=True, slots=True)
class DispatchOutcome:
    """The formatted outcome of dispatching one due occurrence — timing + autonomy provenance."""

    schedule_id: str
    occurrence: int
    occurrence_at: str
    autonomy: AutonomyMode
    executed: bool
    policy_allowed: bool
    policy_decision: str
    reasoning: tuple[str, ...] = field(default_factory=tuple)
    pipeline_status: str | None = None
    session_id: str | None = None
    auto_granted: tuple[str, ...] = field(default_factory=tuple)
    operation: str | None = None
    note: str = ""


@dataclass(frozen=True, slots=True)
class SchedulerHealth:
    """The read-only scheduler health summary (instrumentation only)."""

    active: int
    paused: int
    completed: int
    cancelled: int
    expired: int
    dispatched_total: int
    denied_total: int
    upcoming: tuple[str, ...]  # ids of active schedules with occurrences still to fire
