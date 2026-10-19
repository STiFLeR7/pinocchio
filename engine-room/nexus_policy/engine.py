"""The Policy Engine — the single constitutional evaluator of governance decisions.

Given a :class:`~nexus_policy.model.DecisionRequest` it returns an immutable
:class:`~nexus_policy.model.PolicyEvaluation`: it matches the enabled policy set
(``conditions`` interpreter), resolves conflicts by the fixed order
Specificity → Priority → Version → Default Policy, and yields a decision from the
closed set {Allow, Deny, RequireApproval, Delay, Escalate, RequestInformation}.

Constitutional boundaries it holds:

- **INV-28 — sole evaluator.** This is the only component that returns a
  ``PolicyDecision``; subsystems *query* it and never hardcode governance rules.
- **INV-29 — decides, performs no action.** ``evaluate`` returns a value and emits one
  decision *fact*; it runs no approval workflow, mutates no plan, creates no goal,
  performs no governance. When the decision is ``RequireApproval`` it reports the
  required approval *level* — Governance enforces it elsewhere.
- **INV-30 — fail closed.** A *governed* request with no matching policy is denied by
  the Default Policy; a malformed/erroring evaluation is denied. Only an *explicitly
  ungoverned* action class is allow-by-default.
- **INV-31 — explainable.** Every evaluation carries a reasoning trace, the matched
  policy (by exact identity+version), and the full applicable set.

Evaluation is a pure function of (request, enabled policy set): identical input always
yields the identical decision (ADR-004 §8 determinism). :meth:`simulate` evaluates with
no side effects — no event, no counter (contract §6 *side-effect-free simulation*).
"""

from __future__ import annotations

from collections.abc import Callable

from nexus_core.contracts.base import Struct
from nexus_core.contracts.enums import ApprovalTaxonomy, PolicyDecision
from nexus_core.domain.event import Event
from nexus_core.domain.policy import Policy
from nexus_core.events.interfaces import EventEmitter
from nexus_policy.conditions import matches, specificity
from nexus_policy.defaults import DEFAULT_POLICY
from nexus_policy.events import POLICY_EVALUATED, build_event, system_now
from nexus_policy.ids import decision_event_id
from nexus_policy.model import DecisionRequest, PolicyEvaluation, PolicyRef
from nexus_policy.observability import PolicyObservability
from nexus_policy.precedence import resolve
from nexus_policy.registry import InMemoryPolicyRegistry


