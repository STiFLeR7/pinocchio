"""PipelineExecutor -- run a workflow, and replay it from the event store (Milestone 1/4).

The executor is the top-level entry point: :meth:`execute` runs a :class:`WorkflowRequest` through
the :class:`WorkflowCoordinator` over a wired :class:`Pipeline`, and :meth:`replay` reconstructs the
complete operational timeline **from the authoritative event log alone** (ADR-001) -- no live
engine, no information loss.

Because Knowledge, Item versions, and every engine's state are projections of the append-only log,
reconstruction is deterministic: the same event store always yields the same replayed timeline, and
a second identical run yields a byte-identical event stream.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from nexus_core.domain.event import Event
from nexus_workflows.coordinator import WorkflowCoordinator, WorkflowRun
from nexus_workflows.pipeline import Pipeline
from nexus_workflows.request import WorkflowRequest


@dataclass(frozen=True, slots=True)
class ReplayStage:
    """One contiguous run of same-producer events in the reconstructed history."""

    producer: str
    event_types: tuple[str, ...]
    correlation_identifier: str

    @property
    def count(self) -> int:
        """How many events this producer contributed contiguously."""
        return len(self.event_types)


@dataclass(frozen=True, slots=True)
class ReplayTimeline:
    """The operational history reconstructed from the event store (no information loss)."""

    stages: tuple[ReplayStage, ...]
    event_ids: tuple[str, ...]
    event_types: tuple[str, ...]
    producers: tuple[str, ...]

    @property
    def total_events(self) -> int:
        """Total events reconstructed from the log."""
        return len(self.event_ids)

    def distinct_producers(self) -> tuple[str, ...]:
        """The unique producers that appear in the log, in first-seen order."""
        seen: list[str] = []
        for producer in self.producers:
            if producer not in seen:
                seen.append(producer)
        return tuple(seen)


def reconstruct(events: Iterable[Event]) -> ReplayTimeline:
    """Rebuild the operational timeline from an ordered event stream (the replay function)."""
    ordered = tuple(events)
    stages: list[ReplayStage] = []
    current_producer: str | None = None
    types: list[str] = []
    correlation = ""
    for event in ordered:
        if event.producer != current_producer:
            if current_producer is not None:
                stages.append(ReplayStage(current_producer, tuple(types), correlation))
            current_producer = event.producer
            types = []
            correlation = event.correlation_identifier
        types.append(event.type)
    if current_producer is not None:
        stages.append(ReplayStage(current_producer, tuple(types), correlation))
    return ReplayTimeline(
        stages=tuple(stages),
        event_ids=tuple(e.identifier for e in ordered),
        event_types=tuple(e.type for e in ordered),
        producers=tuple(e.producer for e in ordered),
    )


class PipelineExecutor:
    """Runs a workflow over a pipeline and replays it from the shared event store."""

    def __init__(self, pipeline: Pipeline) -> None:
        self._pipeline = pipeline

    @property
    def pipeline(self) -> Pipeline:
        """The wired pipeline this executor drives."""
        return self._pipeline

    def execute(self, request: WorkflowRequest) -> WorkflowRun:
        """Run one workflow end-to-end and return its outcome + timeline."""
        return WorkflowCoordinator(self._pipeline).run(request)

    def replay(self) -> ReplayTimeline:
        """Reconstruct the operational timeline from the pipeline's event store (ADR-001)."""
        return reconstruct(self._pipeline.infrastructure.event_store.read_all())
