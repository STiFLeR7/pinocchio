"""The unified ``CoreState`` model (doc 24) and per-transition ``StateMetadata``.

Every per-object lifecycle (Intent, Goal, Plan, …) is a specialized projection
of this unified model. ``CoreState`` itself is the canonical reference machine;
the invalid transitions called out in doc 24 (e.g. ``Completed -> Active``) are
absent from its table and therefore rejected by ``StateMachine``.
"""

from __future__ import annotations

from enum import StrEnum

from nexus_core.contracts.base import ValueObject
from nexus_core.state.machine import StateMachine


class CoreState(StrEnum):
    """Unified operational lifecycle states (doc 24)."""

    CREATED = "created"
    READY = "ready"
    ACTIVE = "active"
    WAITING = "waiting"
    PAUSED = "paused"
    RECOVERING = "recovering"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


# State categories (doc 24).
ACTIVE_STATES: frozenset[CoreState] = frozenset(
    {
        CoreState.READY,
        CoreState.ACTIVE,
        CoreState.WAITING,
        CoreState.PAUSED,
        CoreState.RECOVERING,
        CoreState.VALIDATING,
    }
)
TERMINAL_STATES: frozenset[CoreState] = frozenset(
    {CoreState.COMPLETED, CoreState.CANCELLED, CoreState.ARCHIVED}
)
FAILURE_STATES: frozenset[CoreState] = frozenset({CoreState.FAILED})


# Allowed transitions for the unified lifecycle. The doc-24 invalid transitions
# (Completed->Active, Archived->Recovering, Cancelled->Active) are simply not
# present and are therefore rejected.
_CORE_TRANSITIONS: dict[CoreState, frozenset[CoreState]] = {
    CoreState.CREATED: frozenset({CoreState.READY, CoreState.CANCELLED}),
    CoreState.READY: frozenset({CoreState.ACTIVE, CoreState.CANCELLED}),
    CoreState.ACTIVE: frozenset(
        {
            CoreState.WAITING,
            CoreState.PAUSED,
            CoreState.VALIDATING,
            CoreState.COMPLETED,
            CoreState.FAILED,
            CoreState.CANCELLED,
        }
    ),
    CoreState.WAITING: frozenset({CoreState.ACTIVE, CoreState.FAILED, CoreState.CANCELLED}),
    CoreState.PAUSED: frozenset({CoreState.ACTIVE, CoreState.FAILED, CoreState.CANCELLED}),
    CoreState.RECOVERING: frozenset({CoreState.READY, CoreState.FAILED, CoreState.CANCELLED}),
    CoreState.VALIDATING: frozenset({CoreState.COMPLETED, CoreState.FAILED}),
    CoreState.FAILED: frozenset({CoreState.RECOVERING}),
    CoreState.COMPLETED: frozenset({CoreState.ARCHIVED}),
    CoreState.CANCELLED: frozenset(),
    CoreState.ARCHIVED: frozenset(),
}

CORE_STATE_MACHINE: StateMachine[CoreState] = StateMachine(
    name="CoreState",
    transitions=_CORE_TRANSITIONS,
    initial=CoreState.CREATED,
    terminal=TERMINAL_STATES,
    failure=FAILURE_STATES,
)


class StateMetadata(ValueObject):
    """The metadata recorded on every state transition (doc 24).

    This is the descriptive record of a transition; the transition itself is an
    Event (INV-15). ``StateMetadata`` carries no provider/runtime internals.
    """

    timestamp: str
    previous_state: str | None
    current_state: str
    reason: str
    responsible_component: str
    correlation_identifier: str
    execution_identifier: str | None = None
