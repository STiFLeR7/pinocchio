"""Unit tests for nexus_runtime.ids.

Each id function is a pure function: same inputs always produce the same output
(determinism), the output matches the exact documented format, and distinct
inputs produce distinct outputs (collision resistance within the namespace).
"""

from __future__ import annotations

from nexus_runtime.ids import (
    allocation_id,
    correlation_id,
    event_id,
    runtime_session_id,
)

# --------------------------------------------------------------------------- #
# runtime_session_id                                                            #
# --------------------------------------------------------------------------- #


def test_runtime_session_id_default_attempt_format() -> None:
    assert runtime_session_id("pkg-x") == "rts-pkg-x-01"


def test_runtime_session_id_default_attempt_is_one() -> None:
    assert runtime_session_id("abc") == "rts-abc-01"


def test_runtime_session_id_attempt_zero_padded_to_two_digits() -> None:
    assert runtime_session_id("pkg-x", attempt=1) == "rts-pkg-x-01"
    assert runtime_session_id("pkg-x", attempt=9) == "rts-pkg-x-09"


def test_runtime_session_id_attempt_12_zero_padded() -> None:
    assert runtime_session_id("pkg-x", attempt=12) == "rts-pkg-x-12"


def test_runtime_session_id_attempt_two_digits_no_pad() -> None:
    assert runtime_session_id("abc", attempt=99) == "rts-abc-99"


def test_runtime_session_id_is_deterministic() -> None:
    assert runtime_session_id("pkg-abc", attempt=3) == runtime_session_id("pkg-abc", attempt=3)


def test_runtime_session_id_different_packages_differ() -> None:
    assert runtime_session_id("pkg-a") != runtime_session_id("pkg-b")


def test_runtime_session_id_different_attempts_differ() -> None:
    assert runtime_session_id("pkg-x", attempt=1) != runtime_session_id("pkg-x", attempt=2)


def test_runtime_session_id_preserves_package_identity() -> None:
    pkg = "my-package-identity"
    result = runtime_session_id(pkg)
    assert result == f"rts-{pkg}-01"


# --------------------------------------------------------------------------- #
# allocation_id                                                                 #
# --------------------------------------------------------------------------- #


def test_allocation_id_format() -> None:
    assert allocation_id("rts-pkg-x-01", "claude-code") == "alloc-rts-pkg-x-01-claude-code"


def test_allocation_id_is_deterministic() -> None:
    assert allocation_id("rts-abc-01", "gemini") == allocation_id("rts-abc-01", "gemini")


def test_allocation_id_different_sessions_differ() -> None:
    assert allocation_id("rts-a-01", "rt") != allocation_id("rts-b-01", "rt")


def test_allocation_id_different_runtimes_differ() -> None:
    assert allocation_id("rts-x-01", "rt-a") != allocation_id("rts-x-01", "rt-b")


def test_allocation_id_preserves_both_parts() -> None:
    session = "rts-pkg-hr-node-a-01"
    runtime = "claude-code"
    assert allocation_id(session, runtime) == f"alloc-{session}-{runtime}"


# --------------------------------------------------------------------------- #
# event_id                                                                      #
# --------------------------------------------------------------------------- #


def test_event_id_format_basic() -> None:
    assert event_id("scope", "package", 3) == "evt-scope-package-0003"


def test_event_id_zero_pads_sequence_to_four_digits() -> None:
    assert event_id("s", "k", 1) == "evt-s-k-0001"
    assert event_id("s", "k", 9) == "evt-s-k-0009"
    assert event_id("s", "k", 99) == "evt-s-k-0099"
    assert event_id("s", "k", 999) == "evt-s-k-0999"
    assert event_id("s", "k", 1000) == "evt-s-k-1000"


def test_event_id_sequence_zero() -> None:
    assert event_id("s", "k", 0) == "evt-s-k-0000"


def test_event_id_is_deterministic() -> None:
    assert event_id("scope", "package", 3) == event_id("scope", "package", 3)


def test_event_id_different_scope_differs() -> None:
    assert event_id("scope-a", "kind", 1) != event_id("scope-b", "kind", 1)


def test_event_id_different_kind_differs() -> None:
    assert event_id("scope", "kind-a", 1) != event_id("scope", "kind-b", 1)


def test_event_id_different_sequence_differs() -> None:
    assert event_id("scope", "kind", 1) != event_id("scope", "kind", 2)


# --------------------------------------------------------------------------- #
# correlation_id                                                                #
# --------------------------------------------------------------------------- #


def test_correlation_id_format() -> None:
    assert correlation_id("goal-1") == "cor-goal-1"


def test_correlation_id_is_deterministic() -> None:
    assert correlation_id("goal-1") == correlation_id("goal-1")


def test_correlation_id_different_inputs_differ() -> None:
    assert correlation_id("goal-1") != correlation_id("goal-2")


def test_correlation_id_preserves_seed() -> None:
    seed = "session-abc-xyz"
    assert correlation_id(seed) == f"cor-{seed}"
