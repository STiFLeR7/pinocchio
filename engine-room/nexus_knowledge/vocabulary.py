"""Knowledge vocabularies — the closed enumerations and reference tags of the layer.

Knowledge is the **persistence layer**: it decides whether an advisory Knowledge Candidate
becomes durable understanding, and it serves that understanding read-only to consumers (docs
``docs/v2/knowledge/`` 00-10). It never executes, analyses, validates, retries, recovers, or
evaluates governance policy (INV-25/INV-26/INV-28).

The durable **Knowledge Item is the frozen core contract** :class:`nexus_core.domain.Knowledge`
(doc 03 -- "without inventing a competing model"); its identity is the deterministic Knowledge
Subject Key (``ids.subject_key``), its confidence is the shared ``ConfidenceLadder``, its
freshness the shared ``Freshness`` ladder, and its ingestion status ``KnowledgeIngestionStatus``.
Only the closed vocabularies that are *Knowledge-layer* concepts -- the acceptance decision, the
lifecycle states, the duplicate strategy, the named rejection reasons, and the canonical
``Reference`` ``target_type`` strings -- live here.
"""

from __future__ import annotations

from enum import StrEnum


class KnowledgeDecision(StrEnum):
    """The one deterministic outcome the Acceptance Engine returns (doc 05)."""

    ACCEPT_CREATE = "accept_create"
    ACCEPT_EVOLVE = "accept_evolve"
    MERGE = "merge"
    REJECT = "reject"


class KnowledgeLifecycle(StrEnum):
    """The canonical lifecycle states of a knowledge unit (doc 06).

    ``Candidate``/``Rejected`` are ingestion-boundary states; ``Accepted``..``Archived`` are
    Item lifecycle states. They project onto the frozen core ``Freshness`` and
    ``KnowledgeIngestionStatus`` vocabularies via :mod:`nexus_knowledge.lifecycle` -- this layer
    coins no new *persisted* state, only names the doc-06 arc for events and version records.
    """

    CANDIDATE = "candidate"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class DuplicateStrategy(StrEnum):
    """How a Subject-Key match is resolved (Persistence Policy ``duplicate_strategy``, doc 04)."""

    EVOLVE = "evolve"
    MERGE = "merge"
    REJECT_AS_DUPLICATE = "reject_as_duplicate"


# --- named rejection reasons (recorded as the failed requirement, INV-31) ------- #
REASON_INSUFFICIENT_EVIDENCE = "insufficient_evidence"
REASON_PROVENANCE_NOT_VALIDATED = "provenance_not_validated"
REASON_BELOW_MINIMUM_CONFIDENCE = "below_minimum_confidence"
REASON_KIND_NOT_ACCEPTED = "kind_not_accepted"
REASON_DUPLICATE = "duplicate"
REASON_REJECTION_TERMINAL = "rejection_terminal"


# --- canonical Reference target_type strings ----------------------------------- #
# The durable Item is the core Knowledge contract; its repository name (and the string other
# layers already use to reference Knowledge) is ``knowledge``.
KNOWLEDGE_ITEM_TARGET_TYPE = "knowledge"
KNOWLEDGE_VERSION_TARGET_TYPE = "knowledge_version"
# Same string as Reflection's candidate: it is the *same* boundary object, consumed by value.
KNOWLEDGE_CANDIDATE_TARGET_TYPE = "knowledge_candidate"
# Evidence origins that count as *validated* provenance (doc 05 / INV-24): a Validation Report
# or validated Evidence -- never bare execution output.
VALIDATED_PROVENANCE_TARGET_TYPES = frozenset({"validation_report", "evidence", "observation"})
