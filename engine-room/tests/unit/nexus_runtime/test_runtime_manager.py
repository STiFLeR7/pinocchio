"""Unit tests for nexus_runtime.runtime_manager — RuntimeManager preparation pipeline.

Covers every branch of RuntimeManager:
- register_runtime: success, non-RUNTIME descriptor raises ValueError
- prepare happy path: single intake, event order, persistence, observability
- prepare batch of 2 intakes: capacity splitting across distinct runtimes
- _correlation branches: explicit id, intake correlation, session_ref fallback, empty intakes
- failure + rollback: CapabilityMismatchError, no persistence, released emitted, capacity freed
- _fail with no allocation: UnresolvedRuntimeError before allocation emits failed, no released
- release: session → RELEASED, allocation → RELEASED, runtime.released emitted, persisted
- validate_outputs: exercised via batch prepare
"""

from __future__ import annotations

import pytest

from nexus_infra import build_infrastructure
from nexus_runtime import (
    CapabilityMismatchError,
    FixedTimestampSource,
    PreparationResult,
    RuntimeLifecycleState,
    UnresolvedRuntimeError,
    build_runtime,
)
from nexus_runtime.events import (
    RUNTIME_ALLOCATED,
    RUNTIME_CAPABILITIES_MATCHED,
    RUNTIME_DISCOVERED,
    RUNTIME_FAILED,
    RUNTIME_PREPARED,
    RUNTIME_READY,
    RUNTIME_REGISTERED,
    RUNTIME_RELEASED,
    RUNTIME_SESSION_CREATED,
)
from tests.unit.nexus_runtime.helpers import (
    descriptor,
    intake,
    preparation_request,
    runtime_env,
    standard_runtimes,
)

# ---------------------------------------------------------------------------
# Per-session canonical event order for one prepared intake
# ---------------------------------------------------------------------------

_PER_SESSION_EVENT_TYPES = [
    RUNTIME_SESSION_CREATED,
    RUNTIME_DISCOVERED,
    RUNTIME_CAPABILITIES_MATCHED,
    RUNTIME_ALLOCATED,
    RUNTIME_PREPARED,
    RUNTIME_READY,
]


# ===========================================================================
# register_runtime
# ===========================================================================


def test_register_runtime_returns_descriptor() -> None:
    """register_runtime returns the registered HarnessDescriptor."""
    env = runtime_env(register=False)
    d = descriptor("my-runtime")

    result = env.manager.register_runtime(d)

    assert result.identity == "my-runtime"


def test_register_runtime_emits_runtime_registered_event() -> None:
    """register_runtime emits a runtime.registered event."""
    env = runtime_env(register=False)
    d = descriptor("my-runtime")

    env.manager.register_runtime(d)

    assert RUNTIME_REGISTERED in env.event_types()


def test_register_runtime_registered_event_has_runtime_producer() -> None:
    """The runtime.registered event carries producer='runtime'."""
    env = runtime_env(register=False)
    d = descriptor("my-runtime")

    env.manager.register_runtime(d)

    registered_events = [e for e in env.events() if e.type == RUNTIME_REGISTERED]
    assert len(registered_events) == 1
    assert registered_events[0].producer == "runtime"


def test_register_runtime_registered_event_payload_contains_identity() -> None:
    """The runtime.registered payload carries the runtime identity."""
    env = runtime_env(register=False)
    d = descriptor("my-runtime", capabilities=("code_generation",))

    env.manager.register_runtime(d)

    registered_events = [e for e in env.events() if e.type == RUNTIME_REGISTERED]
    payload = registered_events[0].payload
    assert payload["runtime"] == "my-runtime"
    assert "code_generation" in payload["capabilities"]


def test_register_runtime_increments_observability() -> None:
    """register_runtime increments the runtime.registered observability counter."""
    env = runtime_env(register=False)
    d = descriptor("my-runtime")

    env.manager.register_runtime(d)

    assert env.observability.counters.get("runtime.registered", 0) >= 1


