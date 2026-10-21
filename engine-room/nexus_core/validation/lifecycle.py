"""Lifecycle validation — legal states and transitions per object.

Validates that an object's current state (a projection of the event log) is a
member of its lifecycle machine, and provides transition validation that wraps
the state machine's ``IllegalTransitionError`` as a ``LifecycleViolation``.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel

from nexus_core.state.machine import IllegalTransitionError
from nexus_core.state.transitions import MACHINES, machine_for
from nexus_core.validation.errors import ContractViolation, LifecycleViolation
from nexus_core.validation.framework import ValidationIssue, Validator, object_name_of

# Field names that, in order, may carry an object's current lifecycle state.
_STATE_FIELDS = ("status", "stage", "allocation_state")


def _current_state(obj: BaseModel) -> Enum | None:
    for field_name in _STATE_FIELDS:
        if field_name in type(obj).model_fields:
            value = getattr(obj, field_name)
            if isinstance(value, Enum):
                return value
    return None


class LifecycleValidator(Validator):
    """Validates current state membership and (on demand) transition legality."""

    category: ClassVar[str] = "lifecycle"
    exception: ClassVar[type[ContractViolation]] = LifecycleViolation

    def issues(self, obj: BaseModel) -> Iterator[ValidationIssue]:
        name = object_name_of(obj)
        machine = MACHINES.get(name)
        if machine is None:
            return
        state = _current_state(obj)
        if state is not None and state not in machine.states:
            yield ValidationIssue(
                category=self.category,
                object_name=name,
                message=f"state {state!r} is not a member of the {name} lifecycle",
            )

    def validate_transition(self, object_name: str, source: Enum, target: Enum) -> None:
        """Raise ``LifecycleViolation`` unless ``source -> target`` is legal."""
        try:
            machine_for(object_name).validate_transition(source, target)
        except IllegalTransitionError as exc:
            raise LifecycleViolation(object_name, str(exc)) from exc
