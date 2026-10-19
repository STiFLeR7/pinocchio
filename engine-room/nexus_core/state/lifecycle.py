"""Lifecycle interfaces and helpers built on the per-object state machines.

These are *interfaces and pure helpers*, not an orchestration engine. They let a
later-phase projection (which folds events into current state) consult the legal
transitions for any object, and let domain models expose their lifecycle
uniformly.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable

from nexus_core.state.machine import StateMachine
from nexus_core.state.transitions import machine_for


@runtime_checkable
class Lifecycle(Protocol):
    """An object that exposes a current lifecycle state.

    Implemented structurally by domain models that carry a ``status``/state
    field. The ``lifecycle_name`` ties the object to its :class:`StateMachine`.
    """

    @property
    def lifecycle_name(self) -> str:
        """The logical object name registered in ``MACHINES`` (e.g. ``"goal"``)."""
        ...

    @property
    def current_state(self) -> Enum:
        """The object's current lifecycle state (a projection of the event log)."""
        ...


def is_terminal_state(object_name: str, state: Enum) -> bool:
    """True iff ``state`` is a terminal state for the named object's lifecycle."""
    return machine_for(object_name).is_terminal(state)


def is_failure_state(object_name: str, state: Enum) -> bool:
    """True iff ``state`` is a failure state for the named object's lifecycle."""
    return machine_for(object_name).is_failure(state)


def validate_transition(object_name: str, source: Enum, target: Enum) -> None:
    """Raise ``IllegalTransitionError`` unless ``source -> target`` is legal."""
    machine_for(object_name).validate_transition(source, target)


def machine(object_name: str) -> StateMachine[Any]:
    """Convenience accessor for an object's lifecycle machine."""
    return machine_for(object_name)
