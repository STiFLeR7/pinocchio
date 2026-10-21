"""The Execution → Validation seam (P13/F-3) — project the actuator's output into Execution Results.

The Execution Actuator (P11) drives the plan and yields one immutable :class:`ExecutionState` (a
projection of the ``execution.*`` log). Validation consumes the frozen
:class:`~nexus_execution.results.ExecutionResult` — *what happened to one process* — one per executed
node. This module bridges the two **additively**, reconstructing each node's ExecutionResult from the
node's projected state plus the durable runtime log. No incumbent is modified; the actuator's contract
is untouched (it is read, not extended).

The one subtlety it closes: Validation's artifact-corroboration rule (INV-20) reads the independent
``runtime.artifact_emitted`` events keyed by the node's *execution-session* scope — an identity the
actuator does not surface. The bridge recovers it from the runtime's frozen ``runtime.session_created``
fact (which carries ``node``), so the reconstructed ExecutionResult's ``session_ref`` matches the log
and corroboration resolves exactly as it does for the incumbent per-session loop. Because the engine's
teardown always reaches ``Destroyed`` (any outcome), ``final_state`` is deterministically ``DESTROYED``.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference
from nexus_core.domain.event import Event
from nexus_execution.actuation import ExecutionState, NodeState, NodeStatus
from nexus_execution.results import ExecutionResult
from nexus_execution.signals import TerminalOutcome
from nexus_runtime.events import RUNTIME_COMPLETED, RUNTIME_FAILED, RUNTIME_SESSION_CREATED
from nexus_runtime.vocabulary import RUNTIME_SESSION_TARGET_TYPE, RuntimeLifecycleState

_DISPATCHED = (NodeStatus.COMPLETED, NodeStatus.FAILED)


def execution_results(
    state: ExecutionState, events: tuple[Event, ...]
) -> tuple[ExecutionResult, ...]:
    """Reconstruct one ExecutionResult per executed node (the frozen contract Validation consumes)."""
    node_scope = _node_scopes(events, state.identity)
    results: list[ExecutionResult] = []
    for node in state.nodes:
        if node.status not in _DISPATCHED:
            continue  # never dispatched (pending / blocked / waiting) — no process to validate
        scope = node_scope.get(node.node, node.node)
        results.append(_result(node, scope, events))
    return tuple(results)


def _result(node: NodeState, scope: str, events: tuple[Event, ...]) -> ExecutionResult:
    outcome = TerminalOutcome(node.outcome) if node.outcome else TerminalOutcome.FAILED
    terminal = _terminal_fact(scope, events)
    return ExecutionResult(
        session_ref=Reference(target_type=RUNTIME_SESSION_TARGET_TYPE, identifier=scope),
        work_package_ref=node.work_package_ref,
        runtime_ref=node.runtime_ref,
        outcome=outcome,
        final_state=RuntimeLifecycleState.DESTROYED,  # the engine's teardown always reaches Destroyed
        exit_status=terminal.get("exit_status"),
        artifact_refs=node.artifact_refs,
        cleanup_ok=True,
        error_class=terminal.get("error_class"),
        error_owner=terminal.get("owner"),
        error_detail=node.error_detail or terminal.get("detail"),
    )


def _node_scopes(events: tuple[Event, ...], session_identity: str) -> dict[str, str]:
    """Map each node id to its execution-session scope via the frozen ``runtime.session_created`` fact.

    ``events`` is the *entire* durable log (every goal ever run in this process), so the scan is
    restricted to facts stamped for this ``session_identity`` (RC2) — otherwise two goals whose plans
    both produce a node with the same key would overwrite each other's entry in ``mapping``, handing
    Validation the wrong (or a since-overwritten) goal's runtime scope for a node id shared by both.
    """
    mapping: dict[str, str] = {}
    marker = f"-{session_identity}-"
    for event in events:
        if event.type != RUNTIME_SESSION_CREATED:
            continue
        # Event ids are the runtime's frozen ``evt-{scope}-created-0000`` scheme (created is seq 0).
        scope = event.identifier.removeprefix("evt-").removesuffix("-created-0000")
        if marker not in f"-{scope}-":
            continue  # a different execution session's runtime fact
        node = event.payload.get("node")
        if node is None:
            continue
        mapping[str(node)] = scope
    return mapping


def _terminal_fact(scope: str, events: tuple[Event, ...]) -> dict[str, object]:
    """Read the node's terminal runtime fact (exit status / error) from the durable log, if present."""
    prefix = f"evt-{scope}-"
    for event in events:
        if not event.identifier.startswith(prefix):
            continue
        if event.type in (RUNTIME_COMPLETED, RUNTIME_FAILED):
            return dict(event.payload)
    return {}
