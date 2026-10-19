"""Deterministic canary cohort (``nexus_integration.flags.CanaryCohort``, ADR-008 R4)."""

from __future__ import annotations

import pytest

from nexus_integration import CanaryCohort, DecisionIdentity


def _id(key: str) -> DecisionIdentity:
    return DecisionIdentity(owner="o", decision_id="d", correlation_identifier="c", cohort_key=key)


def test_zero_percent_includes_nobody() -> None:
    cohort = CanaryCohort(0)
    assert all(not cohort.includes(_id(f"k{i}")) for i in range(50))


def test_hundred_percent_includes_everybody() -> None:
    cohort = CanaryCohort(100)
    assert all(cohort.includes(_id(f"k{i}")) for i in range(50))


def test_membership_is_stable_for_a_key() -> None:
    cohort = CanaryCohort(50)
    key = "user-abc"
    first = cohort.includes(_id(key))
    assert all(cohort.includes(_id(key)) is first for _ in range(20))  # pinned, no randomness


def test_percentage_bounds_are_validated() -> None:
    with pytest.raises(ValueError):
        CanaryCohort(101)
    with pytest.raises(ValueError):
        CanaryCohort(-1)


def test_falls_back_to_decision_id_without_cohort_key() -> None:
    cohort = CanaryCohort(100)
    assert cohort.includes(DecisionIdentity(owner="o", decision_id="d", correlation_identifier="c"))
