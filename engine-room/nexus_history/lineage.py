"""Knowledge lineage — reconstruct the derivation edges recorded in ``knowledge.*`` facts.

Lineage is a **deterministic reconstruction**, not an inference: it counts candidate/item lifecycle
facts and records the derivation edges the log actually carries (candidate → item; supersedes →
item). It reads events by their recorded fields only and matches on the ``knowledge.*`` type strings
— it imports no knowledge subsystem, so Execution History stays a grounding leaf (core + infra only).
"""

from __future__ import annotations

from collections.abc import Sequence

from nexus_core.domain.event import Event
from nexus_history.model import KnowledgeLineage
from nexus_history.retrieval import first


def build_lineage(events: Sequence[Event]) -> KnowledgeLineage:
    """Reconstruct knowledge lineage (counts + derivation edges) from ``knowledge.*`` facts."""
    candidates = accepted = rejected = created = evolved = 0
    edges: set[tuple[str, str]] = set()

    for e in events:
        if not e.type.startswith("knowledge."):
            continue
        payload = e.payload or {}
        suffix = e.type.split(".", 1)[1]

        if suffix == "candidate_received":
            candidates += 1
        elif suffix == "candidate_accepted":
            accepted += 1
        elif suffix == "candidate_rejected":
            rejected += 1
        elif suffix == "item_created":
            created += 1
        elif suffix in ("item_evolved", "item_superseded"):
            evolved += 1

        target = first(payload, "subject_key") or e.identifier
        source = first(payload, "candidate", "supersedes", "superseded_by")
        if source is not None:
            edges.add((str(source), str(target)))

    return KnowledgeLineage(
        candidates_received=candidates,
        accepted=accepted,
        rejected=rejected,
        items_created=created,
        items_evolved=evolved,
        edges=tuple(sorted(edges)),
    )
