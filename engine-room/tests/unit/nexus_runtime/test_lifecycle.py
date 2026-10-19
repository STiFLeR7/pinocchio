"""Unit tests for nexus_runtime.lifecycle.

Verifies the legal-transition table, is_legal, is_terminal, validate_transition,
and project_state — the ADR-001 event-stream projection.
"""

from __future__ import annotations

import pytest

from nexus_runtime.events import (
    RUNTIME_ALLOCATED,
    RUNTIME_ARTIFACT_EMITTED,
    RUNTIME_CANCELLED,
    RUNTIME_CAPABILITIES_MATCHED,
    RUNTIME_COMPLETED,
    RUNTIME_DESTROYED,
    RUNTIME_DISCOVERED,
    RUNTIME_FAILED,
    RUNTIME_OUTPUT,
    RUNTIME_PREPARED,
    RUNTIME_PROGRESS,
    RUNTIME_READY,
    RUNTIME_REGISTERED,
    RUNTIME_RELEASED,
    RUNTIME_SESSION_CREATED,
    RUNTIME_STARTED,
    RUNTIME_TIMED_OUT,
)
from nexus_runtime.lifecycle import (
    TERMINAL_STATES,
    IllegalTransitionError,
    is_legal,
    is_terminal,
    legal_transitions,
    project_state,
    validate_transition,
)
from nexus_runtime.vocabulary import RuntimeLifecycleState

_S = RuntimeLifecycleState

# --------------------------------------------------------------------------- #
# legal_transitions — table completeness                                        #
# --------------------------------------------------------------------------- #


def test_legal_transitions_from_created() -> None:
    result = legal_transitions(_S.CREATED)
    assert result == frozenset({_S.REGISTERED, _S.FAILED, _S.RELEASED})


def test_legal_transitions_from_registered() -> None:
    result = legal_transitions(_S.REGISTERED)
    assert result == frozenset({_S.ALLOCATED, _S.FAILED, _S.RELEASED})


def test_legal_transitions_from_allocated() -> None:
    result = legal_transitions(_S.ALLOCATED)
    assert result == frozenset({_S.PREPARED, _S.FAILED, _S.RELEASED})


def test_legal_transitions_from_prepared() -> None:
    result = legal_transitions(_S.PREPARED)
    assert result == frozenset({_S.READY, _S.FAILED, _S.RELEASED})


def test_legal_transitions_from_ready() -> None:
    result = legal_transitions(_S.READY)
    assert result == frozenset({_S.RUNNING, _S.RELEASED, _S.FAILED})


def test_legal_transitions_from_failed() -> None:
    result = legal_transitions(_S.FAILED)
    assert result == frozenset({_S.RELEASED, _S.DESTROYED})


def test_legal_transitions_from_running() -> None:
    result = legal_transitions(_S.RUNNING)
    assert result == frozenset({_S.COMPLETED, _S.CANCELLED, _S.FAILED})


def test_legal_transitions_from_completed() -> None:
    result = legal_transitions(_S.COMPLETED)
    assert result == frozenset({_S.DESTROYED})


def test_legal_transitions_from_cancelled() -> None:
    result = legal_transitions(_S.CANCELLED)
    assert result == frozenset({_S.DESTROYED})


def test_legal_transitions_from_destroyed_is_empty() -> None:
    result = legal_transitions(_S.DESTROYED)
    assert result == frozenset()


def test_legal_transitions_from_released_is_empty() -> None:
    result = legal_transitions(_S.RELEASED)
    assert result == frozenset()


# --------------------------------------------------------------------------- #
# is_legal — true cases                                                         #
# --------------------------------------------------------------------------- #


def test_is_legal_created_to_registered() -> None:
    assert is_legal(_S.CREATED, _S.REGISTERED) is True


def test_is_legal_created_to_failed() -> None:
    assert is_legal(_S.CREATED, _S.FAILED) is True


def test_is_legal_created_to_released() -> None:
    assert is_legal(_S.CREATED, _S.RELEASED) is True


