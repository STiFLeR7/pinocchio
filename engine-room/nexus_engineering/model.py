"""Engineering Intelligence value objects — the immutable, explainable Engineering Strategy.

EI produces **exactly one** artifact: the :class:`EngineeringStrategy` (`engineering/03`, `04`) —
one coherent, immutable, declarative decision about *how work should proceed*. It is a subsystem
:class:`~nexus_core.contracts.base.ValueObject` (the ``ValidationReport`` / estimation pattern):
the ``engineering_strategy`` contract is *Proposed*, not frozen, so producing it here freezes no
new contract (INV-07 discipline).

Every facet is a :class:`Recommendation` carrying its own explainability (INV-31): reasoning
chain, contributing evidence, assumptions, confidence, and the **policy / estimation / knowledge
influences** that shaped it. The Strategy is intent-bearing, never instruction-bearing (`03`): no
facet names a runtime, resolves a Skill, writes a Plan, or fixes a completion verdict.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from nexus_core.contracts.base import ValueObject
from nexus_core.domain.goal import Goal
from nexus_core.domain.knowledge import Knowledge
from nexus_estimation.model import EstimationReport


class Recommendation(ValueObject):
    """One facet of the Strategy plus the full explainability the constitution requires (INV-31)."""

    facet: str
    selection: tuple[str, ...]
    """The recommended value(s) — intent/preference/requirement, never a concrete artifact."""
    reasoning_chain: tuple[str, ...]
    contributing_evidence: tuple[str, ...]
    confidence: float
    assumptions: tuple[str, ...] = ()
    policy_influences: tuple[str, ...] = ()
    estimation_influences: tuple[str, ...] = ()
    knowledge_influences: tuple[str, ...] = ()


class PolicyContext(ValueObject):
    """EI's read-only projection of a Policy decision — a **ceiling**, never EI's own verdict.

    Built from a :class:`~nexus_policy.model.PolicyEvaluation` by the Policy Engine (the sole
    evaluator — INV-28). EI *consumes* this; it never evaluates governance. The projection reads
    the evaluation's own attributes (``allowed``, the decision *value*, the approval level) so EI
    never names or constructs the closed governance decision set.
    """

    action_class: str
    decision: str
    allowed: bool
    requires_approval: bool
    approval_level: str | None = None
    matched_policy: str | None = None
    reasoning: tuple[str, ...] = ()

    @classmethod
    def from_evaluation(cls, evaluation: Any) -> PolicyContext:
        """Project a Policy Engine evaluation into EI's read-only ceiling (no governance owned)."""
        decision_value = evaluation.decision.value
        approval = evaluation.approval_requirement
        matched = evaluation.matched_policy
        return cls(
            action_class=evaluation.action_class,
            decision=decision_value,
            allowed=bool(evaluation.allowed),
            requires_approval=decision_value in ("require_approval", "escalate", "delay"),
            approval_level=approval.value if approval is not None else None,
            matched_policy=(
                f"{matched.identity}@{matched.version}" if matched is not None else None
            ),
            reasoning=tuple(evaluation.reasoning_trace),
        )


class EngineeringStrategy(ValueObject):
    """The single, immutable, coherent decision EI emits: how this work should proceed (`04`)."""

    identity: str
    subject_identifier: str
    """The Goal this Strategy is *for* (by id) — EI reads the Goal, never mutates it (INV-08)."""
    correlation_identifier: str
    reasoner_version: str
    engineering_objective: str
    """A restatement of the Goal's outcome as the engineering objective (an outcome, never steps)."""

    # --- the facets (each intent-bearing, each self-explaining) ------------- #
    classification: Recommendation
    approach: Recommendation
    complexity_class: Recommendation
    execution_style: Recommendation
    context_objectives: Recommendation
    skill_requirements: Recommendation
    runtime_preferences: Recommendation
    validation_rigor: Recommendation
    coordination_intent: Recommendation
    recovery_posture: Recommendation
    autonomy_level: Recommendation
    risk_assessment: Recommendation
    observability: Recommendation

    # --- overall + provenance of consumed inputs ---------------------------- #
    rationale: str
    confidence: float
    coherence_notes: tuple[str, ...] = ()
    estimation_ref: str | None = None
    """Identity of the EstimationReport consumed (estimation feeds EI; EI never re-estimates)."""
    policy_context: PolicyContext | None = None
    knowledge_refs: tuple[str, ...] = ()
    timestamp: str = ""

    def facets(self) -> tuple[Recommendation, ...]:
        """Every facet Recommendation, in canonical order (for explainability iteration)."""
        return (
            self.classification,
            self.approach,
            self.complexity_class,
            self.execution_style,
            self.context_objectives,
            self.skill_requirements,
            self.runtime_preferences,
            self.validation_rigor,
            self.coordination_intent,
            self.recovery_posture,
            self.autonomy_level,
            self.risk_assessment,
            self.observability,
        )


@dataclass(frozen=True, slots=True)
class ReasoningInputs:
    """The immutable, read-only inputs EI reasons over (`engineering/02` — the six canonical inputs).

    EI consumes every input **by value / read-only**; it owns none, writes none back, and imports
    no downstream engine (INV-01). ``estimation`` and ``policy_context`` are the outputs of the
    Estimation and Policy engines (which feed EI); ``repository_understanding`` /
    ``operator_preferences`` are fact/reference views (INV-27); all of Repository Understanding,
    Knowledge, and Preferences are **absence-tolerant** (first run, non-repo goal, new operator).
    """

    goal: Goal
    estimation: EstimationReport | None = None
    policy_context: PolicyContext | None = None
    knowledge: tuple[Knowledge, ...] = ()
    repository_understanding: Mapping[str, Any] | None = None
    operator_preferences: Mapping[str, Any] | None = None
    environment_capabilities: tuple[str, ...] = ()
    execution_history: Mapping[str, Any] | None = None
    """Historical grounding facts from Execution History (P8), read-only. Absence-tolerant: first
    run, or history not consulted. EI reads it; it never queries the event log itself (INV-02)."""

    def normalized(self) -> dict[str, Any]:
        """A deterministic, JSON-safe digest of the inputs for the Strategy's content identity."""
        digest: dict[str, Any] = {
            "goal": {
                "identity": self.goal.identity,
                "outcome": self.goal.outcome,
                "domain": self.goal.domain.value,
                "priority": self.goal.priority.value,
                "confidence": self.goal.confidence.value,
                "constraints": sorted(c.kind for c in self.goal.constraints),
                "success_definition": self.goal.success_definition or "",
            },
            "estimation": self.estimation.identity if self.estimation is not None else None,
            "policy": (
                None
                if self.policy_context is None
                else {
                    "decision": self.policy_context.decision,
                    "matched": self.policy_context.matched_policy,
                }
            ),
            "knowledge": sorted(k.identity for k in self.knowledge),
            "repository": _sorted_keys(self.repository_understanding),
            "preferences": _sorted_keys(self.operator_preferences),
            "environment": sorted(self.environment_capabilities),
        }
        if self.execution_history:
            digest["execution_history"] = _sorted_keys(self.execution_history)
        return digest


def _sorted_keys(mapping: Mapping[str, Any] | None) -> list[str]:
    return [] if not mapping else sorted(mapping)