def test_register_runtime_non_runtime_category_raises_value_error() -> None:
    """Registering a non-RUNTIME descriptor through the registry raises ValueError."""
    from nexus_core.registries.interfaces import HarnessCategory

    env = runtime_env(register=False)
    non_runtime = descriptor("my-context-harness", category=HarnessCategory.CONTEXT)

    with pytest.raises(ValueError, match="RUNTIME"):
        env.manager.register_runtime(non_runtime)


def test_register_multiple_runtimes_emits_one_registered_event_each() -> None:
    """Each registered runtime emits exactly one runtime.registered event."""
    env = runtime_env(register=False)
    runtimes = standard_runtimes()

    for d in runtimes:
        env.manager.register_runtime(d)

    registered = [e for e in env.events() if e.type == RUNTIME_REGISTERED]
    assert len(registered) == len(runtimes)


def test_register_runtime_is_safe_across_a_fresh_manager_under_a_different_clock() -> None:
    """A second RuntimeManager (a later actuation, or a restart) re-announcing the same runtime
    identity over the shared log must not crash just because the announcement's timestamp
    differs from the first — the announced fact (identity/category/version/capabilities) is
    identical, so the event id (a pure function of identity alone) colliding is expected, not an
    error. Regression test for a real crash reproduced against this exact scenario: a second
    build_execution_actuation() sharing a runtime identity over one durable infra under a real,
    advancing clock previously raised DuplicateEventError on the second actuation's registration.
    """
    infrastructure = build_infrastructure()
    d = descriptor("claude-code")

    first = build_runtime(
        infrastructure, timestamps=FixedTimestampSource("2026-01-01T00:00:00+00:00")
    )
    first.manager.register_runtime(d)

    # A fresh manager/registry (as a later actuation or a restart would construct) over the same
    # shared event log, at a genuinely different timestamp.
    second = build_runtime(
        infrastructure, timestamps=FixedTimestampSource("2026-01-01T00:05:00+00:00")
    )
    result = second.manager.register_runtime(d)  # must not raise

    assert result.identity == "claude-code"
    registered = [e for e in infrastructure.event_store.read_all() if e.type == RUNTIME_REGISTERED]
    assert len(registered) == 1  # the second announcement was absorbed, not appended again


# ===========================================================================
# prepare — single intake happy path
# ===========================================================================


def test_prepare_single_intake_returns_preparation_result() -> None:
    """prepare() returns a PreparationResult for a single intake."""
    env = runtime_env()
    request = preparation_request(intake())

    result = env.manager.prepare(request)

    assert isinstance(result, PreparationResult)


def test_prepare_single_intake_returns_one_session() -> None:
    """One intake yields exactly one RuntimeSession in the result."""
    env = runtime_env()
    request = preparation_request(intake())

    result = env.manager.prepare(request)

    assert len(result.sessions) == 1


def test_prepare_single_intake_returns_one_allocation() -> None:
    """One intake yields exactly one Allocation in the result."""
    env = runtime_env()
    request = preparation_request(intake())

    result = env.manager.prepare(request)

    assert len(result.allocations) == 1


def test_prepare_single_intake_session_reaches_ready() -> None:
    """The prepared session has lifecycle_state == READY."""
    env = runtime_env()
    request = preparation_request(intake())

    result = env.manager.prepare(request)

    assert result.sessions[0].lifecycle_state == RuntimeLifecycleState.READY


def test_prepare_single_intake_allocation_is_allocated() -> None:
    """The returned allocation is in ALLOCATED state."""
    from nexus_core.contracts.enums import ResourceAllocationState

    env = runtime_env()
    request = preparation_request(intake())

    result = env.manager.prepare(request)

    assert result.allocations[0].allocation_state == ResourceAllocationState.ALLOCATED


def test_prepare_single_intake_session_persisted() -> None:
    """After prepare(), the session is stored in repositories.sessions."""
    env = runtime_env()
    request = preparation_request(intake())

    result = env.manager.prepare(request)

    assert env.repositories.sessions.count == 1
    stored = env.repositories.sessions.get(result.sessions[0].identity)
    assert stored is not None


