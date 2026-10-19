"""Knowledge lifecycle -- deterministic transitions projected onto the frozen vocabularies.

The canonical doc-06 arc (Candidate -> Rejected | Accepted -> Active -> Superseded / Deprecated
-> Expired -> Archived) is named by :class:`~nexus_knowledge.vocabulary.KnowledgeLifecycle`.
The **frozen core contract carries no lifecycle field of its own** -- it exposes
``status`` (:class:`KnowledgeIngestionStatus`) and ``freshness`` (:class:`Freshness`). This module
is the total, deterministic projection between them, so the layer coins no new persisted state:

===================  ===========================  =================
doc-06 lifecycle     ``status``                   ``freshness``
===================  ===========================  =================
Accepted / Active    ``ACCEPTED``                 ``CURRENT``
Superseded           ``ACCEPTED``                 ``SUPERSEDED``
Deprecated           ``ACCEPTED``                 ``DEPRECATED``
Expired              ``ACCEPTED``                 ``HISTORICAL``
Archived             ``ACCEPTED``                 ``ARCHIVED``
Rejected             ``REJECTED``                 -- (no Item)
===================  ===========================  =================

Only ``Active`` (``CURRENT`` and above the serving floor) is served by default (doc 09/11); every
other state is retained and queryable but withheld from the understanding that steers new work.
Transitions are pure functions of evidence, relationships, recorded timestamps (as data, INV-17),
and policy -- never a background clock.
"""

from __future__ import annotations

from datetime import datetime

from nexus_core.contracts.enums import Freshness
from nexus_core.contracts.status import KnowledgeIngestionStatus
from nexus_core.domain.knowledge import Knowledge
from nexus_knowledge.policy import PersistencePolicy, at_least
from nexus_knowledge.vocabulary import KnowledgeLifecycle

_FRESHNESS_FOR: dict[KnowledgeLifecycle, Freshness] = {
    KnowledgeLifecycle.ACCEPTED: Freshness.CURRENT,
    KnowledgeLifecycle.ACTIVE: Freshness.CURRENT,
    KnowledgeLifecycle.SUPERSEDED: Freshness.SUPERSEDED,
    KnowledgeLifecycle.DEPRECATED: Freshness.DEPRECATED,
    KnowledgeLifecycle.EXPIRED: Freshness.HISTORICAL,
    KnowledgeLifecycle.ARCHIVED: Freshness.ARCHIVED,
}


def freshness_for(state: KnowledgeLifecycle) -> Freshness:
    """The persisted ``Freshness`` for an Item lifecycle state (doc 06/11)."""
    return _FRESHNESS_FOR[state]


def status_for(state: KnowledgeLifecycle) -> KnowledgeIngestionStatus:
    """The persisted ingestion ``status`` for a lifecycle state (doc 06)."""
    if state is KnowledgeLifecycle.REJECTED:
        return KnowledgeIngestionStatus.REJECTED
    return KnowledgeIngestionStatus.ACCEPTED


def lifecycle_of(item: Knowledge) -> KnowledgeLifecycle:
    """Recover the doc-06 lifecycle state from a persisted Item's ``(status, freshness)``."""
    if item.status is KnowledgeIngestionStatus.REJECTED:
        return KnowledgeLifecycle.REJECTED
    match item.freshness:
        case Freshness.SUPERSEDED:
            return KnowledgeLifecycle.SUPERSEDED
        case Freshness.DEPRECATED:
            return KnowledgeLifecycle.DEPRECATED
        case Freshness.HISTORICAL:
            return KnowledgeLifecycle.EXPIRED
        case Freshness.ARCHIVED:
            return KnowledgeLifecycle.ARCHIVED
        case _:
            return KnowledgeLifecycle.ACTIVE


def is_served(item: Knowledge, policy: PersistencePolicy) -> bool:
    """Whether an Item is served by default: ``Active`` and above the serving floor (doc 09)."""
    return item.freshness is Freshness.CURRENT and at_least(
        item.confidence, policy.serving_confidence_floor
    )


def is_stale(item_timestamp: str, as_of: str, ttl_seconds: int) -> bool:
    """Whether an Item's recorded age exceeds the freshness window (deterministic, doc 11).

    Timestamps are treated as **data** (INV-17): staleness is a pure function of the Item's
    recorded ``last_evolved`` time and an injected ``as_of`` time, evaluated at maintenance time
    rather than by a background clock. A missing/unparseable timestamp is never stale.
    """
    if not item_timestamp or not as_of:
        return False
    try:
        recorded = datetime.fromisoformat(item_timestamp)
        now = datetime.fromisoformat(as_of)
    except ValueError:
        return False
    return (now - recorded).total_seconds() > ttl_seconds