def test_is_legal_registered_to_allocated() -> None:
    assert is_legal(_S.REGISTERED, _S.ALLOCATED) is True


def test_is_legal_allocated_to_prepared() -> None:
    assert is_legal(_S.ALLOCATED, _S.PREPARED) is True


def test_is_legal_prepared_to_ready() -> None:
    assert is_legal(_S.PREPARED, _S.READY) is True


def test_is_legal_ready_to_released() -> None:
    assert is_legal(_S.READY, _S.RELEASED) is True


def test_is_legal_failed_to_released() -> None:
    assert is_legal(_S.FAILED, _S.RELEASED) is True


# --------------------------------------------------------------------------- #
# is_legal — false cases                                                        #
# --------------------------------------------------------------------------- #


def test_is_legal_created_to_allocated_is_false() -> None:
    assert is_legal(_S.CREATED, _S.ALLOCATED) is False


def test_is_legal_released_to_anything_is_false() -> None:
    for target in _S:
        assert is_legal(_S.RELEASED, target) is False


def test_is_legal_ready_to_prepared_is_false() -> None:
    assert is_legal(_S.READY, _S.PREPARED) is False


def test_is_legal_allocated_to_registered_is_false() -> None:
    assert is_legal(_S.ALLOCATED, _S.REGISTERED) is False


def test_is_legal_failed_to_ready_is_false() -> None:
    assert is_legal(_S.FAILED, _S.READY) is False


# --------------------------------------------------------------------------- #
# is_terminal                                                                   #
# --------------------------------------------------------------------------- #


def test_is_terminal_released_is_true() -> None:
    assert is_terminal(_S.RELEASED) is True


def test_is_terminal_created_is_false() -> None:
    assert is_terminal(_S.CREATED) is False


def test_is_terminal_registered_is_false() -> None:
    assert is_terminal(_S.REGISTERED) is False


def test_is_terminal_allocated_is_false() -> None:
    assert is_terminal(_S.ALLOCATED) is False


def test_is_terminal_prepared_is_false() -> None:
    assert is_terminal(_S.PREPARED) is False


def test_is_terminal_ready_is_false() -> None:
    assert is_terminal(_S.READY) is False


def test_is_terminal_failed_is_false() -> None:
    assert is_terminal(_S.FAILED) is False


def test_terminal_states_are_released_and_destroyed() -> None:
    assert frozenset({_S.RELEASED, _S.DESTROYED}) == TERMINAL_STATES


def test_is_terminal_destroyed_is_true() -> None:
    assert is_terminal(_S.DESTROYED) is True


def test_is_terminal_running_is_false() -> None:
    assert is_terminal(_S.RUNNING) is False


def test_is_terminal_completed_is_false() -> None:
    assert is_terminal(_S.COMPLETED) is False


def test_is_terminal_cancelled_is_false() -> None:
    assert is_terminal(_S.CANCELLED) is False


# --------------------------------------------------------------------------- #
# validate_transition — legal (no raise)                                        #
# --------------------------------------------------------------------------- #


def test_validate_transition_created_to_registered_does_not_raise() -> None:
    validate_transition(_S.CREATED, _S.REGISTERED)  # no raise


def test_validate_transition_registered_to_allocated_does_not_raise() -> None:
    validate_transition(_S.REGISTERED, _S.ALLOCATED)  # no raise


def test_validate_transition_allocated_to_prepared_does_not_raise() -> None:
    validate_transition(_S.ALLOCATED, _S.PREPARED)  # no raise


def test_validate_transition_prepared_to_ready_does_not_raise() -> None:
    validate_transition(_S.PREPARED, _S.READY)  # no raise


def test_validate_transition_ready_to_released_does_not_raise() -> None:
    validate_transition(_S.READY, _S.RELEASED)  # no raise


def test_validate_transition_created_to_failed_does_not_raise() -> None:
    validate_transition(_S.CREATED, _S.FAILED)  # no raise


