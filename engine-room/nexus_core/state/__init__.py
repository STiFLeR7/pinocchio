"""State primitives — the unified lifecycle, a generic state machine, and the
per-object transition tables.

Per ADR-001, a domain object's current state is a **projection** of the
append-only event log, not an independently stored authoritative machine. This
package provides the *rules* for which transitions are legal (so a projection
that applies events can reject illegal transitions, INV-15), and the unified
``CoreState`` every per-object lifecycle specializes.

No orchestration, no execution engine, no scheduling — pure transition logic.
"""

from nexus_core.state.core_state import (
    CORE_STATE_MACHINE,
    CoreState,
    StateMetadata,
)
from nexus_core.state.lifecycle import Lifecycle, is_terminal_state
from nexus_core.state.machine import IllegalTransitionError, StateMachine
from nexus_core.state.transitions import (
    MACHINES,
    machine_for,
)

__all__ = [
    "CORE_STATE_MACHINE",
    "MACHINES",
    "CoreState",
    "IllegalTransitionError",
    "Lifecycle",
    "StateMachine",
    "StateMetadata",
    "is_terminal_state",
    "machine_for",
]
