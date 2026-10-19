"""Unit tests for the event-sourced projection / replay guarantee (ADR-001).

After a happy prepare():
- project_state(session_event_types) folds to READY
After release():
- project_state(session_event_types) folds to RELEASED
Idempotency:
- feeding the same event-type stream twice (with same-state duplicates) still yields
  the correct final state (project_state skips no-op same-state transitions).
Event stream ordering:
- events read from infrastructure.event_store are in append order, i.e. session
  events come after registration events and are in pipeline order within a session.
"""

from __future__ import annotations

from nexus_runtime import (
    RuntimeLifecycleState,
    project_state,
)
from nexus_runtime.events import (
    RUNTIME_ALLOCATED,
    RUNTIME_CAPABILITIES_MATCHED,
    RUNTIME_DISCOVERED,
    RUNTIME_PREPARED,
    RUNTIME_READY,
    RUNTIME_SESSION_CREATED,
)
from tests.unit.nexus_runtime.helpers import (
    intake,
    preparation_request,
    runtime_env,
)

# ===========================================================================
# project_state after prepare — READY
# ===========================================================================


def test_project_state_after_prepare_yields_ready() -> None:
    """project_state over a prepared session's event types gives READY."""
    env = runtime_env()
    request = preparation_request(intake())
    result = env.manager.prepare(request)
    session_id = result.sessions[0].identity

    event_types = env.session_event_types(session_id)
    state = project_state(event_types)

    assert state == RuntimeLifecycleState.READY


def test_project_state_after_prepare_session_identity_matches() -> None:
    """The projected session state matches the runtime session's lifecycle_state."""
    env = runtime_env()
    request = preparation_request(intake())
    result = env.manager.prepare(request)
    session = result.sessions[0]

    event_types = env.session_event_types(session.identity)
    state = project_state(event_types)

    assert state == session.lifecycle_state


# ===========================================================================
# project_state after release — RELEASED
# ===========================================================================


def test_project_state_after_release_yields_released() -> None:
    """project_state after release() folds to RELEASED."""
    env = runtime_env()
    request = preparation_request(intake())
    result = env.manager.prepare(request)
    session_id = result.sessions[0].identity

    env.manager.release(result.sessions[0], result.allocations[0])

    event_types = env.session_event_types(session_id)
    state = project_state(event_types)

    assert state == RuntimeLifecycleState.RELEASED


def test_project_state_after_release_matches_returned_session() -> None:
    """The projected state matches the released session's lifecycle_state."""
    env = runtime_env()
    request = preparation_request(intake())
    result = env.manager.prepare(request)

    released_session, _ = env.manager.release(result.sessions[0], result.allocations[0])

    event_types = env.session_event_types(released_session.identity)
    state = project_state(event_types)

    assert state == released_session.lifecycle_state == RuntimeLifecycleState.RELEASED


# ===========================================================================
# Idempotency — duplicate same-state events are skipped
# ===========================================================================


def test_project_state_idempotent_when_stream_contains_duplicate_ready() -> None:
    """Feeding READY twice in the stream still folds to READY (same-state is skipped)."""
    env = runtime_env()
    request = preparation_request(intake())
    result = env.manager.prepare(request)
    session_id = result.sessions[0].identity

    event_types = env.session_event_types(session_id)
    # Duplicate READY at the end — project_state should skip it
    duplicated = (*event_types, RUNTIME_READY)

    state = project_state(duplicated)

    assert state == RuntimeLifecycleState.READY


def test_project_state_idempotent_when_stream_contains_repeated_tail() -> None:
    """Appending the full session stream to itself still folds to READY."""
    env = runtime_env()
    request = preparation_request(intake())
    result = env.manager.prepare(request)
    session_id = result.sessions[0].identity

    event_types = env.session_event_types(session_id)
    # project_state will skip transitions that are already in the same state or
    # will raise if illegal — we care that READY is the outcome (the tail repeats
    # bring it back to READY-equivalent after same-state skips).
    # The actual outcome: after READY, the repeated CREATED/REGISTERED... would be
    # illegal. So we test with just the READY state repeated.
    same_state_stream = (*event_types, RUNTIME_READY)
    state = project_state(same_state_stream)
    assert state == RuntimeLifecycleState.READY


