"""Operational Explorer — read-only views over persisted state (Milestone 3).

The explorer exposes the operational objects an operator inspects — Goals, Plans, Work Packages,
Runtime Sessions, Validation Reports, Recovery Plans, Reflection Reports, Knowledge Items, and
Briefings — as lightweight, immutable view records projected from the retained
:class:`~nexus_workflows.WorkflowRun`s and the durable Knowledge store. It performs **no mutation**:
every method is a read that reorganizes already-persisted state by reference (INV-27).
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_operator.analysis import node_outcomes, work_package_for
from nexus_operator.history import SessionHistory


@dataclass(frozen=True, slots=True)
class GoalView:
    goal_id: str
    outcome: str
    submission_id: str
    status: str


@dataclass(frozen=True, slots=True)
class PlanView:
    plan_id: str
    goal_id: str
    work_package_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkPackageView:
    work_package_id: str
    plan_id: str
    validation_decision: str
    recovery_decision: str


@dataclass(frozen=True, slots=True)
class RuntimeSessionView:
    session_id: str
    submission_id: str
    runtime_identity: str
    outcome: str


@dataclass(frozen=True, slots=True)
class ValidationReportView:
    work_package_id: str
    decision: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecoveryPlanView:
    work_package_id: str
    decision: str


@dataclass(frozen=True, slots=True)
class ReflectionReportView:
    reflection_ref: str
    submission_id: str
    findings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KnowledgeItemView:
    identity: str
    type: str
    understanding: str
    confidence: str


@dataclass(frozen=True, slots=True)
class BriefingView:
    submission_id: str
    brief_type: str
    title: str
    publishable: bool
    section_count: int


class OperationalExplorer:
    """Read-only navigation over the operational objects a session has produced."""

    def __init__(
        self, history: SessionHistory, knowledge: KnowledgeRepositories | None = None
    ) -> None:
        self._history = history
        self._knowledge = knowledge

    # -- goals / plans / work packages --------------------------------------- #

    def goals(self) -> tuple[GoalView, ...]:
        return tuple(
            GoalView(
                goal_id=record.run.goal_ref.identifier,
                outcome=record.title,
                submission_id=record.submission_id,
                status=record.status,
            )
            for record in self._history.records
        )

    def goal(self, goal_id: str) -> GoalView | None:
        return next((g for g in self.goals() if g.goal_id == goal_id), None)

    def plans(self) -> tuple[PlanView, ...]:
        return tuple(
            PlanView(
                plan_id=record.run.plan_ref.identifier,
                goal_id=record.run.goal_ref.identifier,
                work_package_ids=record.run.work_package_ids,
            )
            for record in self._history.records
        )

    def work_packages(self) -> tuple[WorkPackageView, ...]:
        views: list[WorkPackageView] = []
        for record in self._history.records:
            plan_id = record.run.plan_ref.identifier
            for outcome in node_outcomes(record.run):
                views.append(
                    WorkPackageView(
                        work_package_id=work_package_for(outcome.node, record.run.work_package_ids),
                        plan_id=plan_id,
                        validation_decision=outcome.validation_decision,
                        recovery_decision=outcome.recovery_decision,
                    )
                )
        return tuple(sorted(views, key=lambda v: v.work_package_id))

    # -- runtime sessions ---------------------------------------------------- #

    def runtime_sessions(self) -> tuple[RuntimeSessionView, ...]:
        views: list[RuntimeSessionView] = []
        for record in self._history.records:
            outcomes = record.run.execution_outcomes
            for index, session_id in enumerate(record.run.session_ids):
                views.append(
                    RuntimeSessionView(
                        session_id=session_id,
                        submission_id=record.submission_id,
                        runtime_identity=record.runtime_identity,
                        outcome=outcomes[index] if index < len(outcomes) else "unknown",
                    )
                )
        return tuple(sorted(views, key=lambda v: v.session_id))

    # -- validation / recovery / reflection ---------------------------------- #

    def validation_reports(self) -> tuple[ValidationReportView, ...]:
        views: list[ValidationReportView] = []
        for record in self._history.records:
            for outcome in node_outcomes(record.run):
                views.append(
                    ValidationReportView(
                        work_package_id=work_package_for(outcome.node, record.run.work_package_ids),
                        decision=outcome.validation_decision,
                        evidence_refs=outcome.evidence_refs,
                    )
                )
        return tuple(sorted(views, key=lambda v: v.work_package_id))

    def recovery_plans(self) -> tuple[RecoveryPlanView, ...]:
        views: list[RecoveryPlanView] = []
        for record in self._history.records:
            for outcome in node_outcomes(record.run):
                views.append(
                    RecoveryPlanView(
                        work_package_id=work_package_for(outcome.node, record.run.work_package_ids),
                        decision=outcome.recovery_decision,
                    )
                )
        return tuple(sorted(views, key=lambda v: v.work_package_id))

    def reflection_reports(self) -> tuple[ReflectionReportView, ...]:
        return tuple(
            ReflectionReportView(
                reflection_ref=record.run.reflection_ref.identifier,
                submission_id=record.submission_id,
                findings=record.run.reflection_candidates,
            )
            for record in self._history.records
        )

    # -- knowledge / briefings ----------------------------------------------- #

    def knowledge_items(self) -> tuple[KnowledgeItemView, ...]:
        if self._knowledge is None:
            return ()
        views = [
            KnowledgeItemView(
                identity=item.identity,
                type=item.type.value,
                understanding=item.understanding,
                confidence=item.confidence.value,
            )
            for item in self._knowledge.items.list_all()
        ]
        return tuple(sorted(views, key=lambda v: v.identity))

    def briefings(self) -> tuple[BriefingView, ...]:
        views: list[BriefingView] = []
        for record in self._history.briefings():
            brief = record.brief
            if brief is None:
                continue
            views.append(
                BriefingView(
                    submission_id=record.submission_id,
                    brief_type=brief.brief_type,
                    title=brief.title,
                    publishable=brief.is_publishable,
                    section_count=len(brief.sections),
                )
            )
        return tuple(views)
