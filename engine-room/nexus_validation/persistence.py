"""Validation persistence — the repositories Validation writes its own outputs through.

Validation persists **only its own outputs**: the immutable Evidence it produces and the
Validation Reports it emits. It reuses the **Phase 2** ``InMemoryRepository`` mechanism
unchanged (no new persistence layer). It never writes the stores it *reads* from (the event
log, the Execution Result) — those are inputs, and Validation never mutates execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.persistence.interfaces import Repository
from nexus_infra import InMemoryRepository, Observability
from nexus_validation.evidence import Evidence
from nexus_validation.report import ValidationReport


@dataclass(frozen=True, slots=True)
class ValidationRepositories:
    """The repositories Validation persists its own outputs through (Phase 2, reused)."""

    reports: Repository[ValidationReport]
    evidence: Repository[Evidence]


def build_validation_repositories(
    observability: Observability | None = None,
) -> ValidationRepositories:
    """Wire the default validation repositories over the Phase 2 ``InMemoryRepository``."""
    return ValidationRepositories(
        reports=InMemoryRepository[ValidationReport](
            "validation_report", lambda r: r.identity, observability
        ),
        evidence=InMemoryRepository[Evidence]("evidence", lambda e: e.identity, observability),
    )
