"""Execution History value objects — the immutable, facts-only ExecutionHistoryProfile.

Execution History emits **exactly one** artifact: the :class:`ExecutionHistoryProfile` — a
deterministic projection of *what happened before*, reconstructed from the authoritative event log.
It is **facts only**: counts, timelines, references, and lineage edges. No recommendations, no
scoring, no confidence, no reasoning (the constitution's Grounding rule — INV-27: serve facts, then
stop). Every facet is a frozen :class:`~nexus_core.contracts.base.ValueObject` (value equality,
serializable, durable) so the profile embeds in an ``execution_history.*`` event and replays without
re-projecting.

The whole profile is a **pure function of the operational event log** (for a given query scope) —
identical events → identical profile → identical identity. It is a subsystem value object (the
estimation / EI / repository pattern): the ``execution_history`` view is not a frozen core contract,
so this freezes no new contract (INV-07 discipline).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from nexus_core.contracts.base import ValueObject


class EventFrequency(ValueObject):
    """How often each kind of operational fact occurred (execution frequency — counts only)."""

    total: int
    by_type: tuple[tuple[str, int], ...]
    by_producer: tuple[tuple[str, int], ...]


class TimelineEntry(ValueObject):
    """One ordered point in the execution timeline (an authoritative fact, by reference)."""

    sequence: int
    type: str
    correlation_identifier: str
    producer: str
    timestamp: str


class ExecutionEpisode(ValueObject):
    """A previous execution, grouped by its correlation stream (a factual roll-up, no verdict)."""

    correlation_identifier: str
    runtime_starts: int
    runtime_completions: int
    runtime_failures: int
    validated: bool
    recovered: bool
    reflected: bool


class RuntimeHistory(ValueObject):
    """Runtime + runtime-selection history (lifecycle counts and the runtimes seen — facts)."""

    registered: int
    selections: int
    starts: int
    completions: int
    failures: int
    timeouts: int
    cancellations: int
    runtimes: tuple[str, ...]


class ValidationHistory(ValueObject):
    """What was validated (started/completed counts + recorded verdicts by correlation — facts)."""

    started: int
    completed: int
    verdicts: tuple[tuple[str, str], ...]


class RecoveryHistory(ValueObject):
    """What recovered (started/decision counts + recorded decisions by correlation — facts)."""

    started: int
    decisions: int
    outcomes: tuple[tuple[str, str], ...]


class ReflectionHistory(ValueObject):
    """What reflected (started/report counts + the correlations reflected on — facts)."""

    started: int
    reports: int
    correlations: tuple[str, ...]


class KnowledgeLineage(ValueObject):
    """Knowledge lineage — candidate/item counts and the recorded lineage edges (facts only).

    An edge ``(source, target)`` records a knowledge derivation actually present in the log
    (candidate → item, or supersedes → item). No inference, no ranking.
    """

    candidates_received: int
    accepted: int
    rejected: int
    items_created: int
    items_evolved: int
    edges: tuple[tuple[str, str], ...]


class ArtifactHistory(ValueObject):
    """Historical artifacts — count + references (by reference, never embedded content — INV-27)."""

    count: int
    references: tuple[tuple[str, str], ...]


class EvidenceHistory(ValueObject):
    """Historical evidence — count + references collected during validation (by reference)."""

    count: int
    references: tuple[tuple[str, str], ...]


class WorkPackageHistory(ValueObject):
    """Work package history — created count and the work-package references seen (facts)."""

    created: int
    identifiers: tuple[str, ...]


class GoalHistory(ValueObject):
    """Goal history — the distinct goals/operations observed in the log (facts)."""

    goals: tuple[str, ...]
    count: int


class OperatorHistory(ValueObject):
    """Operator execution history — per-operator activity counts (facts)."""

    by_operator: tuple[tuple[str, int], ...]


class RepositoryExecutionHistory(ValueObject):
    """Repository execution history — per-repository activity counts, plus the scoped root (facts)."""

    by_repository: tuple[tuple[str, int], ...]
    scoped_root: str


class RepositorySeam(ValueObject):
    """The tiny read-only view Repository Intelligence consumes through its execution-history seam.

    Facts only: whether any prior execution exists and how many. Repository Intelligence maps this
    into its own profile seam — it reconstructs nothing itself.
    """

    available: bool
    prior_executions: int


class ExecutionHistoryProfile(ValueObject):
    """The single, immutable, facts-only grounding artifact Execution History produces."""

    identity: str
    projector_version: str
    scope: str
    available: bool
    event_count: int
    execution_count: int
    timeline_truncated: bool
    frequency: EventFrequency
    timeline: tuple[TimelineEntry, ...]
    executions: tuple[ExecutionEpisode, ...]
    runtime: RuntimeHistory
    validation: ValidationHistory
    recovery: RecoveryHistory
    reflection: ReflectionHistory
    knowledge_lineage: KnowledgeLineage
    artifacts: ArtifactHistory
    evidence: EvidenceHistory
    work_packages: WorkPackageHistory
    goals: GoalHistory
    operators: OperatorHistory
    repositories: RepositoryExecutionHistory
    correlation_identifier: str = ""
    timestamp: str = ""

    def repository_seam(self) -> RepositorySeam:
        """The read-only view Repository Intelligence consumes (through its existing seam)."""
        return RepositorySeam(available=self.available, prior_executions=self.execution_count)

    def as_facts(self) -> dict[str, object]:
        """A flat, read-only facts mapping for grounding consumers (e.g. Engineering Intelligence).

        Facts only — no recommendation, opinion, or scoring. Engineering Intelligence consumes this
        as historical grounding; it never queries the event log itself.
        """
        return {
            "available": self.available,
            "execution_count": self.execution_count,
            "event_count": self.event_count,
            "runtime_starts": self.runtime.starts,
            "runtime_completions": self.runtime.completions,
            "runtime_failures": self.runtime.failures,
            "runtimes": list(self.runtime.runtimes),
            "validations_completed": self.validation.completed,
            "recoveries": self.recovery.decisions,
            "reflections": self.reflection.reports,
            "knowledge_items": self.knowledge_lineage.items_created,
            "artifacts": self.artifacts.count,
            "goals": list(self.goals.goals),
        }


@dataclass(frozen=True, slots=True)
class HistoryQuery:
    """The immutable, read-only query that scopes a historical projection (deterministic retrieval).

    Every filter is optional; an empty query means "the whole operational log". Scoping never
    reasons — it selects events by their recorded facts (correlation, goal, repository, runtime,
    operator), then projects deterministically.
    """

    correlation_identifier: str = ""
    goal_identifier: str = ""
    repository_root: str = ""
    runtime: str = ""
    operator: str = ""

    def scope(self) -> str:
        """A short, deterministic descriptor of this query's scope (for identity + observability)."""
        parts = []
        if self.correlation_identifier:
            parts.append(f"cor:{self.correlation_identifier}")
        if self.goal_identifier:
            parts.append(f"goal:{self.goal_identifier}")
        if self.repository_root:
            parts.append(f"repo:{self.repository_root}")
        if self.runtime:
            parts.append(f"rt:{self.runtime}")
        if self.operator:
            parts.append(f"op:{self.operator}")
        return "|".join(parts) if parts else "global"

    def normalized(self) -> Mapping[str, Any]:
        """A JSON-safe view of the query (part of the profile's content identity)."""
        return {
            "correlation": self.correlation_identifier,
            "goal": self.goal_identifier,
            "repository": self.repository_root,
            "runtime": self.runtime,
            "operator": self.operator,
        }
