"""Step 5 — Execution Strategy assignment (ADR-004, INV-05).

Derives one declarative :class:`ExecutionStrategy` per Plan: the coordination
model plus approval/retry/recovery/checkpoint policy. The coordination model is
chosen **deterministically** from the declared topology (an explicit
``coordination_hint`` overrides). The Strategy declares *how* work is coordinated;
it is runtime-, provider-, and transport-agnostic (``runtime_policy`` is empty =
no capability restriction) and it never evaluates its own policy — Orchestration
enacts it, Recovery selects recovery, the Policy Engine evaluates approval.
"""

from __future__ import annotations

from nexus_core.contracts.base import Correlation
from nexus_core.contracts.enums import (
    ApprovalTaxonomy,
    CoordinationModel,
    RetryBehavior,
)
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.goal import Goal
from nexus_planning import ids
from nexus_planning.requests import PlanningRequest


class StrategyAssigner:
    """Assigns a deterministic Execution Strategy for a planning request."""

    def assign(
        self,
        goal: Goal,
        request: PlanningRequest,
        *,
        correlation_identifier: str,
    ) -> ExecutionStrategy:
        """Build the Plan's Execution Strategy — consuming EI's postures when present (P6).

        Each posture prefers an Engineering-Intelligence-supplied hint (EI owns the engineering
        decision) and falls back to the existing topology-derived value for the operator-authored
        path. This is additive: the fallback derivation is unchanged.
        """
        coordination = request.coordination_hint or self._derive_coordination(request)
        approval = request.approval_hint or self._derive_approval(request)
        retry = request.retry_hint or RetryBehavior.NEVER_RETRY
        checkpoint_keys = tuple(item.key for item in request.work_items if item.is_checkpoint)
        return ExecutionStrategy(
            identity=ids.strategy_id(goal.identity, request.plan_version),
            coordination=coordination,
            runtime_policy=dict(request.runtime_policy or {}),
            approval_policy=approval,
            retry_policy=retry,
            timeout_policy={},
            validation_policy=dict(request.validation_policy or {}),
            recovery_policy=dict(request.recovery_policy or {}),
            checkpoint_policy={"required_checkpoints": list(checkpoint_keys)},
            version=request.plan_version,
            correlation=Correlation(correlation_identifier=correlation_identifier),
        )

    def _derive_coordination(self, request: PlanningRequest) -> CoordinationModel:
        items = request.work_items
        if any(item.requires_approval for item in items):
            return CoordinationModel.APPROVAL_DRIVEN
        has_dependencies = any(item.depends_on for item in items)
        if not has_dependencies:
            return CoordinationModel.PARALLEL if len(items) > 1 else CoordinationModel.SEQUENTIAL
        return (
            CoordinationModel.SEQUENTIAL if self._is_linear(request) else CoordinationModel.HYBRID
        )

    def _derive_approval(self, request: PlanningRequest) -> ApprovalTaxonomy:
        approvals = sum(1 for item in request.work_items if item.requires_approval)
        if approvals == 0:
            return ApprovalTaxonomy.AUTOMATIC
        if approvals == 1:
            return ApprovalTaxonomy.HUMAN_REVIEW
        return ApprovalTaxonomy.MULTI_STAGE

    def _is_linear(self, request: PlanningRequest) -> bool:
        """True when the dependency topology is a single chain (each in/out degree ≤ 1)."""
        outdegree: dict[str, int] = {item.key: 0 for item in request.work_items}
        indegree: dict[str, int] = {item.key: 0 for item in request.work_items}
        for item in request.work_items:
            for dependency in item.depends_on:
                outdegree[dependency] += 1
                indegree[item.key] += 1
        return all(d <= 1 for d in outdegree.values()) and all(d <= 1 for d in indegree.values())
