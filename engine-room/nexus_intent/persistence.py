"""Intent persistence — the repository Intent Resolution writes its own analyses through.

Intent Resolution persists **only its own output** (the immutable IntentAnalysis, which bundles the
frozen Intent + Goal). It reuses the P1 ``InMemoryRepository`` mechanism unchanged (no new
persistence layer); over a durable infrastructure context the same analyses ride the durable
substrate (ADR-007). It writes no store it reads from.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.persistence.interfaces import Repository
from nexus_infra import InMemoryRepository, Observability
from nexus_intent.model import IntentAnalysis


@dataclass(frozen=True, slots=True)
class IntentRepositories:
    """The repository Intent Resolution persists its analyses through (P1, reused)."""

    analyses: Repository[IntentAnalysis]


def build_intent_repositories(
    observability: Observability | None = None,
) -> IntentRepositories:
    """Wire the default intent repository over the P1 ``InMemoryRepository``."""
    return IntentRepositories(
        analyses=InMemoryRepository[IntentAnalysis](
            "intent_analysis", lambda a: a.identity, observability
        )
    )
