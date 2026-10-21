"""The Acceptance Engine -- Knowledge's deterministic decision function (doc 05).

Given a Candidate, the current Knowledge state for its Subject Key, and the Persistence Policy,
this returns exactly one governed outcome -- **accept (create)**, **accept (evolve)**, **merge**,
or **reject** -- with an explainable rationale. It is Knowledge's analogue of the Validation rule
evaluator and the Recovery decision precedence: pure, evidence-driven, no clock, no randomness,
no AI, no heuristics.

The precedence is fixed and total: **provenance -> eligibility -> create-vs-evolve ->
merge-vs-reject** (doc 05). The first two steps are the teeth behind "never accept solely because
Reflection recommended it": a candidate is accepted only after *its own* provenance and evidence
clear policy (INV-24), never on the recommendation alone.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nexus_core.contracts.base import Reference, ValueObject
from nexus_core.contracts.enums import ConfidenceLadder
from nexus_core.domain.knowledge import Knowledge
from nexus_knowledge.candidate import KnowledgeCandidate
from nexus_knowledge.model import KnowledgeVersion
from nexus_knowledge.policy import PersistencePolicy, at_least
from nexus_knowledge.vocabulary import (
    REASON_BELOW_MINIMUM_CONFIDENCE,
    REASON_DUPLICATE,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_KIND_NOT_ACCEPTED,
    REASON_PROVENANCE_NOT_VALIDATED,
    REASON_REJECTION_TERMINAL,
    VALIDATED_PROVENANCE_TARGET_TYPES,
    DuplicateStrategy,
    KnowledgeDecision,
)


@dataclass(frozen=True, slots=True)
class SubjectState:
    """The current Knowledge state for one Subject Key (the Engine reads this and nothing else)."""

    item: Knowledge | None = None
    latest_version: KnowledgeVersion | None = None
    recorded_evidence_ids: frozenset[str] = frozenset()
    terminally_rejected: bool = False


class AcceptanceDecision(ValueObject):
    """The immutable, explainable outcome of one acceptance evaluation (INV-31)."""

    outcome: KnowledgeDecision
    subject_key: str
    candidate_id: str
    policy_version: str
    rationale: tuple[str, ...] = ()
    failed_requirement: str | None = None
    confidence_from: ConfidenceLadder | None = None
    confidence_to: ConfidenceLadder | None = None
    evidence_added: tuple[Reference, ...] = ()
    from_version: int | None = None
    to_version: int | None = None

    @property
    def accepted(self) -> bool:
        """Whether the decision creates or changes an Item (anything but reject)."""
        return self.outcome is not KnowledgeDecision.REJECT


class AcceptanceEngine:
    """The pure ``(candidate, subject state, policy) -> decision`` function (doc 05)."""

    def evaluate(
        self,
        candidate: KnowledgeCandidate,
        state: SubjectState,
        policy: PersistencePolicy,
        subject_key: str,
        *,
        source_verifier: Callable[[KnowledgeCandidate], bool] | None = None,
    ) -> AcceptanceDecision:
        """Return the single governed outcome for a candidate, with a rationale trace."""
        trace: list[str] = []

        if state.terminally_rejected:
            return self._reject(
                candidate, subject_key, policy, trace, REASON_REJECTION_TERMINAL, "subject blocked"
            )

        # 1. provenance & evidence (INV-24) -- the recommendation is never enough.
        if len(candidate.evidence_refs) < policy.minimum_evidence:
            return self._reject(
                candidate, subject_key, policy, trace, REASON_INSUFFICIENT_EVIDENCE, "too little"
            )
        if policy.require_validated_provenance and not self._provenance_validated(
            candidate, source_verifier
        ):
            return self._reject(
                candidate,
                subject_key,
                policy,
                trace,
                REASON_PROVENANCE_NOT_VALIDATED,
                "unvalidated",
            )
        trace.append("provenance: ok -- evidence present and validated")

        # 2. eligibility (policy thresholds).
        if not at_least(candidate.confidence, policy.minimum_confidence):
            return self._reject(
                candidate, subject_key, policy, trace, REASON_BELOW_MINIMUM_CONFIDENCE, "too weak"
            )
        if not policy.kind_accepted(candidate.kind):
            return self._reject(
                candidate, subject_key, policy, trace, REASON_KIND_NOT_ACCEPTED, "kind excluded"
            )
        trace.append("eligibility: ok -- confidence and kind clear policy")

        new_evidence = tuple(
            ref
            for ref in candidate.evidence_refs
            if ref.identifier not in state.recorded_evidence_ids
        )
        cumulative = len(
            state.recorded_evidence_ids | {ref.identifier for ref in candidate.evidence_refs}
        )
        if candidate.validation_report_refs:
            cumulative = len(
                {
                    ref.identifier
                    for ref in (
                        *(
                            state.latest_version.validation_report_refs
                            if state.latest_version is not None
                            else ()
                        ),
                        *candidate.validation_report_refs,
                    )
                    if ref.target_type == "validation_report"
                }
            )

        # 3. subject-key resolution.
        if state.item is None or state.latest_version is None:
            confidence_to = policy.promoted_confidence(candidate.confidence, cumulative)
            trace.append("subject: new -- accept (create)")
            return AcceptanceDecision(
                outcome=KnowledgeDecision.ACCEPT_CREATE,
                subject_key=subject_key,
                candidate_id=candidate.identity,
                policy_version=policy.version,
                rationale=tuple(trace),
                confidence_to=confidence_to,
                evidence_added=candidate.evidence_refs,
                to_version=1,
            )

        # 4. duplicate / evolution decision.
        return self._resolve_duplicate(
            candidate, state, policy, subject_key, trace, new_evidence, cumulative
        )

    # -- step 4 -------------------------------------------------------------- #

    def _resolve_duplicate(
        self,
        candidate: KnowledgeCandidate,
        state: SubjectState,
        policy: PersistencePolicy,
        subject_key: str,
        trace: list[str],
        new_evidence: tuple[Reference, ...],
        cumulative: int,
    ) -> AcceptanceDecision:
        assert state.item is not None and state.latest_version is not None
        current = state.latest_version
        statement_changed = candidate.statement != current.statement
        confidence_from = current.confidence
        confidence_to = policy.promoted_confidence(
            self._stronger(current.confidence, candidate.confidence), cumulative
        )

        if policy.duplicate_strategy is DuplicateStrategy.REJECT_AS_DUPLICATE:
            return self._reject(
                candidate, subject_key, policy, trace, REASON_DUPLICATE, "duplicate rejected"
            )

        # Adds nothing new -> reject as duplicate.
        if not new_evidence and not statement_changed:
            return self._reject(
                candidate, subject_key, policy, trace, REASON_DUPLICATE, "no new evidence"
            )

        forced_merge = policy.duplicate_strategy is DuplicateStrategy.MERGE
        if statement_changed and not forced_merge:
            trace.append("duplicate: stronger statement -- accept (evolve)")
            outcome = KnowledgeDecision.ACCEPT_EVOLVE
        else:
            trace.append("duplicate: corroboration -- merge")
            outcome = KnowledgeDecision.MERGE

        return AcceptanceDecision(
            outcome=outcome,
            subject_key=subject_key,
            candidate_id=candidate.identity,
            policy_version=policy.version,
            rationale=tuple(trace),
            confidence_from=confidence_from,
            confidence_to=confidence_to,
            evidence_added=new_evidence,
            from_version=current.version,
            to_version=current.version + 1,
        )

    # -- helpers ------------------------------------------------------------- #

    def _provenance_validated(
        self,
        candidate: KnowledgeCandidate,
        source_verifier: Callable[[KnowledgeCandidate], bool] | None,
    ) -> bool:
        """Every supporting reference resolves; Phase 5 sources require durable verification."""
        types_valid = all(
            ref.target_type in VALIDATED_PROVENANCE_TARGET_TYPES for ref in candidate.evidence_refs
        )
        if not types_valid:
            return False
        if source_verifier is None:
            # Keep the pure engine's legacy type-contract tests independent of infrastructure.
            return candidate.source_goal_ref is None and not candidate.source_run_refs
        return bool(
            candidate.source_goal_ref is not None
            and candidate.source_run_refs
            and candidate.validation_report_refs
            and source_verifier(candidate)
        )

    def _stronger(self, a: ConfidenceLadder, b: ConfidenceLadder) -> ConfidenceLadder:
        return a if at_least(a, b) else b

    def _reject(
        self,
        candidate: KnowledgeCandidate,
        subject_key: str,
        policy: PersistencePolicy,
        trace: list[str],
        reason: str,
        note: str,
    ) -> AcceptanceDecision:
        trace.append(f"reject: {reason} -- {note}")
        return AcceptanceDecision(
            outcome=KnowledgeDecision.REJECT,
            subject_key=subject_key,
            candidate_id=candidate.identity,
            policy_version=policy.version,
            rationale=tuple(trace),
            failed_requirement=reason,
        )
