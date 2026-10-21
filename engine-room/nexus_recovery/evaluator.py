"""Decision evaluation — aggregating recovery rule proposals into one governed decision.

Milestone 2 (aggregation). A pure function of the :class:`RecoveryRuleResult` list and the
:class:`~nexus_recovery.rules.RecoveryContext` — no AI, no randomness. Applicable rules each
propose a decision; the evaluator selects the highest-precedence proposal
(:data:`~nexus_recovery.rules.DECISION_PRECEDENCE`). Progress preservation (Resume) outranks a
full Retry, governance (Await Approval) is never bypassed, a Passed run Completes outright, and
Escalate is the safe floor — so a failure is never silently dropped.

The determination also records the *derivation*: which rule decided, the retry/resume
eligibility the decision rests on, the required next actions, and a one-line-per-rule
reasoning trace (INV-31).
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_recovery.plan import RecoveryRuleResult
from nexus_recovery.rules import DECISION_PRECEDENCE, RecoveryContext
from nexus_recovery.vocabulary import RecoveryDecision, RecoveryRuleOutcome

_PRECEDENCE_INDEX = {decision: rank for rank, decision in enumerate(DECISION_PRECEDENCE)}

_ACTIONS = {
    RecoveryDecision.COMPLETE: ("record completion — no further action required",),
    RecoveryDecision.RETRY: ("re-dispatch the work package for a fresh execution attempt",),
    RecoveryDecision.RESUME: ("restore the latest valid checkpoint and resume execution",),
    RecoveryDecision.ESCALATE: ("hand the failure to the escalation target for a decision",),
    RecoveryDecision.AWAIT_APPROVAL: ("pause and request operator approval before continuing",),
    RecoveryDecision.ABORT: ("stop recovery — the work cannot continue under policy",),
}


@dataclass(frozen=True, slots=True)
class RecoveryDetermination:
    """The aggregated recovery decision plus its explainable derivation."""

    decision: RecoveryDecision
    deciding_rule: str
    required_actions: tuple[str, ...]
    recommendations: tuple[str, ...]
    reasoning_trace: tuple[str, ...]
    retry_eligible: bool
    resumable: bool


class RecoveryEvaluator:
    """Aggregates rule proposals into a deterministic, explainable determination."""

    def evaluate(
        self, rule_results: tuple[RecoveryRuleResult, ...], context: RecoveryContext
    ) -> RecoveryDetermination:
        applicable = [
            r
            for r in rule_results
            if r.outcome is RecoveryRuleOutcome.APPLICABLE and r.proposed_decision is not None
        ]
        winner = min(
            applicable,
            key=lambda r: _PRECEDENCE_INDEX[r.proposed_decision],  # type: ignore[index]
        )
        decision = winner.proposed_decision
        assert decision is not None  # guaranteed by the filter above
        trace = tuple(
            f"{r.rule_id}: {r.outcome.value}"
            + (f" -> {r.proposed_decision.value}" if r.proposed_decision else "")
            + f" — {r.rationale}"
            for r in rule_results
        )
        retry_eligible = any(
            r.rule_id == "recovery_retry" and r.outcome is RecoveryRuleOutcome.APPLICABLE
            for r in rule_results
        )
        resumable = any(
            r.rule_id == "recovery_resume" and r.outcome is RecoveryRuleOutcome.APPLICABLE
            for r in rule_results
        )
        return RecoveryDetermination(
            decision=decision,
            deciding_rule=winner.rule_id,
            required_actions=_ACTIONS[decision],
            recommendations=self._recommendations(decision, context),
            reasoning_trace=trace,
            retry_eligible=retry_eligible,
            resumable=resumable,
        )

    def _recommendations(
        self, decision: RecoveryDecision, context: RecoveryContext
    ) -> tuple[str, ...]:
        if decision is RecoveryDecision.COMPLETE:
            return ()
        if decision is RecoveryDecision.RETRY:
            return (
                f"retry under {context.policy.retry.kind.value} policy "
                f"({context.attempts_remaining} attempt(s) remaining)",
            )
        if decision is RecoveryDecision.RESUME:
            return ("resume preserves completed work — do not repeat it (doc 19)",)
        if decision is RecoveryDecision.AWAIT_APPROVAL:
            return ("await operator approval — recovery never bypasses governance (INV-22)",)
        if decision is RecoveryDecision.ABORT:
            return ("no governed continuation exists — validated evidence is preserved (INV-22)",)
        return (f"escalate to {context.policy.escalation_target} — no automated path remains",)