def test_validate_transition_failed_to_released_does_not_raise() -> None:
    validate_transition(_S.FAILED, _S.RELEASED)  # no raise


# --------------------------------------------------------------------------- #
# validate_transition — illegal (raises IllegalTransitionError)                 #
# --------------------------------------------------------------------------- #


def test_validate_transition_raises_for_created_to_allocated() -> None:
    with pytest.raises(IllegalTransitionError):
        validate_transition(_S.CREATED, _S.ALLOCATED)


def test_validate_transition_raises_for_released_to_created() -> None:
    with pytest.raises(IllegalTransitionError):
        validate_transition(_S.RELEASED, _S.CREATED)


def test_validate_transition_raises_for_ready_to_allocated() -> None:
    with pytest.raises(IllegalTransitionError):
        validate_transition(_S.READY, _S.ALLOCATED)


def test_validate_transition_raises_for_failed_to_ready() -> None:
    with pytest.raises(IllegalTransitionError):
        validate_transition(_S.FAILED, _S.READY)


def test_illegal_transition_error_is_exception_subclass() -> None:
    with pytest.raises(IllegalTransitionError) as exc_info:
        validate_transition(_S.RELEASED, _S.CREATED)
    assert isinstance(exc_info.value, Exception)


def test_validate_transition_error_message_contains_state_names() -> None:
    with pytest.raises(IllegalTransitionError) as exc_info:
        validate_transition(_S.RELEASED, _S.CREATED)
    msg = str(exc_info.value)
    assert "released" in msg
    assert "created" in msg


# --------------------------------------------------------------------------- #
# project_state — empty stream yields CREATED                                   #
# --------------------------------------------------------------------------- #


def test_project_state_empty_stream_returns_created() -> None:
    assert project_state(()) == _S.CREATED


# --------------------------------------------------------------------------- #
# project_state — non-lifecycle events are skipped                              #
# --------------------------------------------------------------------------- #


def test_project_state_skips_capabilities_matched() -> None:
    # runtime.capabilities_matched has no state mapping — should be skipped
    result = project_state((RUNTIME_CAPABILITIES_MATCHED,))
    assert result == _S.CREATED


def test_project_state_skips_registered_observer_event() -> None:
    # runtime.registered is a registry-plane event not in _STATE_FOR_EVENT
    result = project_state((RUNTIME_REGISTERED,))
    assert result == _S.CREATED


def test_project_state_skips_unknown_event_type() -> None:
    result = project_state(("unknown.event.type",))
    assert result == _S.CREATED


def test_project_state_skips_non_lifecycle_events_mixed_in() -> None:
    # Non-lifecycle events interspersed should be transparent
    result = project_state(
        (
            RUNTIME_SESSION_CREATED,
            RUNTIME_CAPABILITIES_MATCHED,
            RUNTIME_DISCOVERED,
        )
    )
    # session_created → CREATED (initial, already there, skipped by target is state)
    # capabilities_matched → skipped
    # candidates_resolved → REGISTERED
    assert result == _S.REGISTERED


# --------------------------------------------------------------------------- #
# project_state — full happy-path stream                                        #
# --------------------------------------------------------------------------- #


def test_project_state_full_preparation_stream() -> None:
    stream = (
        RUNTIME_SESSION_CREATED,  # → CREATED (skipped: already CREATED)
        RUNTIME_DISCOVERED,  # → REGISTERED
        RUNTIME_ALLOCATED,  # → ALLOCATED
        RUNTIME_PREPARED,  # → PREPARED
        RUNTIME_READY,  # → READY
    )
    assert project_state(stream) == _S.READY


def test_project_state_reaches_released_from_ready() -> None:
    stream = (
        RUNTIME_SESSION_CREATED,
        RUNTIME_DISCOVERED,
        RUNTIME_ALLOCATED,
        RUNTIME_PREPARED,
        RUNTIME_READY,
        RUNTIME_RELEASED,
    )
    assert project_state(stream) == _S.RELEASED


