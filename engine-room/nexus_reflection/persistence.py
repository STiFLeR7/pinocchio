"""Reflection persistence — the repositories Reflection writes its own outputs through.

Reflection persists **only its own outputs**: the immutable Reflection Reports and the
Operational Patterns it produces. It reuses the **Phase 2** ``InMemoryRepository`` mechanism
unchanged (no new persistence layer). It never writes the stores it *reads* from (the Execution
Results, Validation Reports, Recovery Plans, event log) — those are inputs, and Reflection never
modifies collected data (doc 26 *Evidence First*). It does **not** persist Knowledge Candidates
as Knowledge (INV-25) — candidates travel inside the Report as advisory outputs only.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.persistence.interfaces import Repository
from nexus_infra import InMemoryRepository, Observability
from nexus_reflection.patterns import OperationalPattern
from nexus_reflection.report import ReflectionReport


@dataclass(frozen=True, slots=True)
class ReflectionRepositories:
    """The repositories Reflection persists its own outputs through (Phase 2, reused)."""

    reports: Repository[ReflectionReport]
    patterns: Repository[OperationalPattern]


def build_reflection_repositories(
    observability: Observability | None = None,
) -> ReflectionRepositories:
    """Wire the default reflection repositories over the Phase 2 ``InMemoryRepository``."""
    return ReflectionRepositories(
        reports=InMemoryRepository[ReflectionReport](
            "reflection_report", lambda r: r.identity, observability
        ),
        patterns=InMemoryRepository[OperationalPattern](
            "operational_pattern", lambda p: p.identity, observability
        ),
    )
