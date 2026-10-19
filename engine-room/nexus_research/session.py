"""ResearchSession — the immutable outcome of one autonomous research execution.

A session bundles what a research run produced: the topic, the runtime it executed on, the raw
:class:`~nexus_workflows.WorkflowRun` (every engine's output), the projected
:class:`~nexus_research.brief.ResearchBrief`, and the Knowledge repositories the run wrote to (so
a later run can consume that learning — Milestone 6). It adds no behaviour of its own beyond
read-only projections of the run it holds; replay is the existing log reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.domain.event import Event
from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_research.brief import ResearchBrief
from nexus_research.topic import ResearchTopic
from nexus_workflows import ReplayTimeline, WorkflowRun, WorkflowTimeline, reconstruct


@dataclass(frozen=True, slots=True)
class ResearchSession:
    """One research execution's complete, immutable record."""

    topic: ResearchTopic
    runtime_identity: str
    run: WorkflowRun
    brief: ResearchBrief
    knowledge_repositories: KnowledgeRepositories

    @property
    def succeeded(self) -> bool:
        """Whether every research stage executed to completion (not a validation verdict)."""
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
        """How many Knowledge Items informed this run's Planning (Milestone 6)."""
        return self.run.knowledge_consumed

    def replay(self) -> ReplayTimeline:
        """Reconstruct the operational history from the event log alone (no live engine)."""
        return reconstruct(self.run.events)
