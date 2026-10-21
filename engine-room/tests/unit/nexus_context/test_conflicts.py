"""Unit tests for :class:`~nexus_context.conflict_detector.ConflictDetector`.

The detector surfaces (never resolves) four conflict kinds — duplicate,
contradiction, stale, missing_dependency — over the normalized item set, and
returns them in a deterministic ``(kind, category, key)`` order. These tests pin
each kind, the no-conflict case, deterministic ordering across kinds, the absent
``supersedes`` target case, immutability of :class:`Conflict`, and the tuple
return contract.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_context.categories import ConflictKind, ContextCategory, ContextSource
from nexus_context.conflict_detector import ConflictDetector
from nexus_context.normalizer import Normalizer
from nexus_context.requests import Conflict, ContextItem, RawContextFragment
from tests.unit.nexus_context.helpers import fragment, request


def _items(*fragments: RawContextFragment) -> tuple[ContextItem, ...]:
    """Normalize fragments into the canonical item set the detector consumes."""
    return Normalizer().normalize(fragments)


def test_detect_returns_tuple() -> None:
    items = _items(fragment("alpha"))
    result = ConflictDetector().detect(items, request())
    assert isinstance(result, tuple)


def test_unique_key_yields_no_conflict() -> None:
    items = _items(fragment("alpha"), fragment("beta"))
    conflicts = ConflictDetector().detect(items, request())
    assert conflicts == ()


def test_duplicate_conflict() -> None:
    frag_a = fragment("shared", source=ContextSource.WORKSPACE, payload={"v": 1})
    frag_b = fragment("shared", source=ContextSource.RUNTIME, payload={"v": 1})
    items = _items(frag_a, frag_b)

    conflicts = ConflictDetector().detect(items, request())

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.kind is ConflictKind.DUPLICATE
    assert conflict.category is ContextCategory.WORKSPACE
    assert conflict.key == "shared"
    assert conflict.item_refs == tuple(sorted(item.identity for item in items))
    assert conflict.detail == {"sources": ["runtime", "workspace"]}


def test_contradiction_conflict() -> None:
    frag_a = fragment("shared", source=ContextSource.WORKSPACE, payload={"v": 1})
    frag_b = fragment("shared", source=ContextSource.RUNTIME, payload={"v": 2})
    items = _items(frag_a, frag_b)

    conflicts = ConflictDetector().detect(items, request())

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.kind is ConflictKind.CONTRADICTION
    assert conflict.category is ContextCategory.WORKSPACE
    assert conflict.key == "shared"
    assert conflict.item_refs == tuple(sorted(item.identity for item in items))
    assert conflict.detail == {"sources": ["runtime", "workspace"]}


def test_stale_conflict() -> None:
    superseded = fragment("old", source=ContextSource.WORKSPACE)
    superseding = fragment("new", source=ContextSource.RUNTIME, supersedes=("old",))
    items = _items(superseded, superseding)
    by_key = {item.key: item for item in items}

    conflicts = ConflictDetector().detect(items, request())

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.kind is ConflictKind.STALE
    assert conflict.category is ContextCategory.WORKSPACE
    assert conflict.key == "old"
    assert conflict.detail == {"superseded_by": by_key["new"].identity}
    assert conflict.item_refs == tuple(sorted((by_key["new"].identity, by_key["old"].identity)))


def test_stale_supersedes_absent_key_yields_no_conflict() -> None:
    superseding = fragment("new", supersedes=("ghost",))
    items = _items(superseding)

    conflicts = ConflictDetector().detect(items, request())

    assert conflicts == ()


def test_missing_dependency_conflict() -> None:
    items = _items(fragment("present"))

    conflicts = ConflictDetector().detect(items, request(declared_dependencies=("absent",)))

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.kind is ConflictKind.MISSING_DEPENDENCY
    assert conflict.category is None
    assert conflict.key == "absent"
    assert conflict.item_refs == ()


def test_declared_dependency_present_yields_no_conflict() -> None:
    items = _items(fragment("present"))

    conflicts = ConflictDetector().detect(items, request(declared_dependencies=("present",)))

    assert conflicts == ()


def test_deterministic_ordering_across_kinds() -> None:
    # contradiction on ("shared")
    dup_a = fragment("shared", source=ContextSource.WORKSPACE, payload={"v": 1})
    dup_b = fragment("shared", source=ContextSource.RUNTIME, payload={"v": 2})
    # stale: "new" supersedes present "old"
    superseded = fragment("old", source=ContextSource.WORKSPACE)
    superseding = fragment("new", source=ContextSource.RUNTIME, supersedes=("old",))
    items = _items(dup_a, dup_b, superseded, superseding)

    conflicts = ConflictDetector().detect(items, request(declared_dependencies=("missing-dep",)))

    kinds = [conflict.kind for conflict in conflicts]
    assert kinds == [
        ConflictKind.CONTRADICTION,
        ConflictKind.MISSING_DEPENDENCY,
        ConflictKind.STALE,
    ]
    sort_keys = [(c.kind.value, c.category.value if c.category else "", c.key) for c in conflicts]
    assert sort_keys == sorted(sort_keys)


def test_conflict_is_frozen() -> None:
    conflict = Conflict(
        kind=ConflictKind.MISSING_DEPENDENCY,
        category=None,
        key="absent",
    )
    with pytest.raises(ValidationError):
        conflict.key = "other"  # type: ignore[misc]
