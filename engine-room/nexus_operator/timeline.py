"""Operational Timeline — a unified, operator-facing execution history (Milestone 2).

The :class:`TimelineCoordinator` projects a submission's :class:`~nexus_workflows.WorkflowTimeline`
into operator phases — Context, Planning, Runtime, Execution, Validation, Recovery, Reflection,
Knowledge, and (for a briefing submission) Briefings. Each entry links back to persisted evidence:
the artifact references the stage produced *and* the span of the persisted event log the stage
appended (INV-27 — references only, never duplicated content). It is pure instrumentation over the
authoritative log; it decides nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_operator.history import SubmissionKind, SubmissionRecord

# Engine → operator phase. Orchestration / Harness / Runtime are folded into one "Runtime" phase;
# the two Knowledge stages (read/write) both surface as "Knowledge".
_PHASE_BY_ENGINE: dict[str, str] = {
    "context_engineering": "Context",
    "knowledge": "Knowledge",
    "planning": "Planning",
    "orchestration": "Runtime",
    "harness": "Runtime",
    "runtime": "Runtime",
    "execution": "Execution",
    "validation": "Validation",
    "recovery": "Recovery",
    "reflection": "Reflection",
}


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """One operator-facing timeline entry, linked to its persisted evidence."""

    ordinal: int
    phase: str
    engine: str
    label: str
    evidence_refs: tuple[str, ...]
    first_event_index: int
    event_count: int


@dataclass(frozen=True, slots=True)
class OperationalTimeline:
    """The unified execution history of one submission."""

    submission_id: str
    entries: tuple[TimelineEntry, ...]
    total_events: int

    def phases(self) -> tuple[str, ...]:
        """The distinct operator phases, in first-seen order."""
        seen: list[str] = []
        for entry in self.entries:
            if entry.phase not in seen:
                seen.append(entry.phase)
        return tuple(seen)

    def evidence(self) -> tuple[str, ...]:
        """Every persisted evidence reference linked across the timeline, in order."""
        return tuple(ref for entry in self.entries for ref in entry.evidence_refs)


class TimelineCoordinator:
    """Builds a :class:`OperationalTimeline` from a submission record (Milestone 1/2)."""

    def build(self, record: SubmissionRecord) -> OperationalTimeline:
        """Project ``record``'s workflow timeline into operator phases with evidence links."""
        entries = [
            TimelineEntry(
                ordinal=ordinal,
                phase=_PHASE_BY_ENGINE.get(stage.engine, stage.engine.title()),
                engine=stage.engine,
                label=stage.label,
                evidence_refs=tuple(ref.identifier for ref in stage.artifact_refs),
                first_event_index=stage.event_index_before,
                event_count=stage.emitted_count,
            )
            for ordinal, stage in enumerate(record.run.timeline.stages)
        ]
        if record.kind is SubmissionKind.BRIEFING and record.brief is not None:
            entries.append(_briefings_entry(len(entries), record))
        return OperationalTimeline(
            submission_id=record.submission_id,
            entries=tuple(entries),
            total_events=record.run.timeline.total_events,
        )


def _briefings_entry(ordinal: int, record: SubmissionRecord) -> TimelineEntry:
    brief = record.brief
    assert brief is not None
    evidence = tuple(
        ref for section in brief.sections for ref in section.validated_artifacts
    ) or tuple(ref for section in brief.sections for ref in section.evidence_refs)
    last = record.run.timeline.stages[-1] if record.run.timeline.stages else None
    tail = last.event_index_after if last is not None else 0
    return TimelineEntry(
        ordinal=ordinal,
        phase="Briefings",
        engine="briefings",
        label=f"briefing:{brief.brief_type}",
        evidence_refs=evidence,
        first_event_index=tail,
        event_count=0,
    )
