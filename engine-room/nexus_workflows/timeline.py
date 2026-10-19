"""Cross-layer operational timeline (Milestone 3).

A :class:`WorkflowTimeline` is the coherent execution history of one workflow run: an ordered
record of every engine the :class:`~nexus_workflows.coordinator.WorkflowCoordinator` entered and
completed, the ``*.``-namespaced events each stage appended to the shared event store, the
artifacts it produced (by reference, INV-27), the correlation lineage, and a deterministic duration
proxy. It is **pure instrumentation** built from the authoritative event log -- it never influences
a decision, and removing it changes visibility, never behaviour.

Because the whole pipeline runs under one injected ``TimestampSource`` (INV-17), wall-clock duration
is deterministic; the honest, replay-stable measure of a stage's work is the number of events it
appended (``emitted_count``), captured here alongside the recorded timestamps.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from nexus_core.contracts.base import Reference
from nexus_core.domain.event import Event


@dataclass(frozen=True, slots=True)
class StageRecord:
    """One engine invocation: entered, completed, what it emitted and produced."""

    ordinal: int
    engine: str
    label: str
    entered_at: str
    completed_at: str
    event_index_before: int
    event_index_after: int
    emitted_event_types: tuple[str, ...]
    artifact_refs: tuple[Reference, ...]
    correlation_identifier: str

    @property
    def emitted_count(self) -> int:
        """How many events this stage appended to the shared log (the duration proxy)."""
        return self.event_index_after - self.event_index_before


@dataclass(frozen=True, slots=True)
class WorkflowTimeline:
    """The ordered, coherent execution history of one workflow run."""

    stages: tuple[StageRecord, ...] = ()
    total_events: int = 0

    def engines(self) -> tuple[str, ...]:
        """The engines entered, in execution order (an engine may appear more than once)."""
        return tuple(stage.engine for stage in self.stages)

    def distinct_engines(self) -> tuple[str, ...]:
        """The unique engines that participated, in first-seen order."""
        seen: list[str] = []
        for stage in self.stages:
            if stage.engine not in seen:
                seen.append(stage.engine)
        return tuple(seen)

    def artifacts(self) -> tuple[Reference, ...]:
        """Every artifact reference produced across the run, in order."""
        return tuple(ref for stage in self.stages for ref in stage.artifact_refs)

    def emitted_types(self) -> tuple[str, ...]:
        """Every event type emitted across the run, in stage/append order."""
        return tuple(t for stage in self.stages for t in stage.emitted_event_types)


class TimelineRecorder:
    """Builds a :class:`WorkflowTimeline` by bracketing each engine call (enter/complete)."""

    def __init__(self, read_all: Callable[[], Iterable[Event]], now: Callable[[], str]) -> None:
        self._read_all = read_all
        self._now = now
        self._stages: list[StageRecord] = []
        self._open: tuple[str, str, int, str] | None = None

    def _snapshot(self) -> tuple[Event, ...]:
        return tuple(self._read_all())

    def _timestamp(self) -> str:
        return self._now()

    def enter(self, engine: str, label: str = "") -> None:
        """Mark entry into an engine stage (records the pre-stage event index)."""
        self._open = (engine, label or engine, len(self._snapshot()), self._timestamp())

    def complete(self, artifacts: tuple[Reference, ...] = ()) -> None:
        """Mark completion of the open stage, capturing the events it appended."""
        assert self._open is not None, "complete() without a matching enter()"
        engine, label, before, entered = self._open
        snapshot = self._snapshot()
        after = len(snapshot)
        emitted = snapshot[before:after]
        correlation = next(
            (e.correlation_identifier for e in emitted if e.correlation_identifier), ""
        )
        self._stages.append(
            StageRecord(
                ordinal=len(self._stages),
                engine=engine,
                label=label,
                entered_at=entered,
                completed_at=self._timestamp(),
                event_index_before=before,
                event_index_after=after,
                emitted_event_types=tuple(e.type for e in emitted),
                artifact_refs=artifacts,
                correlation_identifier=correlation,
            )
        )
        self._open = None

    def build(self) -> WorkflowTimeline:
        """Finalise the recorded stages into an immutable timeline."""
        return WorkflowTimeline(stages=tuple(self._stages), total_events=len(self._snapshot()))
