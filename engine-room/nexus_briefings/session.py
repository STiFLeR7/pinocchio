"""BriefingSession — the immutable outcome of one briefing generation.

A session bundles what a generation produced: the brief type, the runtime it executed on, the raw
:class:`~nexus_workflows.WorkflowRun` (every engine's output), the composed
:class:`~nexus_briefings.document.Brief`, and the Knowledge repositories the run wrote to (so a
later generation can consume that learning — Milestone 5). It adds no behaviour of its own beyond
read-only projections and rendering of the brief it holds; replay is the existing log
reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_briefings.brieftype import BriefType
from nexus_briefings.document import Brief
from nexus_briefings.renderers import render
from nexus_core.domain.event import Event
from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_workflows import ReplayTimeline, WorkflowRun, WorkflowTimeline, reconstruct


@dataclass(frozen=True, slots=True)
class BriefingSession:
    """One briefing generation's complete, immutable record."""

    brief_type: BriefType
    runtime_identity: str
    run: WorkflowRun
    brief: Brief
    knowledge_repositories: KnowledgeRepositories

    @property
    def succeeded(self) -> bool:
        """Whether every briefing stage executed to completion (not a validation verdict)."""
        return self.run.succeeded

    @property
    def events(self) -> tuple[Event, ...]:
        """Every event the run appended to the shared log, in order."""
        return self.run.events

    @property
    def timeline(self) -> WorkflowTimeline:
        """The cross-layer stage timeline of the run."""
        return self.run.timeline

    @property
    def knowledge_consumed(self) -> int:
        """How many Knowledge Items informed this generation's Planning (Milestone 5)."""
        return self.run.knowledge_consumed

    def render(self, fmt: str = "markdown") -> str:
        """Render the composed brief in ``fmt`` (markdown / html / json)."""
        return render(self.brief, fmt)

    def replay(self) -> ReplayTimeline:
        """Reconstruct the operational history from the event log alone (no live engine)."""
        return reconstruct(self.run.events)