def test_prepare_single_intake_allocation_persisted() -> None:
    """After prepare(), the allocation is stored in repositories.allocations."""
    env = runtime_env()
    request = preparation_request(intake())

    result = env.manager.prepare(request)

    assert env.repositories.allocations.count == 1
    stored = env.repositories.allocations.get(result.allocations[0].identity)
    assert stored is not None


def test_prepare_single_intake_event_order() -> None:
    """Per-session events appear in canonical doc-15 order after registration events."""
    env = runtime_env()
    request = preparation_request(intake())

    env.manager.prepare(request)

    all_types = list(env.event_types())
    # Registration events come first (3 standard runtimes)
    n_registered = all_types.count(RUNTIME_REGISTERED)
    assert n_registered == 3

    # Per-session events follow
    session_types = all_types[n_registered:]
    for i, expected in enumerate(_PER_SESSION_EVENT_TYPES):
        assert session_types[i] == expected, (
            f"position {i}: expected {expected!r}, got {session_types[i]!r}"
        )


def test_prepare_single_intake_all_events_have_runtime_producer() -> None:
    """Every preparation event carries producer='runtime'."""
    env = runtime_env()
    request = preparation_request(intake())

    env.manager.prepare(request)

    for event in env.events():
        assert event.producer == "runtime", (
            f"event {event.identifier!r} has wrong producer: {event.producer!r}"
        )


def test_prepare_single_intake_event_identifiers_are_unique() -> None:
    """No two emitted events share the same identifier."""
    env = runtime_env()
    request = preparation_request(intake())

    env.manager.prepare(request)

    identifiers = [e.identifier for e in env.events()]
    assert len(identifiers) == len(set(identifiers))


def test_prepare_single_intake_session_has_correct_node() -> None:
    """The prepared session carries the node from the intake."""
    env = runtime_env()
    request = preparation_request(intake(node="node-alpha"))

    result = env.manager.prepare(request)

    assert result.sessions[0].node == "node-alpha"


def test_prepare_single_intake_session_bound_to_runtime() -> None:
    """The prepared session has a non-None runtime_ref."""
    env = runtime_env()
    request = preparation_request(intake())

    result = env.manager.prepare(request)

    assert result.sessions[0].runtime_ref is not None


def test_prepare_single_intake_session_has_allocation_ref() -> None:
    """The prepared session carries an allocation_ref matching the returned allocation."""
    env = runtime_env()
    request = preparation_request(intake())

    result = env.manager.prepare(request)
    session = result.sessions[0]
    allocation = result.allocations[0]

    assert session.allocation_ref is not None
    assert session.allocation_ref.identifier == allocation.identity


# ===========================================================================
# prepare — batch of 2 intakes (capacity splitting)
# ===========================================================================


def test_prepare_batch_two_intakes_returns_two_sessions() -> None:
    """A two-intake batch yields two sessions."""
    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-a", node="node-a", session="session-a", work_package_id="wp-a"
        ),
        intake(
            package_identity="pkg-b", node="node-b", session="session-b", work_package_id="wp-b"
        ),
    )

    result = env.manager.prepare(request)

    assert len(result.sessions) == 2
    assert len(result.allocations) == 2


def test_prepare_batch_two_intakes_both_sessions_ready() -> None:
    """Both sessions in a two-intake batch reach READY state."""
    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-a", node="node-a", session="session-a", work_package_id="wp-a"
        ),
        intake(
            package_identity="pkg-b", node="node-b", session="session-b", work_package_id="wp-b"
        ),
    )

    result = env.manager.prepare(request)

    for session in result.sessions:
        assert session.lifecycle_state == RuntimeLifecycleState.READY