class PolicyEngine:
    """Deterministic, fail-closed, explainable evaluation of governance decisions."""

    def __init__(
        self,
        registry: InMemoryPolicyRegistry,
        *,
        emitter: EventEmitter | None = None,
        observability: PolicyObservability | None = None,
        now: Callable[[], str] | None = None,
        default_policy: Policy = DEFAULT_POLICY,
    ) -> None:
        self._registry = registry
        self._emitter = emitter
        self._obs = observability or PolicyObservability()
        self._now = now or system_now
        self._default = default_policy

    # -- public API --------------------------------------------------------- #

    def evaluate(self, request: DecisionRequest, *, simulate: bool = False) -> PolicyEvaluation:
        """Evaluate ``request`` to one immutable decision; emit exactly one fact unless simulating."""
        try:
            evaluation = self._decide(request)
        except Exception as exc:
            evaluation = self._fail_closed(request, exc)
        if not simulate:
            self._record(evaluation)
        return evaluation

    def simulate(self, request: DecisionRequest) -> PolicyEvaluation:
        """Evaluate with zero side effects — no event, no counter (contract §6)."""
        return self.evaluate(request, simulate=True)

    # -- evaluation --------------------------------------------------------- #

    def _decide(self, request: DecisionRequest) -> PolicyEvaluation:
        if not request.governed:
            return self._value(
                request,
                decision=PolicyDecision.ALLOW,
                default_applied=False,
                specificity_value=0,
                matched=None,
                applicable=(),
                trace=("ungoverned action class → allow-by-default (INV-30)",),
            )

        view = request.evaluation_view()
        applicable: list[tuple[Policy, int]] = []
        trace: list[str] = []
        for policy in sorted(self._registry.enabled(), key=lambda p: p.identity):
            if matches(policy.conditions, view):
                spec = specificity(policy.conditions)
                applicable.append((policy, spec))
                trace.append(
                    f"applicable: {policy.identity}@{policy.version} "
                    f"(specificity={spec}, decision={policy.decision.value})"
                )

        if not applicable:
            winner = self._default
            default_applied = True
            trace.append(
                f"no policy matched → Default Policy {winner.identity}@{winner.version} "
                f"→ {winner.decision.value} (fail-closed, INV-30)"
            )
        else:
            winner = resolve(tuple(applicable))
            default_applied = False
            trace.append(
                f"winner: {winner.identity}@{winner.version} → {winner.decision.value} "
                f"(Specificity → Priority → Version)"
            )

        return self._value(
            request,
            decision=winner.decision,
            default_applied=default_applied,
            specificity_value=specificity(winner.conditions),
            matched=PolicyRef(winner.identity, winner.version),
            applicable=tuple(PolicyRef(p.identity, p.version) for p, _ in applicable),
            trace=tuple(trace),
            approval_source=winner.approval_requirement,
            constraints=winner.constraints,
        )

    def _fail_closed(self, request: DecisionRequest, exc: Exception) -> PolicyEvaluation:
        return self._value(
            request,
            decision=PolicyDecision.DENY,
            default_applied=True,
            specificity_value=0,
            matched=PolicyRef(self._default.identity, self._default.version),
            applicable=(),
            trace=(f"evaluation error → fail-closed deny (INV-30): {type(exc).__name__}: {exc}",),
        )

    def _value(
        self,
        request: DecisionRequest,
        *,
        decision: PolicyDecision,
        default_applied: bool,
        specificity_value: int,
        matched: PolicyRef | None,
        applicable: tuple[PolicyRef, ...],
        trace: tuple[str, ...],
        approval_source: ApprovalTaxonomy | None = None,
        constraints: Struct | None = None,
    ) -> PolicyEvaluation:
        approval = None
        if decision is PolicyDecision.REQUIRE_APPROVAL:
            # ADR-004 §3.3: an unspecified level maps to HumanReview (v1 "Explicit Approval").
            approval = approval_source or ApprovalTaxonomy.HUMAN_REVIEW
        return PolicyEvaluation(
            decision=decision,
            action_class=request.action_class,
            correlation_identifier=request.correlation_identifier,
            governed=request.governed,
            default_applied=default_applied,
            specificity=specificity_value,
            matched_policy=matched,
            applicable_policies=applicable,
            reasoning_trace=trace,
            request_attributes=dict(request.attributes),
            approval_requirement=approval,
            constraints=constraints,
        )

    # -- provenance (WP-P2.2) ---------------------------------------------- #

    def _record(self, evaluation: PolicyEvaluation) -> None:
        self._obs.evaluated(evaluation.decision)
        if evaluation.default_applied:
            self._obs.default_applied()
        if self._emitter is not None:
            self._emitter.emit(self._decision_event(evaluation))

    def _decision_event(self, evaluation: PolicyEvaluation) -> Event:
        payload = {
            "decision": evaluation.decision.value,
            "action_class": evaluation.action_class,
            "governed": evaluation.governed,
            "default_applied": evaluation.default_applied,
            "specificity": evaluation.specificity,
            "matched_policy": (
                {
                    "identity": evaluation.matched_policy.identity,
                    "version": evaluation.matched_policy.version,
                }
                if evaluation.matched_policy is not None
                else None
            ),
            "applicable": [
                {"identity": r.identity, "version": r.version}
                for r in evaluation.applicable_policies
            ],
            "approval_requirement": (
                evaluation.approval_requirement.value
                if evaluation.approval_requirement is not None
                else None
            ),
            "attributes": dict(evaluation.request_attributes),
        }
        return build_event(
            decision_event_id(evaluation.correlation_identifier, payload),
            POLICY_EVALUATED,
            evaluation.correlation_identifier,
            payload,
            self._now(),
        )