def test_project_state_reaches_failed() -> None:
    stream = (
        RUNTIME_SESSION_CREATED,
        RUNTIME_DISCOVERED,
        RUNTIME_FAILED,
    )
    assert project_state(stream) == _S.FAILED


def test_project_state_failed_then_released() -> None:
    stream = (
        RUNTIME_SESSION_CREATED,
        RUNTIME_FAILED,
        RUNTIME_RELEASED,
    )
    assert project_state(stream) == _S.RELEASED


# --------------------------------------------------------------------------- #
# project_state — idempotent: repeating the same driving event is a no-op      #
# --------------------------------------------------------------------------- #


def test_project_state_repeated_session_created_event_is_idempotent() -> None:
    # RUNTIME_SESSION_CREATED maps to CREATED; already in CREATED → target is state → skip
    result = project_state(
        (RUNTIME_SESSION_CREATED, RUNTIME_SESSION_CREATED, RUNTIME_SESSION_CREATED)
    )
    assert result == _S.CREATED


def test_project_state_repeated_discovered_after_registered_is_idempotent() -> None:
    # First DISCOVERED transitions CREATED→REGISTERED; second is target==state → skip
    result = project_state(
        (
            RUNTIME_DISCOVERED,
            RUNTIME_DISCOVERED,
        )
    )
    assert result == _S.REGISTERED


# --------------------------------------------------------------------------- #
# project_state — raises on illegal event sequence                              #
# --------------------------------------------------------------------------- #


def test_project_state_raises_on_illegal_sequence_allocated_before_registered() -> None:
    # CREATED → ALLOCATED is illegal
    with pytest.raises(IllegalTransitionError):
        project_state((RUNTIME_ALLOCATED,))


def test_project_state_raises_on_illegal_sequence_ready_before_prepared() -> None:
    with pytest.raises(IllegalTransitionError):
        project_state(
            (
                RUNTIME_DISCOVERED,  # → REGISTERED
                RUNTIME_ALLOCATED,  # → ALLOCATED
                RUNTIME_READY,  # illegal: ALLOCATED → READY
            )
        )


def test_project_state_raises_on_transition_from_released() -> None:
    # After RELEASED (terminal), any lifecycle event is illegal
    with pytest.raises(IllegalTransitionError):
        project_state(
            (
                RUNTIME_DISCOVERED,
                RUNTIME_ALLOCATED,
                RUNTIME_PREPARED,
                RUNTIME_READY,
                RUNTIME_RELEASED,
                RUNTIME_FAILED,  # illegal: RELEASED → FAILED
            )
        )


# --------------------------------------------------------------------------- #
# Execution slice — is_legal (doc 07 §4)                                        #
# --------------------------------------------------------------------------- #


def test_is_legal_ready_to_running() -> None:
    assert is_legal(_S.READY, _S.RUNNING) is True


def test_is_legal_running_to_completed() -> None:
    assert is_legal(_S.RUNNING, _S.COMPLETED) is True


def test_is_legal_running_to_cancelled() -> None:
    assert is_legal(_S.RUNNING, _S.CANCELLED) is True


def test_is_legal_running_to_failed() -> None:
    assert is_legal(_S.RUNNING, _S.FAILED) is True


def test_is_legal_completed_to_destroyed() -> None:
    assert is_legal(_S.COMPLETED, _S.DESTROYED) is True


def test_is_legal_cancelled_to_destroyed() -> None:
    assert is_legal(_S.CANCELLED, _S.DESTROYED) is True


def test_is_legal_failed_to_destroyed() -> None:
    assert is_legal(_S.FAILED, _S.DESTROYED) is True


def test_is_legal_running_to_ready_is_false() -> None:
    assert is_legal(_S.RUNNING, _S.READY) is False


def test_is_legal_ready_to_completed_is_false() -> None:
    # Ready must pass through Running; it cannot jump straight to Completed
    assert is_legal(_S.READY, _S.COMPLETED) is False