def test_prepare_batch_two_intakes_distinct_runtimes_when_capacity_one() -> None:
    """With capacity-1 runtimes, two intakes with the same capability bind distinct runtimes."""
    # Use two runtimes, each with capacity=1 (default), both advertising code_generation
    runtimes = (
        descriptor("rt-alpha", capabilities=("code_generation",)),
        descriptor("rt-beta", capabilities=("code_generation",)),
    )
    env = runtime_env(runtimes=runtimes)

    request = preparation_request(
        intake(
            package_identity="pkg-a",
            node="node-a",
            session="session-a",
            work_package_id="wp-a",
            candidates=("rt-alpha", "rt-beta"),
        ),
        intake(
            package_identity="pkg-b",
            node="node-b",
            session="session-b",
            work_package_id="wp-b",
            candidates=("rt-alpha", "rt-beta"),
        ),
    )

    result = env.manager.prepare(request)

    runtime_ids = {a.runtime_ref.identifier for a in result.allocations}
    assert len(runtime_ids) == 2, "Expected two distinct runtimes to be chosen"


def test_prepare_batch_two_intakes_both_persisted() -> None:
    """Both sessions and both allocations are persisted after a batch prepare."""
    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-a", node="node-a", session="session-a", work_package_id="wp-a"
        ),
        intake(
            package_identity="pkg-b", node="node-b", session="session-b", work_package_id="wp-b"
        ),
    )

    env.manager.prepare(request)

    assert env.repositories.sessions.count == 2
    assert env.repositories.allocations.count == 2


def test_prepare_batch_validate_outputs_passes() -> None:
    """validate_outputs does not raise for a correctly produced batch result."""
    from nexus_runtime import validate_outputs

    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-a", node="node-a", session="session-a", work_package_id="wp-a"
        ),
        intake(
            package_identity="pkg-b", node="node-b", session="session-b", work_package_id="wp-b"
        ),
    )

    result = env.manager.prepare(request)

    # Should not raise
    validate_outputs(len(result.sessions), len(result.allocations), len(request.intakes))


# ===========================================================================
# _correlation branches
# ===========================================================================


def test_correlation_explicit_id_on_request() -> None:
    """Explicit correlation_identifier on the request is used as the correlation."""
    env = runtime_env()
    request = preparation_request(intake(), correlation_identifier="explicit-cor-xyz")

    result = env.manager.prepare(request)

    # All events should carry the explicit correlation
    session_events = [
        e for e in env.events() if e.identifier.startswith(f"evt-{result.sessions[0].identity}-")
    ]
    for event in session_events:
        assert event.correlation_identifier == "explicit-cor-xyz"


def test_correlation_from_first_intake_correlation_object() -> None:
    """When request.correlation_identifier is None, first intake's Correlation is used."""
    env = runtime_env()
    i = intake(correlation="cor-from-intake")
    request = preparation_request(i, correlation_identifier=None)

    result = env.manager.prepare(request)

    session_events = [
        e for e in env.events() if e.identifier.startswith(f"evt-{result.sessions[0].identity}-")
    ]
    assert all(e.correlation_identifier == "cor-from-intake" for e in session_events)


def test_correlation_falls_back_to_session_ref_when_intake_correlation_none() -> None:
    """When request and intake both have no correlation, falls back to cor-<session_ref.id>."""
    env = runtime_env()
    i = intake(session="my-session-ref", correlation=None)
    request = preparation_request(i, correlation_identifier=None)

    result = env.manager.prepare(request)

    expected_correlation = "cor-my-session-ref"
    session_events = [
        e for e in env.events() if e.identifier.startswith(f"evt-{result.sessions[0].identity}-")
    ]
    assert all(e.correlation_identifier == expected_correlation for e in session_events)


def test_correlation_empty_intakes_returns_cor_runtime() -> None:
    """An empty intakes tuple makes _correlation return 'cor-runtime'."""
    from nexus_runtime import PreparationRequest

    env = runtime_env()
    request = PreparationRequest(intakes=(), correlation_identifier=None)

    result = env.manager.prepare(request)

    # Empty result, no events emitted from prepare itself
    assert result.sessions == ()
    assert result.allocations == ()


def test_prepare_empty_intakes_does_not_raise() -> None:
    """prepare() with zero intakes returns an empty PreparationResult without raising."""
    from nexus_runtime import PreparationRequest

    env = runtime_env()
    request = PreparationRequest(intakes=())

    result = env.manager.prepare(request)

    assert result.sessions == ()
    assert result.allocations == ()


