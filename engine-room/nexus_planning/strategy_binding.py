"""Strategy binding — where Planning **consumes** the Engineering Strategy (P6).

The Constitution permits "Plan may depend on the Engineering Strategy": Engineering Intelligence
*authors* the engineering postures (execution style, approval, recovery, validation, runtime
capabilities); Planning *consumes* them and decomposes within them. This module maps the immutable
:class:`~nexus_engineering.model.EngineeringStrategy` facets onto the Planning input surface — the
optional hints on :class:`~nexus_planning.requests.PlanningRequest` that :class:`StrategyAssigner`
already prefers over its own derivation. It performs **no engineering reasoning**: it reads the
Strategy's already-decided facet values and translates them into Planning's vocabulary.

This is the design's compatibility property: EI adds a *producer* of the postures, not a mutation of
Planning. The decomposition algorithm is untouched; only the *source* of the postures moves from
operator/topology to the Engineering Strategy.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import ApprovalTaxonomy, CoordinationModel, RetryBehavior
from nexus_engineering.model import EngineeringStrategy
from nexus_planning.requests import PlanningRequest

# EI execution style → Planning coordination model (topology-level; Orchestration enacts — INV-05).
_COORDINATION = {
    "sequential": CoordinationModel.SEQUENTIAL,
    "parallel": CoordinationModel.PARALLEL,
    "mixed": CoordinationModel.HYBRID,
}
# EI autonomy level → approval posture (the frozen taxonomy; Policy still decides the outcome — INV-29).
_APPROVAL = {
    "autonomous": ApprovalTaxonomy.AUTOMATIC,
    "supervised": ApprovalTaxonomy.HUMAN_REVIEW,
    "gated": ApprovalTaxonomy.HUMAN_REVIEW,
    "manual": ApprovalTaxonomy.MULTI_STAGE,
}
# EI recovery posture → retry behavior (declaration only; Recovery selects — INV-22).
_RETRY = {
    "retry_then_escalate": RetryBehavior.FIXED_RETRY,
    "checkpoint_and_escalate": RetryBehavior.FIXED_RETRY,
    "escalate_immediately": RetryBehavior.HUMAN_ESCALATION,
}


def strategy_hints(strategy: EngineeringStrategy) -> dict[str, object]:
    """Translate an EngineeringStrategy's facets into Planning's posture hints (pure)."""
    execution = strategy.execution_style.selection[0]
    autonomy = strategy.autonomy_level.selection[0]
    recovery = strategy.recovery_posture.selection[0]
    rigor = strategy.validation_rigor.selection
    return {
        "coordination_hint": _COORDINATION.get(execution),
        "approval_hint": _APPROVAL.get(autonomy),
        "retry_hint": _RETRY.get(recovery),
        "validation_policy": {"rigor": rigor[0], "mandatory_evidence": list(rigor[1:])},
        "recovery_policy": {"posture": recovery},
        "runtime_policy": {"capabilities": list(strategy.runtime_preferences.selection)},
        "engineering_strategy_ref": Reference(
            target_type="engineering_strategy", identifier=strategy.identity
        ),
    }


def bind_strategy(request: PlanningRequest, strategy: EngineeringStrategy) -> PlanningRequest:
    """Return a copy of ``request`` whose posture hints are supplied by the Engineering Strategy.

    EI is the constitutional author of these postures, so the Strategy's values are applied
    (overriding any operator-authored hints). The work decomposition (``work_items``) is untouched —
    Planning still owns breakdown, dependencies, graph, and sequencing.
    """
    return request.model_copy(update=strategy_hints(strategy))
