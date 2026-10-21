"""Unit tests for the generic, immutable :class:`StateMachine` primitive."""

from __future__ import annotations

from enum import StrEnum

import pytest

from nexus_core.state.machine import IllegalTransitionError, StateMachine


class _Light(StrEnum):
    """A tiny throwaway lifecycle used to exercise the generic mechanics."""

    OFF = "off"
    ON = "on"
    BROKEN = "broken"


def _build_machine() -> StateMachine[_Light]:
    return StateMachine(
        name="Light",
        transitions={
            _Light.OFF: frozenset({_Light.ON, _Light.BROKEN}),
            _Light.ON: frozenset({_Light.OFF, _Light.BROKEN}),
            _Light.BROKEN: frozenset(),
        },
        initial=_Light.OFF,
        terminal=frozenset({_Light.BROKEN}),
        failure=frozenset({_Light.BROKEN}),
    )


def test_states_collects_sources_and_targets() -> None:
    machine = _build_machine()
    assert machine.states == frozenset({_Light.OFF, _Light.ON, _Light.BROKEN})


def test_allowed_targets() -> None:
    machine = _build_machine()
    assert machine.allowed_targets(_Light.OFF) == frozenset({_Light.ON, _Light.BROKEN})
    assert machine.allowed_targets(_Light.BROKEN) == frozenset()


def test_can_transition() -> None:
    machine = _build_machine()
    assert machine.can_transition(_Light.OFF, _Light.ON) is True
    assert machine.can_transition(_Light.ON, _Light.OFF) is True
    assert machine.can_transition(_Light.BROKEN, _Light.ON) is False


def test_validate_transition_legal_is_silent() -> None:
    machine = _build_machine()
    machine.validate_transition(_Light.OFF, _Light.ON)  # does not raise


def test_validate_transition_illegal_raises_with_message() -> None:
    machine = _build_machine()
    with pytest.raises(IllegalTransitionError) as exc_info:
        machine.validate_transition(_Light.BROKEN, _Light.ON)
    error = exc_info.value
    assert error.machine_name == "Light"
    assert error.source is _Light.BROKEN
    assert error.target is _Light.ON
    assert error.allowed == frozenset()
    rendered = str(error)
    assert "Light" in rendered
    assert "broken" in rendered
    assert "on" in rendered
    assert "(none — terminal)" in rendered


def test_validate_transition_illegal_renders_allowed_targets() -> None:
    machine = _build_machine()
    with pytest.raises(IllegalTransitionError) as exc_info:
        machine.validate_transition(_Light.OFF, _Light.OFF)
    rendered = str(exc_info.value)
    assert "broken" in rendered
    assert "on" in rendered


def test_is_terminal() -> None:
    machine = _build_machine()
    assert machine.is_terminal(_Light.BROKEN) is True
    assert machine.is_terminal(_Light.OFF) is False


def test_is_failure() -> None:
    machine = _build_machine()
    assert machine.is_failure(_Light.BROKEN) is True
    assert machine.is_failure(_Light.ON) is False


def test_is_initial() -> None:
    machine = _build_machine()
    assert machine.is_initial(_Light.OFF) is True
    assert machine.is_initial(_Light.ON) is False


def test_allowed_targets_unknown_source_is_empty() -> None:
    machine = StateMachine(
        name="Partial",
        transitions={_Light.OFF: frozenset({_Light.ON})},
        initial=_Light.OFF,
    )
    # ON is a target but not a key — treated as having no outgoing transitions.
    assert machine.allowed_targets(_Light.ON) == frozenset()
    assert machine.can_transition(_Light.ON, _Light.OFF) is False


def test_machine_is_frozen() -> None:
    machine = _build_machine()
    with pytest.raises((AttributeError, TypeError)):
        machine.name = "Other"  # type: ignore[misc]