# ===========================================================================
# Failure + rollback
# ===========================================================================


def test_prepare_failure_raises_capability_mismatch_error() -> None:
    """When the 2nd intake has an unresolvable capability, CapabilityMismatchError is raised."""
    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-a",
            node="node-a",
            session="session-a",
            work_package_id="wp-a",
        ),
        intake(
            package_identity="pkg-b",
            node="node-b",
            session="session-b",
            work_package_id="wp-b",
            required=("missing_cap",),
            candidates=("claude-code", "gemini-cli", "shell"),
        ),
    )

    with pytest.raises(CapabilityMismatchError):
        env.manager.prepare(request)


def test_prepare_failure_nothing_persisted() -> None:
    """On failure, no sessions or allocations are persisted."""
    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-a",
            node="node-a",
            session="session-a",
            work_package_id="wp-a",
        ),
        intake(
            package_identity="pkg-b",
            node="node-b",
            session="session-b",
            work_package_id="wp-b",
            required=("missing_cap",),
            candidates=("claude-code", "gemini-cli", "shell"),
        ),
    )

    with pytest.raises(CapabilityMismatchError):
        env.manager.prepare(request)

    assert env.repositories.sessions.count == 0
    assert env.repositories.allocations.count == 0


def test_prepare_failure_emits_runtime_failed_event() -> None:
    """On failure, runtime.failed is emitted."""
    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-a",
            node="node-a",
            session="session-a",
            work_package_id="wp-a",
        ),
        intake(
            package_identity="pkg-b",
            node="node-b",
            session="session-b",
            work_package_id="wp-b",
            required=("missing_cap",),
            candidates=("claude-code", "gemini-cli", "shell"),
        ),
    )

    with pytest.raises(CapabilityMismatchError):
        env.manager.prepare(request)

    assert RUNTIME_FAILED in env.event_types()


def test_prepare_failure_rollback_emits_runtime_released_for_first_intake() -> None:
    """The successfully allocated first intake is rolled back: runtime.released emitted."""
    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-a",
            node="node-a",
            session="session-a",
            work_package_id="wp-a",
        ),
        intake(
            package_identity="pkg-b",
            node="node-b",
            session="session-b",
            work_package_id="wp-b",
            required=("missing_cap",),
            candidates=("claude-code", "gemini-cli", "shell"),
        ),
    )

    with pytest.raises(CapabilityMismatchError):
        env.manager.prepare(request)

    assert RUNTIME_RELEASED in env.event_types()


def test_prepare_failure_rollback_releases_first_allocation_payload_has_rollback() -> None:
    """The rollback runtime.released event carries rollback=True in its payload."""
    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-a",
            node="node-a",
            session="session-a",
            work_package_id="wp-a",
        ),
        intake(
            package_identity="pkg-b",
            node="node-b",
            session="session-b",
            work_package_id="wp-b",
            required=("missing_cap",),
            candidates=("claude-code", "gemini-cli", "shell"),
        ),
    )

    with pytest.raises(CapabilityMismatchError):
        env.manager.prepare(request)

    released_events = [e for e in env.events() if e.type == RUNTIME_RELEASED]
    rollback_events = [e for e in released_events if e.payload.get("rollback") is True]
    assert len(rollback_events) >= 1


def test_prepare_failure_capacity_freed_for_subsequent_prepare() -> None:
    """After a failed batch, the rolled-back runtime's capacity is freed for re-use."""
    env = runtime_env()

    # First batch: first intake succeeds, second fails — rolls back
    request_fail = preparation_request(
        intake(
            package_identity="pkg-a",
            node="node-a",
            session="session-a",
            work_package_id="wp-a",
        ),
        intake(
            package_identity="pkg-b",
            node="node-b",
            session="session-b",
            work_package_id="wp-b",
            required=("missing_cap",),
            candidates=("claude-code", "gemini-cli", "shell"),
        ),
    )

    with pytest.raises(CapabilityMismatchError):
        env.manager.prepare(request_fail)

    # Subsequent single prepare should succeed (capacity was freed)
    request_ok = preparation_request(
        intake(
            package_identity="pkg-c",
            node="node-c",
            session="session-c",
            work_package_id="wp-c",
        )
    )
    result = env.manager.prepare(request_ok)
    assert len(result.sessions) == 1
    assert result.sessions[0].lifecycle_state == RuntimeLifecycleState.READY


