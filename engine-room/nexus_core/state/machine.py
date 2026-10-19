"""A generic, immutable state machine over an ``Enum`` of states.

The machine validates whether a transition is legal. It performs no I/O, owns no
state of any object, and never *drives* transitions — it only answers "is this
transition allowed?" Driving transitions is the job of the (later-phase)
projection engine that folds events; this primitive gives it the rules.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum


class IllegalTransitionError(Exception):
    """Raised when a state transition is not permitted by the machine.

    Carries the machine name, the source and target states, and the set of
    legal targets, so callers fail fast with a complete, explainable message
    (no silent correction).
    """

    def __init__(
        self, machine_name: str, source: Enum, target: Enum, allowed: frozenset[Enum]
    ) -> None:
        self.machine_name = machine_name
        self.source = source
        self.target = target
        self.allowed = allowed
        allowed_render = ", ".join(sorted(a.value for a in allowed)) or "(none — terminal)"
        super().__init__(
            f"{machine_name}: illegal transition {source.value!r} -> {target.value!r}; "
            f"allowed from {source.value!r}: {allowed_render}"
        )


@dataclass(frozen=True, slots=True)
class StateMachine[E: Enum]:
    """An immutable transition specification for one object's lifecycle.

    - ``transitions`` maps each state to the set of states it may move to.
    - ``initial`` is the only legal entry state.
    - ``terminal`` are success/closed states with no outgoing transitions.
    - ``failure`` are failure states (a subset relationship with the table, not
      with ``terminal``; a failure state may still transition, e.g. to recovery).
    """

    name: str
    transitions: Mapping[E, frozenset[E]]
    initial: E
    terminal: frozenset[E] = field(default_factory=frozenset)
    failure: frozenset[E] = field(default_factory=frozenset)

    @property
    def states(self) -> frozenset[E]:
        """Every state known to the machine."""
        known: set[E] = set(self.transitions)
        for targets in self.transitions.values():
            known.update(targets)
        return frozenset(known)

    def allowed_targets(self, source: E) -> frozenset[E]:
        """The states reachable in one step from ``source`` (empty if terminal/unknown)."""
        return self.transitions.get(source, frozenset())

    def can_transition(self, source: E, target: E) -> bool:
        """True iff moving ``source -> target`` is permitted."""
        return target in self.allowed_targets(source)

    def validate_transition(self, source: E, target: E) -> None:
        """Raise :class:`IllegalTransitionError` unless the transition is legal."""
        if not self.can_transition(source, target):
            raise IllegalTransitionError(self.name, source, target, self.allowed_targets(source))

    def is_terminal(self, state: E) -> bool:
        return state in self.terminal

    def is_failure(self, state: E) -> bool:
        return state in self.failure

    def is_initial(self, state: E) -> bool:
        return state == self.initial
