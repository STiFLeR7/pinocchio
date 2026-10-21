"""Persistence Policy -- the declarative bundle that governs acceptance (doc 04).

The policy is **pure data**: the Acceptance Engine (doc 05) is a pure function of ``(candidate,
existing Item + version chain, policy)``. It exists to enforce the program's central rule --
*Knowledge is never accepted solely because Reflection recommends it* -- by requiring independent
satisfaction of confidence, evidence-count, validated-provenance, and accepted-kind thresholds
(fail-closed; mirrors INV-24 and the platform "never trust a self-report" discipline).

Confidence uses the shared, earned :class:`~nexus_core.contracts.enums.ConfidenceLadder`.
Promotion is deterministic and count-derived (never learned, never AI-scored): accumulated
independent evidence raises an Item along the ladder, exactly like Reflection's confidence
(doc 26). The policy is versioned; every acceptance records the policy version it used, so any
decision is replayable against the exact policy that produced it.
"""

from __future__ import annotations

from nexus_core.contracts.base import ValueObject
from nexus_core.contracts.enums import ConfidenceLadder, KnowledgeType
from nexus_knowledge.vocabulary import DuplicateStrategy

# The earned ladder, lowest-to-highest -- the single source of ordering for the layer.
LADDER: tuple[ConfidenceLadder, ...] = (
    ConfidenceLadder.EXPERIMENTAL,
    ConfidenceLadder.OBSERVED,
    ConfidenceLadder.VALIDATED,
    ConfidenceLadder.PROVEN,
)


def ladder_index(level: ConfidenceLadder) -> int:
    """The 0-based rung of a confidence level (higher is stronger)."""
    return LADDER.index(level)


def at_least(level: ConfidenceLadder, floor: ConfidenceLadder) -> bool:
    """Whether ``level`` is at or above ``floor`` on the earned ladder."""
    return ladder_index(level) >= ladder_index(floor)


def confidence_for(evidence_count: int) -> ConfidenceLadder:
    """Map an accumulated independent-evidence count onto the earned ladder (deterministic).

    Mirrors Reflection's count-derived confidence (doc 26): a lone datum is ``Experimental``;
    corroboration raises it toward ``Proven``. This is the substrate of confidence *promotion*.
    """
    if evidence_count >= 5:
        return ConfidenceLadder.PROVEN
    if evidence_count >= 3:
        return ConfidenceLadder.VALIDATED
    if evidence_count == 2:
        return ConfidenceLadder.OBSERVED
    return ConfidenceLadder.EXPERIMENTAL


_ALL_KINDS: tuple[KnowledgeType, ...] = tuple(KnowledgeType)


class PersistencePolicy(ValueObject):
    """The immutable, versioned, deterministic acceptance configuration (doc 04)."""

    version: str = "persistence-policy/1"
    minimum_confidence: ConfidenceLadder = ConfidenceLadder.OBSERVED
    minimum_evidence: int = 1
    require_validated_provenance: bool = True
    accepted_kinds: tuple[KnowledgeType, ...] = _ALL_KINDS
    duplicate_strategy: DuplicateStrategy = DuplicateStrategy.EVOLVE
    confidence_promotion: bool = True
    serving_confidence_floor: ConfidenceLadder = ConfidenceLadder.EXPERIMENTAL
    rejection_is_terminal: bool = False
    owner: str = "knowledge-governance"
    # Optional freshness window for the deterministic maintenance pass (doc 11); seconds of the
    # recorded age beyond which an Active Item is expired. ``None`` disables TTL expiry.
    freshness_ttl_seconds: int | None = None

    def kind_accepted(self, kind: KnowledgeType) -> bool:
        """Whether ``kind`` is eligible for persistence under this policy."""
        return kind in self.accepted_kinds

    def promoted_confidence(
        self, asserted: ConfidenceLadder, evidence_count: int
    ) -> ConfidenceLadder:
        """The Item confidence after accumulation: the stronger of asserted vs count-derived.

        With ``confidence_promotion`` disabled the Item holds exactly the asserted level; enabled,
        it rises to whichever is higher on the ladder so corroboration can only strengthen, never
        weaken, an Item (contradiction drives deprecation, not a silent downgrade -- doc 10).
        """
        if not self.confidence_promotion:
            return asserted
        derived = confidence_for(evidence_count)
        return derived if ladder_index(derived) > ladder_index(asserted) else asserted


DEFAULT_PERSISTENCE_POLICY = PersistencePolicy()
"""The default policy: evidence-backed, validated provenance, promote on corroboration."""