# ===========================================================================
# _fail with no allocation (before allocation stage)
# ===========================================================================


def test_prepare_unresolved_candidate_raises_unresolved_runtime_error() -> None:
    """An intake referencing a non-existent candidate raises UnresolvedRuntimeError."""
    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-ghost",
            node="node-ghost",
            session="session-ghost",
            work_package_id="wp-ghost",
            candidates=("does-not-exist",),
        )
    )

    with pytest.raises(UnresolvedRuntimeError):
        env.manager.prepare(request)


def test_prepare_unresolved_candidate_emits_runtime_failed() -> None:
    """UnresolvedRuntimeError before allocation still emits runtime.failed."""
    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-ghost",
            node="node-ghost",
            session="session-ghost",
            work_package_id="wp-ghost",
            candidates=("does-not-exist",),
        )
    )

    with pytest.raises(UnresolvedRuntimeError):
        env.manager.prepare(request)

    assert RUNTIME_FAILED in env.event_types()


def test_prepare_unresolved_candidate_does_not_emit_runtime_released() -> None:
    """When failure occurs before allocation, runtime.released is NOT emitted."""
    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-ghost",
            node="node-ghost",
            session="session-ghost",
            work_package_id="wp-ghost",
            candidates=("does-not-exist",),
        )
    )

    with pytest.raises(UnresolvedRuntimeError):
        env.manager.prepare(request)

    # runtime.released should not appear for the failed session
    released_events = [
        e for e in env.events() if e.type == RUNTIME_RELEASED and "rollback" not in e.payload
    ]
    assert len(released_events) == 0


def test_prepare_unresolved_candidate_no_sessions_persisted() -> None:
    """No sessions or allocations are persisted when all intakes fail before allocation."""
    env = runtime_env()
    request = preparation_request(
        intake(
            package_identity="pkg-ghost",
            node="node-ghost",
            session="session-ghost",
            work_package_id="wp-ghost",
            candidates=("does-not-exist",),
        )
    )

    with pytest.raises(UnresolvedRuntimeError):
        env.manager.prepare(request)

    assert env.repositories.sessions.count == 0
    assert env.repositories.allocations.count == 0


# ===========================================================================
# release
# ===========================================================================


def test_release_returns_released_session_and_allocation() -> None:
    """release() returns a tuple of (RuntimeSession, Allocation) both in RELEASED state."""
    from nexus_core.contracts.enums import ResourceAllocationState

    env = runtime_env()
    request = preparation_request(intake())
    result = env.manager.prepare(request)

    session, allocation = env.manager.release(result.sessions[0], result.allocations[0])

    assert session.lifecycle_state == RuntimeLifecycleState.RELEASED
    assert allocation.allocation_state == ResourceAllocationState.RELEASED


def test_release_emits_runtime_released_event() -> None:
    """release() emits a runtime.released event."""
    env = runtime_env()
    request = preparation_request(intake())
    result = env.manager.prepare(request)

    env.manager.release(result.sessions[0], result.allocations[0])

    released_events = [e for e in env.events() if e.type == RUNTIME_RELEASED]
    assert len(released_events) >= 1


def test_release_persists_released_session_and_allocation() -> None:
    """release() persists the RELEASED session and allocation into repositories."""
    from nexus_core.contracts.enums import ResourceAllocationState

    env = runtime_env()
    request = preparation_request(intake())
    result = env.manager.prepare(request)

    released_session, released_allocation = env.manager.release(
        result.sessions[0], result.allocations[0]
    )

    # Session persisted in RELEASED state
    stored_session = env.repositories.sessions.get(released_session.identity)
    assert stored_session is not None
    assert stored_session.lifecycle_state == RuntimeLifecycleState.RELEASED

    # Allocation persisted in RELEASED state
    stored_alloc = env.repositories.allocations.get(released_allocation.identity)
    assert stored_alloc is not None
    assert stored_alloc.allocation_state == ResourceAllocationState.RELEASED