def test_is_legal_completed_to_running_is_false() -> None:
    assert is_legal(_S.COMPLETED, _S.RUNNING) is False


def test_is_legal_destroyed_to_anything_is_false() -> None:
    for target in _S:
        assert is_legal(_S.DESTROYED, target) is False


# --------------------------------------------------------------------------- #
# Execution slice — validate_transition                                         #
# --------------------------------------------------------------------------- #


def test_validate_transition_ready_to_running_does_not_raise() -> None:
    validate_transition(_S.READY, _S.RUNNING)  # no raise


def test_validate_transition_running_to_completed_does_not_raise() -> None:
    validate_transition(_S.RUNNING, _S.COMPLETED)  # no raise


def test_validate_transition_completed_to_destroyed_does_not_raise() -> None:
    validate_transition(_S.COMPLETED, _S.DESTROYED)  # no raise


def test_validate_transition_raises_for_running_to_destroyed() -> None:
    # Running must pass through a terminal execution state before teardown
    with pytest.raises(IllegalTransitionError):
        validate_transition(_S.RUNNING, _S.DESTROYED)


def test_validate_transition_raises_for_destroyed_to_running() -> None:
    with pytest.raises(IllegalTransitionError):
        validate_transition(_S.DESTROYED, _S.RUNNING)


# --------------------------------------------------------------------------- #
# Execution slice — project_state over full session streams                     #
# --------------------------------------------------------------------------- #

_PREP = (
    RUNTIME_SESSION_CREATED,
    RUNTIME_DISCOVERED,
    RUNTIME_ALLOCATED,
    RUNTIME_PREPARED,
    RUNTIME_READY,
)


def test_project_state_full_execution_stream_completed_then_destroyed() -> None:
    stream = (
        *_PREP,
        RUNTIME_STARTED,  # → RUNNING
        RUNTIME_OUTPUT,  # non-lifecycle, skipped
        RUNTIME_PROGRESS,  # non-lifecycle, skipped
        RUNTIME_ARTIFACT_EMITTED,  # non-lifecycle, skipped
        RUNTIME_COMPLETED,  # → COMPLETED
        RUNTIME_RELEASED,  # non-lifecycle here? released drives RELEASED — see below
    )
    # runtime.released maps to RELEASED, but COMPLETED → RELEASED is illegal; the
    # teardown terminal after a run is DESTROYED. So the engine emits runtime.destroyed
    # as the state-driving teardown event; runtime.released is the allocation fact.
    # This stream therefore stops before RELEASED to assert the COMPLETED projection.
    assert project_state(stream[:-1]) == _S.COMPLETED


def test_project_state_execution_completed_to_destroyed() -> None:
    stream = (*_PREP, RUNTIME_STARTED, RUNTIME_COMPLETED, RUNTIME_DESTROYED)
    assert project_state(stream) == _S.DESTROYED


def test_project_state_execution_cancelled_to_destroyed() -> None:
    stream = (*_PREP, RUNTIME_STARTED, RUNTIME_CANCELLED, RUNTIME_DESTROYED)
    assert project_state(stream) == _S.DESTROYED


def test_project_state_execution_failed_to_destroyed() -> None:
    stream = (*_PREP, RUNTIME_STARTED, RUNTIME_FAILED, RUNTIME_DESTROYED)
    assert project_state(stream) == _S.DESTROYED


def test_project_state_skips_execution_non_lifecycle_events() -> None:
    stream = (*_PREP, RUNTIME_STARTED, RUNTIME_TIMED_OUT, RUNTIME_OUTPUT)
    # timed_out and output carry no state transition; state stays RUNNING
    assert project_state(stream) == _S.RUNNING


def test_project_state_raises_on_ready_to_completed_without_running() -> None:
    with pytest.raises(IllegalTransitionError):
        project_state((*_PREP, RUNTIME_COMPLETED))  # READY → COMPLETED is illegal
