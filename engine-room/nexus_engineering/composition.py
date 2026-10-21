"""Engineering composition — dependency-injection wiring for Engineering Intelligence.

Mirrors ``build_estimation`` / ``build_policy``: it **reuses** the P1 substrate unchanged (emitter
= the infrastructure context, repository = a reused ``InMemoryRepository``, metrics = the context's
observability). Integration is additive DI only; no engine is modified. Durable persistence is
transparent over ``build_durable_infrastructure`` (ADR-007).

:meth:`EngineeringContext.strategize_for_goal` is where EI **consumes** its upstream inputs: it
queries the Estimation Engine (which *feeds* EI) for a report and the Policy Engine (the sole
evaluator — INV-28) via side-effect-free ``simulate`` for the governance ceiling, then reasons.
EI never evaluates policy and never estimates quantitatively — it delegates to their owners and
consumes the results (INV-02).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from nexus_core.domain.goal import Goal
from nexus_core.domain.knowledge import Knowledge
from nexus_engineering.engine import EngineeringIntelligence
from nexus_engineering.model import EngineeringStrategy, PolicyContext, ReasoningInputs
from nexus_engineering.observability import EngineeringObservability
from nexus_engineering.persistence import EngineeringRepositories, build_engineering_repositories
from nexus_engineering.reasoner import Reasoner
from nexus_infra import InfrastructureContext


@dataclass(frozen=True, slots=True)
class EngineeringContext:
    """The wired Engineering-Intelligence subsystem (immutable wiring, stateful engine + repo)."""

    infrastructure: InfrastructureContext
    repositories: EngineeringRepositories
    engine: EngineeringIntelligence

    def strategize_for_goal(
        self,
        goal: Goal,
        *,
        estimation_engine: Any | None = None,
        policy_engine: Any | None = None,
        knowledge: tuple[Knowledge, ...] = (),
        repository_profile: Any | None = None,
        repository_understanding: Mapping[str, float] | None = None,
        execution_history_profile: Any | None = None,
        execution_history: Mapping[str, Any] | None = None,
        operator_preferences: Mapping[str, float] | None = None,
        environment_capabilities: tuple[str, ...] = (),
        action_class: str = "engineering",
        signals: Mapping[str, float] | None = None,
        persist: bool = True,
    ) -> EngineeringStrategy:
        """Consume Estimation + Policy (+ optional Repository/History grounding) for a Goal, then reason.

        ``repository_profile`` is a RepositoryProfile from Repository Intelligence (P7);
        ``execution_history_profile`` is an ExecutionHistoryProfile from Execution History (P8). EI
        consumes each as read-only grounding facts (``profile.as_facts()``) — it never inspects the
        repository and never queries the event log itself. Both are duck-typed so EI takes no
        dependency on ``nexus_repository`` / ``nexus_history`` (grounding is upstream).
        """
        correlation = (
            goal.correlation.correlation_identifier
            if goal.correlation is not None
            else goal.identity
        )
        if repository_profile is not None and repository_understanding is None:
            repository_understanding = repository_profile.as_facts()
        if execution_history_profile is not None and execution_history is None:
            execution_history = execution_history_profile.as_facts()

        estimation = None
        if estimation_engine is not None:
            from nexus_estimation import EstimationInputs

            estimation = estimation_engine.estimate(
                EstimationInputs(goal.identity, correlation, signals or signals_from_goal(goal)),
                persist=persist,
            )

        policy_context = None
        if policy_engine is not None:
            from nexus_policy import DecisionRequest

            evaluation = policy_engine.simulate(
                DecisionRequest(
                    action_class=action_class,
                    correlation_identifier=correlation,
                    attributes={"domain": goal.domain.value, "priority": goal.priority.value},
                )
            )
            policy_context = PolicyContext.from_evaluation(evaluation)

        inputs = ReasoningInputs(
            goal=goal,
            estimation=estimation,
            policy_context=policy_context,
            knowledge=knowledge,
            repository_understanding=repository_understanding,
            execution_history=execution_history,
            operator_preferences=operator_preferences,
            environment_capabilities=environment_capabilities,
        )
        return self.engine.strategize(inputs, persist=persist)


def signals_from_goal(goal: Goal) -> dict[str, float]:
    """Coarse, factual goal-level signals for a goal-scoped estimate (counts only; no scoring)."""
    return {
        "objective_size": float(len(goal.outcome.split())),
        "constraint_count": float(len(goal.constraints)),
        "scope_included": float(len(goal.scope.included)),
        "scope_excluded": float(len(goal.scope.excluded)),
        "assumption_count": float(len(goal.assumptions)),
    }


def build_engineering(
    infrastructure: InfrastructureContext,
    *,
    reasoner: Reasoner | None = None,
    repositories: EngineeringRepositories | None = None,
    now: Callable[[], str] | None = None,
) -> EngineeringContext:
    """Wire an engineering context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    resolved = repositories or build_engineering_repositories(obs)
    engine = EngineeringIntelligence(
        reasoner,
        emitter=infrastructure,
        repositories=resolved,
        observability=EngineeringObservability(obs),
        now=now,
    )
    return EngineeringContext(infrastructure=infrastructure, repositories=resolved, engine=engine)
