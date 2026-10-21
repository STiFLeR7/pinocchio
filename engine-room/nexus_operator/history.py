"""SessionHistory — the immutable record of what an operator submitted this session (Milestone 1).

Every submission (a Goal workflow or a briefing generation) is retained as a
:class:`SubmissionRecord` holding the raw :class:`~nexus_workflows.WorkflowRun` (every engine's
output) and, for a briefing, the composed :class:`~nexus_briefings.Brief`. The history adds no
behaviour of its own beyond read-only projections; the timeline, explorers, search, and dashboard
all read from it.
"""

from __future__ import annotations

import enum
from collections.abc import Iterator
from dataclasses import dataclass

from nexus_briefings import Brief
from nexus_workflows import WorkflowRun


class SubmissionKind(enum.StrEnum):
    """The kind of thing an operator submitted."""

    GOAL = "goal"
    BRIEFING = "briefing"


@dataclass(frozen=True, slots=True)
class SubmissionRecord:
    """One operator submission's complete, immutable record."""

    submission_id: str
    kind: SubmissionKind
    title: str
    runtime_identity: str
    run: WorkflowRun
    brief: Brief | None = None

    @property
    def succeeded(self) -> bool:
        """Whether every stage of the submission executed to completion."""
        return self.run.succeeded

    @property
    def status(self) -> str:
        """The terminal workflow status derived from persisted execution outcomes."""
        return "completed" if self.run.succeeded else "failed"


@dataclass(frozen=True, slots=True)
class SessionHistory:
    """The ordered, immutable set of submissions made in one operator session."""

    records: tuple[SubmissionRecord, ...] = ()

    def with_record(self, record: SubmissionRecord) -> SessionHistory:
        """Return a new history with ``record`` appended (the history is immutable)."""
        return SessionHistory((*self.records, record))

    def get(self, submission_id: str) -> SubmissionRecord | None:
        """The record for ``submission_id``, or ``None`` if there is no such submission."""
        return next((r for r in self.records if r.submission_id == submission_id), None)

    def goals(self) -> tuple[SubmissionRecord, ...]:
        """Every Goal submission, in submission order."""
        return tuple(r for r in self.records if r.kind is SubmissionKind.GOAL)

    def briefings(self) -> tuple[SubmissionRecord, ...]:
        """Every briefing submission, in submission order."""
        return tuple(r for r in self.records if r.kind is SubmissionKind.BRIEFING)

    def __iter__(self) -> Iterator[SubmissionRecord]:
        return iter(self.records)

    def __len__(self) -> int:
        return len(self.records)
