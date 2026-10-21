"""Unit tests for the unified ``CoreState`` machine and ``StateMetadata``."""

from __future__ import annotations

from itertools import pairwise

import pytest
from pydantic import ValidationError

from nexus_core.state.core_state import (
    ACTIVE_STATES,
    CORE_STATE_MACHINE,
    FAILURE_STATES,
    TERMINAL_STATES,
    CoreState,
    StateMetadata,
)
from nexus_core.state.machine import IllegalTransitionError


def test_happy_path_all_legal() -> None:
    """CREATED -> READY -> ACTIVE -> VALIDATING -> COMPLETED -> ARCHIVED."""
    path = [
        CoreState.CREATED,
        CoreState.READY,
        CoreState.ACTIVE,
        CoreState.VALIDATING,
        CoreState.COMPLETED,
        CoreState.ARCHIVED,
    ]
    for source, target in pairwise(path):
        assert CORE_STATE_MACHINE.can_transition(source, target) is True
        CORE_STATE_MACHINE.validate_transition(source, target)  # does not raise


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (CoreState.COMPLETED, CoreState.ACTIVE),
        (CoreState.ARCHIVED, CoreState.RECOVERING),
        (CoreState.CANCELLED, CoreState.ACTIVE),
    ],
)
def test_documented_invalid_transitions_rejected(source: CoreState, target: CoreState) -> None:
    assert CORE_STATE_MACHINE.can_transition(source, target) is False
    with pytest.raises(IllegalTransitionError):
        CORE_STATE_MACHINE.validate_transition(source, target)


def test_failure_recovery_path_legal() -> None:
    """ACTIVE -> FAILED -> RECOVERING -> READY."""
    path = [CoreState.ACTIVE, CoreState.FAILED, CoreState.RECOVERING, CoreState.READY]
    for source, target in pairwise(path):
        CORE_STATE_MACHINE.validate_transition(source, target)  # does not raise


def test_initial_state() -> None:
    assert CORE_STATE_MACHINE.is_initial(CoreState.CREATED) is True
    assert CORE_STATE_MACHINE.initial is CoreState.CREATED


def test_category_sets_partition_correctly() -> None:
    assert ACTIVE_STATES.isdisjoint(TERMINAL_STATES)
    assert ACTIVE_STATES.isdisjoint(FAILURE_STATES)
    assert TERMINAL_STATES.isdisjoint(FAILURE_STATES)
    # Every member of every category is a member of the machine.
    for state in ACTIVE_STATES | TERMINAL_STATES | FAILURE_STATES:
        assert state in CORE_STATE_MACHINE.states


def test_terminal_and_failure_sets_match_machine() -> None:
    assert CORE_STATE_MACHINE.terminal == TERMINAL_STATES
    assert CORE_STATE_MACHINE.failure == FAILURE_STATES
    for state in TERMINAL_STATES:
        assert CORE_STATE_MACHINE.is_terminal(state) is True
    for state in FAILURE_STATES:
        assert CORE_STATE_MACHINE.is_failure(state) is True


def test_terminal_states_have_no_outgoing_except_completed() -> None:
    # CANCELLED and ARCHIVED are dead-ends; COMPLETED still moves to ARCHIVED.
    assert CORE_STATE_MACHINE.allowed_targets(CoreState.CANCELLED) == frozenset()
    assert CORE_STATE_MACHINE.allowed_targets(CoreState.ARCHIVED) == frozenset()
    assert CORE_STATE_MACHINE.allowed_targets(CoreState.COMPLETED) == frozenset(
        {CoreState.ARCHIVED}
    )


def _build_metadata() -> StateMetadata:
    return StateMetadata(
        timestamp="2026-06-29T00:00:00Z",
        previous_state="ready",
        current_state="active",
        reason="execution started",
        responsible_component="orchestration",
        correlation_identifier="corr-1",
        execution_identifier="exec-1",
    )


def test_state_metadata_constructs() -> None:
    meta = _build_metadata()
    assert meta.previous_state == "ready"
    assert meta.current_state == "active"
    assert meta.execution_identifier == "exec-1"


def test_state_metadata_optional_fields_default() -> None:
    meta = StateMetadata(
        timestamp="2026-06-29T00:00:00Z",
        previous_state=None,
        current_state="created",
        reason="created",
        responsible_component="intent",
        correlation_identifier="corr-1",
    )
    assert meta.previous_state is None
    assert meta.execution_identifier is None


def test_state_metadata_is_frozen() -> None:
    meta = _build_metadata()
    with pytest.raises(ValidationError):
        meta.reason = "changed"  # type: ignore[misc]
