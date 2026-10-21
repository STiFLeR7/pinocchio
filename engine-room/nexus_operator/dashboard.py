"""Operational Dashboard — aggregate operational information (Milestone 5).

The dashboard is derived **entirely from persisted state** — the retained submission history and
the durable Knowledge store. It computes running/completed workflow counts, validation outcomes,
recovery statistics, knowledge growth, and briefing generation as pure aggregations; it stores no
state of its own and decides nothing.

Execution in this control plane is synchronous and deterministic — a submission fully completes
before :meth:`~nexus_operator.session.OperatorSession.submit_goal` returns — so ``running_workflows``
is always ``0``: there is no in-flight state to report. Completed / failed counts derive from the
persisted execution outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_operator.analysis import node_outcomes
from nexus_operator.history import SessionHistory


@dataclass(frozen=True, slots=True)
class OperationalDashboard:
    """Aggregate operational information derived from persisted state."""

    running_workflows: int
    completed_workflows: int
    failed_workflows: int
    validation_passed: int
    validation_failed: int
    recovery_breakdown: tuple[tuple[str, int], ...]
    knowledge_items: int
    briefings_generated: int
    briefings_publishable: int

    @property
    def total_workflows(self) -> int:
        """Every submission the session has processed."""
        return self.running_workflows + self.completed_workflows + self.failed_workflows


def build_dashboard(
    history: SessionHistory, knowledge: KnowledgeRepositories | None = None
) -> OperationalDashboard:
    """Aggregate the session's persisted state into an :class:`OperationalDashboard`."""
    completed = sum(1 for record in history.records if record.succeeded)
    failed = sum(1 for record in history.records if not record.succeeded)

    validation_passed = 0
    validation_failed = 0
    recovery: dict[str, int] = {}
    for record in history.records:
        for outcome in node_outcomes(record.run):
            if outcome.validation_decision == "passed":
                validation_passed += 1
            else:
                validation_failed += 1
            recovery[outcome.recovery_decision] = recovery.get(outcome.recovery_decision, 0) + 1

    briefings = history.briefings()
    publishable = sum(
        1 for record in briefings if record.brief is not None and record.brief.is_publishable
    )
    knowledge_count = len(knowledge.items.list_all()) if knowledge is not None else 0

    return OperationalDashboard(
        running_workflows=0,
        completed_workflows=completed,
        failed_workflows=failed,
        validation_passed=validation_passed,
        validation_failed=validation_failed,
        recovery_breakdown=tuple(sorted(recovery.items())),
        knowledge_items=knowledge_count,
        briefings_generated=len(briefings),
        briefings_publishable=publishable,
    )
