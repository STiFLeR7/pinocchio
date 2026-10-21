"""Execution-history persistence — the repository Execution History writes its own profiles through.

It persists **only its own output** (the immutable ExecutionHistoryProfile), never a copy of the
operational history it reads — history is reconstructed from the authoritative log, never duplicated.
It reuses the P1 ``InMemoryRepository`` mechanism unchanged; over a durable infrastructure context
the same profiles ride the durable substrate (ADR-007). It writes no store it reads from.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.persistence.interfaces import Repository
from nexus_history.model import ExecutionHistoryProfile
from nexus_infra import InMemoryRepository, Observability


@dataclass(frozen=True, slots=True)
class HistoryRepositories:
    """The repository Execution History persists its profiles through (P1, reused)."""

    profiles: Repository[ExecutionHistoryProfile]


def build_history_repositories(
    observability: Observability | None = None,
) -> HistoryRepositories:
    """Wire the default execution-history-profile store over the P1 ``InMemoryRepository``."""
    return HistoryRepositories(
        profiles=InMemoryRepository[ExecutionHistoryProfile](
            "execution_history_profile", lambda p: p.identity, observability
        )
    )
