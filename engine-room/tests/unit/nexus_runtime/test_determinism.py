"""Unit tests for the Phase 8A determinism guarantee.

Verifies that given identical intakes and an identical Registry snapshot, two
independent RuntimeManager instances (with FixedTimestampSource) always produce:
- identical RuntimeSession tuples
- identical Allocation tuples
- identical event streams (identifier, type, payload)

Also asserts that session and allocation identifiers contain no timestamp component
(they are pure functions of the intake and attempt ordinal).
"""

from __future__ import annotations

from nexus_runtime import FixedTimestampSource
from tests.unit.nexus_runtime.helpers import (
    intake,
    preparation_request,
    runtime_env,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _two_envs():  # type: ignore[no-untyped-def]
    """Two independent runtime environments sharing no state."""
    return runtime_env(), runtime_env()


def _single_request():  # type: ignore[no-untyped-def]
    return preparation_request(
        intake(
            package_identity="pkg-deterministic",
            node="node-det",
            session="session-det",
            work_package_id="wp-det",
        )
    )


# ===========================================================================
# Identical sessions across two independent environments
# ===========================================================================


def test_two_runs_produce_equal_sessions() -> None:
    """Two prepares of the same request in independent envs yield equal sessions."""
    env1, env2 = _two_envs()
    request = _single_request()

    result1 = env1.manager.prepare(request)
    result2 = env2.manager.prepare(request)

    assert result1.sessions == result2.sessions


def test_two_runs_produce_equal_session_identities() -> None:
    """Session identities are pure functions of the intake — no randomness."""
    env1, env2 = _two_envs()
    request = _single_request()

    result1 = env1.manager.prepare(request)
    result2 = env2.manager.prepare(request)

    ids1 = tuple(s.identity for s in result1.sessions)
    ids2 = tuple(s.identity for s in result2.sessions)
    assert ids1 == ids2


def test_two_runs_produce_equal_session_lifecycle_states() -> None:
    """Both runs end with sessions in the same lifecycle state."""
    env1, env2 = _two_envs()
    request = _single_request()

    result1 = env1.manager.prepare(request)
    result2 = env2.manager.prepare(request)

    states1 = tuple(s.lifecycle_state for s in result1.sessions)
    states2 = tuple(s.lifecycle_state for s in result2.sessions)
    assert states1 == states2


# ===========================================================================
# Identical allocations across two independent environments
# ===========================================================================


def test_two_runs_produce_equal_allocations() -> None:
    """Two prepares yield equal allocations."""
    env1, env2 = _two_envs()
    request = _single_request()

    result1 = env1.manager.prepare(request)
    result2 = env2.manager.prepare(request)

    assert result1.allocations == result2.allocations


def test_two_runs_produce_equal_allocation_identities() -> None:
    """Allocation identities are pure functions of session id and runtime identity."""
    env1, env2 = _two_envs()
    request = _single_request()

    result1 = env1.manager.prepare(request)
    result2 = env2.manager.prepare(request)

    ids1 = tuple(a.identity for a in result1.allocations)
    ids2 = tuple(a.identity for a in result2.allocations)
    assert ids1 == ids2


def test_two_runs_choose_same_runtime() -> None:
    """Both runs select the same runtime (selection is deterministic)."""
    env1, env2 = _two_envs()
    request = _single_request()

    result1 = env1.manager.prepare(request)
    result2 = env2.manager.prepare(request)

    runtime1 = result1.allocations[0].runtime_ref.identifier
    runtime2 = result2.allocations[0].runtime_ref.identifier
    assert runtime1 == runtime2


# ===========================================================================
# Identical event streams across two independent environments
# ===========================================================================


def test_two_runs_emit_equal_event_types_in_order() -> None:
    """Both runs emit the same ordered sequence of event types."""
    env1, env2 = _two_envs()
    request = _single_request()

    env1.manager.prepare(request)
    env2.manager.prepare(request)

    types1 = list(env1.event_types())
    types2 = list(env2.event_types())
    assert types1 == types2


def test_two_runs_emit_equal_event_identifiers() -> None:
    """Both runs emit events with identical identifiers (deterministic event ids)."""
    env1, env2 = _two_envs()
    request = _single_request()

    env1.manager.prepare(request)
    env2.manager.prepare(request)

    ids1 = [e.identifier for e in env1.events()]
    ids2 = [e.identifier for e in env2.events()]
    assert ids1 == ids2


def test_two_runs_emit_equal_event_payloads() -> None:
    """Both runs emit events with identical payloads."""
    env1, env2 = _two_envs()
    request = _single_request()

    env1.manager.prepare(request)
    env2.manager.prepare(request)

    payloads1 = [e.payload for e in env1.events()]
    payloads2 = [e.payload for e in env2.events()]
    assert payloads1 == payloads2


def test_two_runs_emit_equal_event_timestamps() -> None:
    """Both runs emit events with identical timestamps (FixedTimestampSource)."""
    env1, env2 = _two_envs()
    request = _single_request()

    env1.manager.prepare(request)
    env2.manager.prepare(request)

    ts1 = [e.timestamp for e in env1.events()]
    ts2 = [e.timestamp for e in env2.events()]
    assert ts1 == ts2


def test_two_runs_full_event_equality() -> None:
    """All event fields (id, type, payload, timestamp) match between two runs."""
    env1, env2 = _two_envs()
    request = _single_request()

    env1.manager.prepare(request)
    env2.manager.prepare(request)

    events1 = list(env1.events())
    events2 = list(env2.events())
    assert events1 == events2


def test_two_runs_triple_events_identifier_payload_type_equal() -> None:
    """The (identifier, type, payload) triple is equal for each event position."""
    env1, env2 = _two_envs()
    request = _single_request()

    env1.manager.prepare(request)
    env2.manager.prepare(request)

    triples1 = [(e.identifier, e.type, e.payload) for e in env1.events()]
    triples2 = [(e.identifier, e.type, e.payload) for e in env2.events()]
    assert triples1 == triples2


# ===========================================================================
# Identifiers are timestamp-free (pure functions)
# ===========================================================================


def test_session_identifiers_contain_no_timestamp_component() -> None:
    """Session identifiers are derived from package identity and attempt, not the clock."""
    env = runtime_env()
    request = _single_request()

    result = env.manager.prepare(request)

    # The fixed timestamp value should NOT appear in any session id
    fixed_ts = "1970-01-01T00:00:00+00:00"
    for session in result.sessions:
        assert fixed_ts not in session.identity
        # Identity should follow the rts-<pkg>-<attempt> pattern
        assert session.identity.startswith("rts-")


def test_allocation_identifiers_contain_no_timestamp_component() -> None:
    """Allocation identifiers are derived from session id and runtime identity."""
    env = runtime_env()
    request = _single_request()

    result = env.manager.prepare(request)

    fixed_ts = "1970-01-01T00:00:00+00:00"
    for allocation in result.allocations:
        assert fixed_ts not in allocation.identity
        assert allocation.identity.startswith("alloc-")


def test_session_id_stable_across_runs() -> None:
    """The session id is the same between two independent runs with the same intake."""
    env1, env2 = _two_envs()
    request = _single_request()

    result1 = env1.manager.prepare(request)
    result2 = env2.manager.prepare(request)

    assert result1.sessions[0].identity == result2.sessions[0].identity


def test_fixed_timestamp_source_is_stable() -> None:
    """FixedTimestampSource always returns the same value."""
    ts = FixedTimestampSource("1970-01-01T00:00:00+00:00")

    assert ts.now() == "1970-01-01T00:00:00+00:00"
    assert ts.now() == ts.now()


def test_two_runs_with_explicit_fixed_source_produce_equal_timestamps() -> None:
    """Explicitly constructed FixedTimestampSource instances produce equal timestamps."""
    env1 = runtime_env(timestamps=FixedTimestampSource("2000-01-01T00:00:00+00:00"))
    env2 = runtime_env(timestamps=FixedTimestampSource("2000-01-01T00:00:00+00:00"))
    request = _single_request()

    env1.manager.prepare(request)
    env2.manager.prepare(request)

    ts1 = {e.timestamp for e in env1.events()}
    ts2 = {e.timestamp for e in env2.events()}
    assert ts1 == ts2
    assert len(ts1) == 1
