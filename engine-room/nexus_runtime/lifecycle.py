"""Runtime lifecycle — the Phase 8A preparation state machine and its transition guard.

Defines the legal transitions between :class:`RuntimeLifecycleState` values, rejects
illegal ones fail-fast (the platform's no-silent-correction rule, mirroring the core
state machine's ``IllegalTransitionError`` discipline), and folds a ``runtime.*`` event
stream back into the current state — proving the ADR-001 property that session state is a
*projection* of the log, not an independently mutated field (doc 07 §5).

This realizes doc 07's canonical machine across both slices:

* **preparation** (Phase 8A): ``Created → Registered → Allocated → Prepared → Ready``,
  with ``Released`` as the preparation-abandon terminal and ``Failed`` reachable from any
  non-terminal preparation state (a preparation may be abandoned before handoff — doc 07 §3);
* **execution + teardown** (Execution Engine phase): ``Ready → Running → Completed /
  Cancelled / Failed → Destroyed`` (doc 07 §4).

``Released`` remains the terminal for a session that never ran (preparation abandon);
``Destroyed`` is the teardown terminal for a session that ran (doc 07 §6). The suspend/
resume/approval states (``Paused / Waiting``) are still deferred — the minimal Execution
Engine drives no pause, wait, or resume — so they are not modeled here.
"""

from __future__ import annotations

from collections.abc import Mapping

from nexus_runtime.events import (
    RUNTIME_ALLOCATED,
    RUNTIME_CANCELLED,
    RUNTIME_COMPLETED,
    RUNTIME_DESTROYED,
    RUNTIME_DISCOVERED,
    RUNTIME_FAILED,
    RUNTIME_PREPARED,
    RUNTIME_READY,
    RUNTIME_RELEASED,
    RUNTIME_SESSION_CREATED,
    RUNTIME_STARTED,
)
from nexus_runtime.vocabulary import RuntimeLifecycleState

_S = RuntimeLifecycleState


class IllegalTransitionError(Exception):
    """A requested lifecycle transition is not permitted by the state machine."""


_LEGAL: Mapping[RuntimeLifecycleState, frozenset[RuntimeLifecycleState]] = {
    # preparation slice (Phase 8A)
    _S.CREATED: frozenset({_S.REGISTERED, _S.FAILED, _S.RELEASED}),
    _S.REGISTERED: frozenset({_S.ALLOCATED, _S.FAILED, _S.RELEASED}),
    _S.ALLOCATED: frozenset({_S.PREPARED, _S.FAILED, _S.RELEASED}),
    _S.PREPARED: frozenset({_S.READY, _S.FAILED, _S.RELEASED}),
    # handoff: Ready may start (→ Running) or be abandoned (→ Released) or error
    _S.READY: frozenset({_S.RUNNING, _S.RELEASED, _S.FAILED}),
    # execution slice (Execution Engine phase) — doc 07 §4
    _S.RUNNING: frozenset({_S.COMPLETED, _S.CANCELLED, _S.FAILED}),
    _S.COMPLETED: frozenset({_S.DESTROYED}),
    _S.CANCELLED: frozenset({_S.DESTROYED}),
    # Failed tears down to Released (never ran) or Destroyed (ran) — doc 07 §6
    _S.FAILED: frozenset({_S.RELEASED, _S.DESTROYED}),
    # teardown terminals
    _S.RELEASED: frozenset(),
    _S.DESTROYED: frozenset(),
}

TERMINAL_STATES: frozenset[RuntimeLifecycleState] = frozenset({_S.RELEASED, _S.DESTROYED})

# The event that *drives* each state on entry (used by the projection fold).
_STATE_FOR_EVENT: Mapping[str, RuntimeLifecycleState] = {
    RUNTIME_SESSION_CREATED: _S.CREATED,
    RUNTIME_DISCOVERED: _S.REGISTERED,
    RUNTIME_ALLOCATED: _S.ALLOCATED,
    RUNTIME_PREPARED: _S.PREPARED,
    RUNTIME_READY: _S.READY,
    RUNTIME_STARTED: _S.RUNNING,
    RUNTIME_COMPLETED: _S.COMPLETED,
    RUNTIME_CANCELLED: _S.CANCELLED,
    RUNTIME_FAILED: _S.FAILED,
    RUNTIME_RELEASED: _S.RELEASED,
    RUNTIME_DESTROYED: _S.DESTROYED,
}


def legal_transitions(state: RuntimeLifecycleState) -> frozenset[RuntimeLifecycleState]:
    """The states reachable in one step from ``state``."""
    return _LEGAL[state]


def is_legal(current: RuntimeLifecycleState, target: RuntimeLifecycleState) -> bool:
    """Whether ``current → target`` is a permitted transition."""
    return target in _LEGAL[current]


def is_terminal(state: RuntimeLifecycleState) -> bool:
    """Whether ``state`` admits no further transition."""
    return state in TERMINAL_STATES


def validate_transition(current: RuntimeLifecycleState, target: RuntimeLifecycleState) -> None:
    """Raise :class:`IllegalTransitionError` unless ``current → target`` is legal."""
    if not is_legal(current, target):
        raise IllegalTransitionError(
            f"illegal runtime lifecycle transition: {current.value} -> {target.value}"
        )


def project_state(event_types: tuple[str, ...]) -> RuntimeLifecycleState:
    """Fold an ordered ``runtime.*`` event-type stream into the current state (ADR-001).

    Non-lifecycle events (e.g. ``runtime.capabilities_matched``, ``runtime.registered``)
    carry no state transition and are skipped. Replaying the same stream always yields the
    same state (idempotent, deterministic — INV-16).
    """
    state = RuntimeLifecycleState.CREATED
    for event_type in event_types:
        target = _STATE_FOR_EVENT.get(event_type)
        if target is None or target is state:
            continue
        validate_transition(state, target)
        state = target
    return state
