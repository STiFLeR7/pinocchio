"""Integration tests for the Phase 8A runtime preparation pipeline.

A realistic end-to-end scenario:
- Register 3 runtimes (claude-code, gemini-cli, shell) with distinct/overlapping capabilities
- Prepare a batch of 3 intakes with differing required capabilities and a runtime_policy
- Assert each session is bound to the correct runtime (matched capability)
- Assert all sessions and allocations are persisted
- Assert shared correlation across the batch event stream (INV-39)
- Assert all sessions in lifecycle READY

Tests only nexus_core/nexus_runtime — no nexus_harness/nexus_orchestration imports.
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
    RUNTIME_REGISTERED,
    RUNTIME_SESSION_CREATED,
)
from tests.unit.nexus_runtime.helpers import (
    descriptor,
    intake,
    preparation_request,
    runtime_env,
)

# ---------------------------------------------------------------------------
# Scenario setup helpers
# ---------------------------------------------------------------------------


def _three_distinct_runtimes():  # type: ignore[no-untyped-def]
    """Three runtimes with differing capability sets for realistic routing."""
    return (
        descriptor("claude-code", capabilities=("code_generation", "file_write")),
        descriptor("gemini-cli", capabilities=("code_generation", "web_search")),
        descriptor("shell", capabilities=("shell_exec", "file_write")),
    )


def _three_intakes():  # type: ignore[no-untyped-def]
    """Three intakes each requiring a distinct capability, bound to specific runtimes."""
    return (
        # Requires web_search → only gemini-cli qualifies
        intake(
            package_identity="pkg-search",
            node="node-search",
            session="session-search",
            work_package_id="wp-search",
            required=("web_search",),
            candidates=("claude-code", "gemini-cli", "shell"),
        ),
        # Requires shell_exec → only shell qualifies
        intake(
            package_identity="pkg-shell",
            node="node-shell",
            session="session-shell",
            work_package_id="wp-shell",
            required=("shell_exec",),
            candidates=("claude-code", "gemini-cli", "shell"),
        ),
        # Requires code_generation → claude-code or gemini-cli; add preferred policy
        intake(
            package_identity="pkg-code",
            node="node-code",
            session="session-code",
            work_package_id="wp-code",
            required=("code_generation",),
            candidates=("claude-code", "gemini-cli", "shell"),
            runtime_policy={"preferred_runtimes": ["claude-code"]},
        ),
    )


# ===========================================================================
# Batch prepare — result shape
# ===========================================================================


def test_integration_batch_returns_three_sessions() -> None:
    """A three-intake batch yields three RuntimeSessions."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    result = env.manager.prepare(request)

    assert len(result.sessions) == 3


def test_integration_batch_returns_three_allocations() -> None:
    """A three-intake batch yields three Allocations."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    result = env.manager.prepare(request)

    assert len(result.allocations) == 3


def test_integration_all_sessions_reach_ready() -> None:
    """All three sessions in the batch reach READY lifecycle state."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    result = env.manager.prepare(request)

    for session in result.sessions:
        assert session.lifecycle_state == RuntimeLifecycleState.READY


# ===========================================================================
# Correct runtime routing by capability
# ===========================================================================


def test_integration_web_search_intake_bound_to_gemini_cli() -> None:
    """The intake requiring web_search is bound to gemini-cli (only eligible candidate)."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    result = env.manager.prepare(request)

    # Find session for pkg-search
    search_session = next(s for s in result.sessions if s.node == "node-search")
    assert search_session.runtime_ref is not None
    assert search_session.runtime_ref.identifier == "gemini-cli"


def test_integration_shell_exec_intake_bound_to_shell() -> None:
    """The intake requiring shell_exec is bound to shell (only eligible candidate)."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    result = env.manager.prepare(request)

    shell_session = next(s for s in result.sessions if s.node == "node-shell")
    assert shell_session.runtime_ref is not None
    assert shell_session.runtime_ref.identifier == "shell"


def test_integration_code_generation_intake_bound_to_claude_code_via_policy() -> None:
    """The code_generation intake is bound to claude-code per the preferred_runtimes policy."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    result = env.manager.prepare(request)

    code_session = next(s for s in result.sessions if s.node == "node-code")
    assert code_session.runtime_ref is not None
    assert code_session.runtime_ref.identifier == "claude-code"


def test_integration_all_runtimes_chosen_are_distinct() -> None:
    """Each of the three intakes is assigned to a distinct runtime."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    result = env.manager.prepare(request)

    runtime_ids = {s.runtime_ref.identifier for s in result.sessions if s.runtime_ref}
    assert len(runtime_ids) == 3


# ===========================================================================
# Persistence
# ===========================================================================


def test_integration_all_sessions_persisted() -> None:
    """All three sessions are stored in repositories.sessions."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    result = env.manager.prepare(request)

    assert env.repositories.sessions.count == 3
    for session in result.sessions:
        stored = env.repositories.sessions.get(session.identity)
        assert stored is not None
        assert stored.identity == session.identity


def test_integration_all_allocations_persisted() -> None:
    """All three allocations are stored in repositories.allocations."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    result = env.manager.prepare(request)

    assert env.repositories.allocations.count == 3
    for allocation in result.allocations:
        stored = env.repositories.allocations.get(allocation.identity)
        assert stored is not None
        assert stored.identity == allocation.identity