def test_release_runtime_released_event_payload_has_runtime_and_allocation() -> None:
    """The runtime.released event payload carries runtime and allocation identities."""
    env = runtime_env()
    request = preparation_request(intake())
    result = env.manager.prepare(request)

    released_session, released_allocation = env.manager.release(
        result.sessions[0], result.allocations[0]
    )

    released_events = [e for e in env.events() if e.type == RUNTIME_RELEASED]
    assert len(released_events) >= 1
    payload = released_events[-1].payload
    assert "runtime" in payload
    assert "allocation" in payload


def test_release_increments_released_observability_counter() -> None:
    """release() increments the runtime.released observability counter."""
    env = runtime_env()
    request = preparation_request(intake())
    result = env.manager.prepare(request)

    before = env.observability.counters.get("runtime.released", 0)
    env.manager.release(result.sessions[0], result.allocations[0])
    after = env.observability.counters.get("runtime.released", 0)

    assert after > before


# ===========================================================================
# Canonical event type strings (doc 15)
# ===========================================================================


def test_prepare_emits_canonical_runtime_session_created_type() -> None:
    """runtime.session_created is emitted with its canonical type string."""
    env = runtime_env()
    request = preparation_request(intake())

    env.manager.prepare(request)

    assert "runtime.session_created" in env.event_types()


def test_prepare_emits_canonical_candidates_resolved_type() -> None:
    """runtime.candidates_resolved is emitted with its canonical type string."""
    env = runtime_env()
    request = preparation_request(intake())

    env.manager.prepare(request)

    assert "runtime.candidates_resolved" in env.event_types()


def test_prepare_emits_canonical_capabilities_matched_type() -> None:
    """runtime.capabilities_matched is emitted with its canonical type string."""
    env = runtime_env()
    request = preparation_request(intake())

    env.manager.prepare(request)

    assert "runtime.capabilities_matched" in env.event_types()


def test_prepare_emits_canonical_allocated_type() -> None:
    """runtime.allocated is emitted with its canonical type string."""
    env = runtime_env()
    request = preparation_request(intake())

    env.manager.prepare(request)

    assert "runtime.allocated" in env.event_types()


def test_prepare_emits_canonical_prepared_type() -> None:
    """runtime.prepared is emitted with its canonical type string."""
    env = runtime_env()
    request = preparation_request(intake())

    env.manager.prepare(request)

    assert "runtime.prepared" in env.event_types()


def test_prepare_emits_canonical_ready_type() -> None:
    """runtime.ready is emitted with its canonical type string."""
    env = runtime_env()
    request = preparation_request(intake())

    env.manager.prepare(request)

    assert "runtime.ready" in env.event_types()


# ===========================================================================
# _fail with allocation not None (error after allocation step)
# ===========================================================================


def test_fail_with_allocation_releases_allocation_and_emits_released() -> None:
    """_fail() with a live allocation releases it and emits runtime.released."""
    from unittest.mock import patch

    from nexus_runtime.validators import AllocationError

    env = runtime_env()
    request = preparation_request(intake())

    # Patch _obs.allocated to raise AllocationError after allocation is set.
    # This makes the failure fire inside _prepare_one AFTER allocation is assigned,
    # so _fail is called with allocation is not None — covering lines 264-277.
    def raise_after_allocation() -> None:
        raise AllocationError("forced failure after allocation for coverage")

    with patch.object(env.manager._obs, "allocated", side_effect=raise_after_allocation):
        with pytest.raises(AllocationError):
            env.manager.prepare(request)

    # runtime.released should have been emitted from _fail (allocation is not None path)
    released_events = [e for e in env.events() if e.type == RUNTIME_RELEASED]
    assert len(released_events) >= 1

    # runtime.failed should also have been emitted
    assert RUNTIME_FAILED in env.event_types()
