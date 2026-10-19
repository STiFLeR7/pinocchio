"""Estimation persistence — the repository Estimation writes its own reports through.

Estimation persists **only its own output** (the immutable Estimation Report). It reuses the
P1 ``InMemoryRepository`` mechanism unchanged (no new persistence layer); over a durable
infrastructure context the same reports ride the durable substrate. It never writes the stores
it reads from — its inputs are immutable facts it never mutates.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.persistence.interfaces import Repository
from nexus_estimation.model import EstimationReport
from nexus_infra import InMemoryRepository, Observability


@dataclass(frozen=True, slots=True)
class EstimationRepositories:
    """The repository Estimation persists its reports through (P1, reused)."""

    reports: Repository[EstimationReport]


def build_estimation_repositories(
    observability: Observability | None = None,
) -> EstimationRepositories:
    """Wire the default estimation repository over the P1 ``InMemoryRepository``."""
    return EstimationRepositories(
        reports=InMemoryRepository[EstimationReport](
            "estimation_report", lambda r: r.identity, observability
        )
    )
