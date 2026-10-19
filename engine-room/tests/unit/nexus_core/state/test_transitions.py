"""Structural-integrity tests for every per-object lifecycle machine."""

from __future__ import annotations

from itertools import pairwise

import pytest

from nexus_core.contracts.status import WorkPackageStatus
from nexus_core.state.lifecycle import (
    is_failure_state,
    is_terminal_state,
    validate_transition,
)
from nexus_core.state.machine import IllegalTransitionError
from nexus_core.state.transitions import MACHINES, machine_for

_EXPECTED_MACHINE_NAMES = {
    "intent",
    "goal",
    "context_package",
    "plan",
    "work_package",
    "execution_strategy",
    "execution_graph",
    "skill",
    "capability",
    "resource",
    "artifact",
    "observation",
    "event",
    "checkpoint",
    "policy",
    "knowledge",
    "reflection",
}


def test_all_seventeen_machines_present() -> None:
    assert set(MACHINES) == _EXPECTED_MACHINE_NAMES
    assert len(MACHINES) == 17


@pytest.mark.parametrize("name", sorted(_EXPECTED_MACHINE_NAMES))
def test_machine_structural_integrity(name: str) -> None:
    machine = MACHINES[name]
    states = machine.states

    # The initial state must be a known state.
    assert machine.initial in states

    # Every transition target must be a known state.
    for source, targets in machine.transitions.items():
        assert source in states
        for target in targets:
            assert target in states

    # Terminal states have no outgoing transitions.
    for terminal in machine.terminal:
        assert machine.allowed_targets(terminal) == frozenset(), name

    # Terminal and failure sets are subsets of states.
    assert machine.terminal <= states
    assert machine.failure <= states


def test_machine_for_unknown_raises_keyerror() -> None:
    with pytest.raises(KeyError) as exc_info:
        machine_for("nope")
    # The message lists known names.
    assert "nope" in str(exc_info.value)
    assert "goal" in str(exc_info.value)


def test_machine_for_known_returns_registered() -> None:
    assert machine_for("work_package") is MACHINES["work_package"]


def test_work_package_happy_path() -> None:
    path = [
        WorkPackageStatus.CREATED,
        WorkPackageStatus.READY,
        WorkPackageStatus.EXECUTING,
        WorkPackageStatus.COMPLETED,
    ]
    machine = machine_for("work_package")
    for source, target in pairwise(path):
        machine.validate_transition(source, target)  # does not raise


def test_work_package_illegal_move_raises() -> None:
    machine = machine_for("work_package")
    with pytest.raises(IllegalTransitionError):
        machine.validate_transition(WorkPackageStatus.COMPLETED, WorkPackageStatus.EXECUTING)


def test_is_terminal_state_helper() -> None:
    assert is_terminal_state("work_package", WorkPackageStatus.COMPLETED) is True
    assert is_terminal_state("work_package", WorkPackageStatus.EXECUTING) is False


def test_is_failure_state_helper() -> None:
    assert is_failure_state("work_package", WorkPackageStatus.FAILED) is True
    assert is_failure_state("work_package", WorkPackageStatus.COMPLETED) is False


def test_validate_transition_helper_legal() -> None:
    # Does not raise for a legal transition.
    validate_transition("work_package", WorkPackageStatus.CREATED, WorkPackageStatus.READY)


def test_validate_transition_helper_illegal() -> None:
    with pytest.raises(IllegalTransitionError):
        validate_transition("work_package", WorkPackageStatus.COMPLETED, WorkPackageStatus.READY)
