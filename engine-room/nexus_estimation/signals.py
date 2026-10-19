"""Signal extraction — turning immutable facts into deterministic numeric signals.

Estimation consumes **only immutable facts** and never mutable runtime state or AI-generated
opinions. This module extracts numeric signals from those facts: work-package metadata (the
frozen :class:`~nexus_core.domain.work_package.WorkPackage`), dependency-graph counts,
repository metrics, versioned historical statistics, runtime capabilities, and declared
constraints. Extraction is pure and deterministic — the same WorkPackage always yields the
same signals — and it reads only structural facts, never opinions.
"""

from __future__ import annotations

from collections.abc import Mapping

from nexus_core.domain.work_package import WorkPackage


def signals_from_work_package(work_package: WorkPackage) -> dict[str, float]:
    """Deterministic structural signals from an immutable Work Package (metadata only)."""
    return {
        "objective_size": float(len(work_package.objective)),
        "skill_count": float(len(work_package.skills)),
        "input_count": float(len(work_package.inputs)),
        "output_count": float(len(work_package.outputs)),
        "constraint_count": float(len(work_package.constraints)),
        "dependency_count": float(len(work_package.dependencies)),
        "resource_count": float(len(work_package.resources)),
    }


def merge_signals(*sources: Mapping[str, float]) -> dict[str, float]:
    """Merge signal maps deterministically (later sources override earlier on key collision)."""
    merged: dict[str, float] = {}
    for source in sources:
        for name in sorted(source):
            merged[name] = float(source[name])
    return merged