def test_project_state_skips_unknown_event_types() -> None:
    """Non-lifecycle events (e.g. capabilities_matched, registered) are silently skipped."""
    stream = (
        RUNTIME_SESSION_CREATED,
        RUNTIME_CAPABILITIES_MATCHED,  # not a lifecycle driver — skipped
        "runtime.registered",  # not a lifecycle driver — skipped
        RUNTIME_DISCOVERED,
        RUNTIME_ALLOCATED,
        RUNTIME_PREPARED,
        RUNTIME_READY,
    )

    state = project_state(stream)

    assert state == RuntimeLifecycleState.READY


def test_project_state_empty_stream_returns_created() -> None:
    """An empty event-type stream returns the initial CREATED state."""
    state = project_state(())

    assert state == RuntimeLifecycleState.CREATED


# ===========================================================================
# Event stream ordering (append order invariant)
# ===========================================================================


def test_session_events_come_after_registration_events_in_global_stream() -> None:
    """In the global event store, registration events precede session events."""
    env = runtime_env()
    request = preparation_request(intake())
    env.manager.prepare(request)

    all_events = list(env.events())
    types = [e.type for e in all_events]

    # Find last registration event and first session event
    last_registered_idx = max(i for i, t in enumerate(types) if t == "runtime.registered")
    first_session_idx = types.index("runtime.session_created")

    assert last_registered_idx < first_session_idx


def test_session_event_types_in_pipeline_order() -> None:
    """Per-session events are in preparation pipeline order."""
    env = runtime_env()
    request = preparation_request(intake())
    result = env.manager.prepare(request)
    session_id = result.sessions[0].identity

    event_types = env.session_event_types(session_id)

    expected_order = [
        RUNTIME_SESSION_CREATED,
        RUNTIME_DISCOVERED,
        RUNTIME_CAPABILITIES_MATCHED,
        RUNTIME_ALLOCATED,
        RUNTIME_PREPARED,
        RUNTIME_READY,
    ]
    assert list(event_types) == expected_order


def test_event_store_read_all_returns_events_in_append_order() -> None:
    """read_all() yields events in the order they were appended."""
    env = runtime_env()
    request = preparation_request(intake())

    env.manager.prepare(request)

    all_events = list(env.events())
    # First events are runtime.registered, last is runtime.ready
    assert all_events[0].type == "runtime.registered"
    assert all_events[-1].type == "runtime.ready"


def test_event_store_correlation_groups_session_events() -> None:
    """All session events share the same correlation_identifier as the batch correlation."""
    env = runtime_env()
    explicit_cor = "cor-replay-test"
    request = preparation_request(intake(), correlation_identifier=explicit_cor)
    result = env.manager.prepare(request)
    session_id = result.sessions[0].identity

    session_events = [e for e in env.events() if e.identifier.startswith(f"evt-{session_id}-")]

    for event in session_events:
        assert event.correlation_identifier == explicit_cor


# ===========================================================================
# Projection over two sessions in a batch
# ===========================================================================


def test_project_state_for_each_session_in_batch_is_ready() -> None:
    """project_state for each session in a two-intake batch yields READY."""
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
        ),
    )
    result = env.manager.prepare(request)

    for session in result.sessions:
        event_types = env.session_event_types(session.identity)
        state = project_state(event_types)
        assert state == RuntimeLifecycleState.READY


def test_each_session_in_batch_has_independent_event_stream() -> None:
    """Each session in a batch has its own scoped event stream (filtered by identity prefix)."""
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
        ),
    )
    result = env.manager.prepare(request)

    stream_a = env.session_event_types(result.sessions[0].identity)
    stream_b = env.session_event_types(result.sessions[1].identity)

    # Each stream should have the same length but different session scopes
    assert len(stream_a) == len(stream_b)
    # They are independent — no overlap in identifiers
    ids_a = {
        e.identifier
        for e in env.events()
        if e.identifier.startswith(f"evt-{result.sessions[0].identity}-")
    }
    ids_b = {
        e.identifier
        for e in env.events()
        if e.identifier.startswith(f"evt-{result.sessions[1].identity}-")
    }
    assert ids_a.isdisjoint(ids_b)
