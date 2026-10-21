"""Policy events — the ``policy.*`` facts the Policy Engine emits.

Each fact is a canonical :class:`~nexus_core.domain.event.Event` with
``producer="policy"`` and ``source="nexus_policy"`` and a deterministic identifier,
so an evaluation replays identically (ADR-001; INV-17). The two facts:

- ``policy.registered`` — a policy was admitted to the registry (a lifecycle
  transition, INV-15); its payload embeds the serialized policy so the registry is a
  pure projection of the log (rebuildable after restart, ADR-007).
- ``policy.evaluated`` — a decision was produced (WP-P2.2). Exactly one per
  ``evaluate()``; correlated to its operation (INV-39). Replaying the ``policy.*``
  stream reconstructs the full authorization history without re-inference (INV-17).

Timestamps are the one captured-as-data, non-structural value (INV-17); their source
is injected so tests are reproducible and the value objects stay timestamp-free.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexus_core.contracts.base import Struct
from nexus_core.domain.event import Event

__all__ = [
    "POLICY_EVALUATED",
    "POLICY_REGISTERED",
    "build_event",
    "system_now",
]

POLICY_PRODUCER = "policy"
POLICY_SOURCE = "nexus_policy"
EVENT_VERSION = "1"

# --- canonical policy.* taxonomy (doc 20 *Policy Events*) ----------------------- #
POLICY_REGISTERED = "policy.registered"
POLICY_EVALUATED = "policy.evaluated"


def system_now() -> str:
    """Default timestamp source: wall-clock UTC, ISO-8601 (captured as event data)."""
    return datetime.now(UTC).isoformat()


def build_event(
    identifier: str,
    event_type: str,
    correlation_identifier: str,
    payload: Struct,
    timestamp: str,
    *,
    execution_identifier: str | None = None,
) -> Event:
    """Construct a canonical policy Event with deterministic identity."""
    return Event(
        identifier=identifier,
        type=event_type,
        version=EVENT_VERSION,
        timestamp=timestamp,
        producer=POLICY_PRODUCER,
        correlation_identifier=correlation_identifier,
        execution_identifier=execution_identifier,
        payload=payload,
        source=POLICY_SOURCE,
    )
