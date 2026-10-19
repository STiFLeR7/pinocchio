"""The constitutional learning integration (P14/A) — governed, deterministic Knowledge grounding.

The platform records Knowledge (Reflection → Knowledge). P14 closes the loop: prior Knowledge becomes
an **optional, governed** grounding input to future executions, flowing **Knowledge → Engineering →
Context → Planning** — never directly into Planning (INV-26), never owned by anyone but the Knowledge
engine (read-only serve).

:class:`KnowledgeSelector` is the deterministic selector:

1. **retrieve** — ``knowledge.serve(query)`` (read-only, stable order — INV-16); the Knowledge engine
   remains the sole owner and decides what matches;
2. **govern** — the Policy engine (sole evaluator — INV-28) evaluates a ``knowledge_grounding`` decision;
   admitted only when governance allows. This is a *governed* action class permitted by an explicit,
   overridable allow-baseline policy (mirroring ``policy.execution.allow-baseline``) — a deny policy
   filters grounding out. No bypass, fail-closed-consistent (INV-30).

The output :class:`KnowledgeSelection` carries the admitted Knowledge (fed to Engineering's ``knowledge``
input and the P9 grounded-Context ``GroundingInputs.knowledge`` — INV-06) plus **references-only**
provenance (subject, kind, governance verdict + trace, selected ids). Selection is a pure function of the
Knowledge store + Goal + Policy, so it is deterministic and replayable; it mutates no Knowledge and does
no semantic/LLM ranking.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, Struct, ValueObject
from nexus_core.contracts.enums import ConfidenceLadder, KnowledgeType
from nexus_core.domain.goal import Goal
from nexus_core.domain.knowledge import Knowledge
from nexus_knowledge import KnowledgeEngine, KnowledgeQuery
from nexus_policy import (
    KNOWLEDGE_GROUNDING_ACTION_CLASS,
    DecisionRequest,
    PolicyEngine,
    knowledge_grounding_baseline,
)

# The governance policy that admits grounding is defined by the governance owner (nexus_policy) and only
# *registered* + *queried* here — the learning integration never constructs a policy verdict (INV-28).
KNOWLEDGE_GROUNDING_ACTION = KNOWLEDGE_GROUNDING_ACTION_CLASS

__all__ = [
    "KNOWLEDGE_GROUNDING_ACTION",
    "KnowledgeSelection",
    "KnowledgeSelector",
    "knowledge_grounding_baseline",
]


class KnowledgeSelection(ValueObject):
    """The immutable, governed selection of prior Knowledge to ground one execution (references only).

    ``items`` are the admitted Knowledge value objects (fed to Engineering + grounded Context, by value,
    read-only). ``references`` / ``selected_ids`` are the provenance (INV — embed references only).
    ``governed`` is the governance verdict (``allowed``); ``decision`` + ``reasoning`` explain it.
    """

    subject: str
    kind: str
    governed: bool
    decision: str
    reasoning: tuple[str, ...]
    references: tuple[Reference, ...]
    selected_ids: tuple[str, ...]
    items: tuple[Knowledge, ...] = ()  # by value; not serialized to a fact

    @property
    def consumed(self) -> int:
        """How many prior Knowledge items were admitted as grounding."""
        return len(self.items)

    def provenance(self) -> dict[str, object]:
        """A replayable record of the exact selected immutable item projections."""
        return {
            "subject": self.subject,
            "kind": self.kind,
            "governed": self.governed,
            "decision": self.decision,
            "reasoning": list(self.reasoning),
            "references": [
                {"target_type": r.target_type, "identifier": r.identifier} for r in self.references
            ],
            "selected_ids": list(self.selected_ids),
            "count": self.consumed,
            "item_snapshots": [item.model_dump(mode="json") for item in self.items],
        }


class KnowledgeSelector:
    """Deterministically retrieves prior Knowledge and governs its admission as grounding."""

    def __init__(self, knowledge_engine: KnowledgeEngine, policy_engine: PolicyEngine) -> None:
        self._knowledge = knowledge_engine
        self._policy = policy_engine

    def select(
        self,
        *,
        goal: Goal,
        subject: str,
        kind: KnowledgeType,
        correlation: str,
        applicability: Struct | None = None,
        confidence_floor: ConfidenceLadder | None = None,
    ) -> KnowledgeSelection:
        """Serve prior Knowledge for the subject, then admit it only if governance allows."""
        served = self._knowledge.serve(
            KnowledgeQuery(
                subject=subject,
                kind=kind,
                domain=goal.domain,
                applicability=applicability,
                confidence_floor=confidence_floor,
            )
        )
        verdict = self._policy.simulate(
            DecisionRequest(
                action_class=KNOWLEDGE_GROUNDING_ACTION,
                correlation_identifier=correlation,
                attributes={
                    "domain": goal.domain.value,
                    "priority": goal.priority.value,
                    "subject": subject,
                },
                governed=True,
            )
        )
        admitted = served if verdict.allowed else ()
        return KnowledgeSelection(
            subject=subject,
            kind=kind.value,
            governed=verdict.allowed,
            decision=verdict.decision.value,
            reasoning=tuple(verdict.reasoning_trace),
            references=tuple(
                Reference(target_type="knowledge", identifier=item.identity) for item in admitted
            ),
            selected_ids=tuple(item.identity for item in admitted),
            items=tuple(admitted),
        )