# ===========================================================================
# Shared correlation across batch event stream (INV-39)
# ===========================================================================


def test_integration_batch_shares_single_correlation_identifier() -> None:
    """All session events in the batch carry the same explicit correlation_identifier (INV-39)."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    cor = "cor-int-test"
    request = preparation_request(*_three_intakes(), correlation_identifier=cor)
    result = env.manager.prepare(request)

    session_ids = {s.identity for s in result.sessions}
    session_events = [
        e
        for e in env.events()
        if any(e.identifier.startswith(f"evt-{sid}-") for sid in session_ids)
    ]

    for event in session_events:
        assert event.correlation_identifier == cor, (
            f"event {event.identifier!r} has correlation {event.correlation_identifier!r}, "
            f"expected {cor!r}"
        )


def test_integration_batch_correlation_on_all_allocations() -> None:
    """Each allocation carries the batch correlation identifier."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    cor = "cor-int-test"
    request = preparation_request(*_three_intakes(), correlation_identifier=cor)
    result = env.manager.prepare(request)

    for allocation in result.allocations:
        assert allocation.correlation.correlation_identifier == cor


# ===========================================================================
# Event structure — registration then per-session (3x3 + 3x6)
# ===========================================================================


def test_integration_event_count_is_registration_plus_session_events() -> None:
    """Total events = 3 runtime.registered + 3 sessions x 6 per-session events = 21."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    env.manager.prepare(request)

    all_types = list(env.event_types())
    n_registered = all_types.count(RUNTIME_REGISTERED)
    assert n_registered == 3  # 3 runtimes registered

    per_session_types = [
        RUNTIME_SESSION_CREATED,
        RUNTIME_DISCOVERED,
        RUNTIME_CAPABILITIES_MATCHED,
        RUNTIME_ALLOCATED,
        RUNTIME_PREPARED,
        RUNTIME_READY,
    ]
    n_session_events = sum(all_types.count(t) for t in per_session_types)
    assert n_session_events == 3 * 6  # 3 sessions x 6 events each

    assert len(all_types) == 3 + 3 * 6


def test_integration_registration_events_precede_session_events() -> None:
    """All runtime.registered events appear before the first session event."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    env.manager.prepare(request)

    all_types = list(env.event_types())
    last_registered_idx = max(i for i, t in enumerate(all_types) if t == RUNTIME_REGISTERED)
    first_session_idx = all_types.index(RUNTIME_SESSION_CREATED)

    assert last_registered_idx < first_session_idx


# ===========================================================================
# Lifecycle projection (ADR-001 cross-cutting)
# ===========================================================================


def test_integration_project_state_for_each_session_is_ready() -> None:
    """project_state() for each session's event stream yields READY."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")
    result = env.manager.prepare(request)

    for session in result.sessions:
        event_types = env.session_event_types(session.identity)
        assert project_state(event_types) == RuntimeLifecycleState.READY


# ===========================================================================
# Policy — denied_runtimes filter
# ===========================================================================


def test_integration_denied_runtimes_policy_excludes_candidate() -> None:
    """denied_runtimes policy causes the denied runtime to be skipped in selection."""
    # Two runtimes both advertising code_generation; deny claude-code
    rts = (
        descriptor("claude-code", capabilities=("code_generation",)),
        descriptor("gemini-cli", capabilities=("code_generation",)),
    )
    env = runtime_env(runtimes=rts)
    i = intake(
        package_identity="pkg-denied",
        node="node-denied",
        session="session-denied",
        work_package_id="wp-denied",
        required=("code_generation",),
        candidates=("claude-code", "gemini-cli"),
        runtime_policy={"denied_runtimes": ["claude-code"]},
    )
    request = preparation_request(i)

    result = env.manager.prepare(request)

    assert result.sessions[0].runtime_ref.identifier == "gemini-cli"


# ===========================================================================
# Observability counters after batch
# ===========================================================================


def test_integration_observability_registered_counter_equals_runtime_count() -> None:
    """runtime.registered counter equals the number of runtimes registered."""
    env = runtime_env(runtimes=_three_distinct_runtimes())

    count = env.observability.counters.get("runtime.registered", 0)
    assert count == 3


def test_integration_observability_session_created_counter_equals_intake_count() -> None:
    """runtime.session_created counter equals the number of intakes prepared."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    env.manager.prepare(request)

    assert env.observability.counters.get("runtime.session_created", 0) == 3


def test_integration_observability_allocated_counter_equals_intake_count() -> None:
    """runtime.allocated counter equals the number of intakes prepared."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    env.manager.prepare(request)

    assert env.observability.counters.get("runtime.allocated", 0) == 3


def test_integration_observability_session_ready_counter_equals_intake_count() -> None:
    """runtime.session_ready counter equals the number of intakes prepared."""
    env = runtime_env(runtimes=_three_distinct_runtimes())
    request = preparation_request(*_three_intakes(), correlation_identifier="cor-int-test")

    env.manager.prepare(request)

    assert env.observability.counters.get("runtime.session_ready", 0) == 3
