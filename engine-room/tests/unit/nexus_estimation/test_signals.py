"""Signal extraction from immutable facts (``nexus_estimation.signals``)."""

from __future__ import annotations

from nexus_estimation.signals import merge_signals, signals_from_work_package
from tests.unit.nexus_estimation.fixtures import make_work_package


def test_signals_from_work_package_are_structural_and_deterministic() -> None:
    wp = make_work_package(dependencies=4, skills=3)
    a = signals_from_work_package(wp)
    b = signals_from_work_package(wp)
    assert a == b  # deterministic
    assert a["dependency_count"] == 4.0
    assert a["skill_count"] == 3.0
    assert a["objective_size"] == float(len(wp.objective))


def test_merge_signals_later_overrides_earlier() -> None:
    merged = merge_signals({"a": 1.0, "b": 2.0}, {"b": 9.0, "c": 3.0})
    assert merged == {"a": 1.0, "b": 9.0, "c": 3.0}
