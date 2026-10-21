"""Determinism-class comparison + diff engine (``nexus_integration.comparator``, ADR-008 §3.3)."""

from __future__ import annotations

import pytest

from nexus_integration import (
    ComparatorRegistry,
    DeterminismClass,
    DeterministicComparator,
    DiffVerdict,
    ExternalStateComparator,
    ProbabilisticComparator,
    default_comparators,
)


def test_deterministic_exact_match() -> None:
    assert DeterministicComparator().compare({"v": 1}, {"v": 1})[0] is DiffVerdict.MATCH
    assert DeterministicComparator().compare({"v": 1}, {"v": 2})[0] is DiffVerdict.MISMATCH


def test_probabilistic_never_exact_match_without_hook() -> None:
    # Different tokens must NOT produce a false mismatch — UNDETERMINED, route to human.
    verdict, detail = ProbabilisticComparator().compare("Deploy the app", "deploy application")
    assert verdict is DiffVerdict.UNDETERMINED
    assert "human" in detail["reason"]


def test_probabilistic_equivalence_band() -> None:
    band = ProbabilisticComparator(equivalence=lambda a, b: a.lower().strip() == b.lower().strip())
    assert band.compare("Deploy", "deploy ")[0] is DiffVerdict.EQUIVALENT
    assert band.compare("deploy", "delete")[0] is DiffVerdict.MISMATCH


def test_external_state_is_evidence_aware() -> None:
    # Default evidence is equality; an override accepts legitimate external drift.
    tolerant = ExternalStateComparator(evidence=lambda a, b: abs(a - b) <= 1)
    assert tolerant.compare(10, 11)[0] is DiffVerdict.EQUIVALENT
    assert tolerant.compare(10, 20)[0] is DiffVerdict.MISMATCH


def test_registry_is_extensible() -> None:
    registry = default_comparators()
    assert isinstance(registry.for_class(DeterminismClass.DETERMINISTIC), DeterministicComparator)
    registry.register(DeterminismClass.PROBABILISTIC, ProbabilisticComparator(lambda a, b: True))
    assert (
        registry.for_class(DeterminismClass.PROBABILISTIC).compare("x", "y")[0]
        is DiffVerdict.EQUIVALENT
    )


def test_registry_raises_for_unregistered_class() -> None:
    with pytest.raises(KeyError):
        ComparatorRegistry().for_class(DeterminismClass.DETERMINISTIC)


def test_diff_generation_is_deterministic() -> None:
    comparator = DeterministicComparator()
    assert comparator.compare({"a": 1}, {"a": 2}) == comparator.compare({"a": 1}, {"a": 2})
