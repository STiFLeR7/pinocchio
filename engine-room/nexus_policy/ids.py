"""Deterministic identifier derivation for policy events.

Every identifier is a pure function of the fact it names — no clock, no counter, no
randomness — so evaluation is reproducible and idempotent (INV-16/INV-17). A decision
event's id is a content hash of its payload: re-evaluating an identical request that
yields an identical decision produces the *same* id (an idempotent no-op in the log),
while any different outcome produces a new id. The ``pol-`` marker keeps policy events
from colliding with other producers in the shared, correlated store.
"""

from __future__ import annotations

from nexus_core.contracts.base import Struct
from nexus_infra import content_hash


def decision_event_id(correlation_identifier: str, payload: Struct) -> str:
    """A correlation-scoped, content-addressed id for one ``policy.evaluated`` fact."""
    return f"evt-{correlation_identifier}-pol-{content_hash(payload)[:16]}"


def registered_event_id(identity: str, version: str) -> str:
    """A stable id for one ``policy.registered`` fact (idempotent on re-registration)."""
    return f"evt-policy-registered-{identity}-{version}"
