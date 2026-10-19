"""Unit tests for nexus_harness.ids.

Each id function is a pure function: same inputs always produce the same output
(determinism), the output matches the exact documented format, and distinct
inputs produce distinct outputs (collision resistance within the namespace).
"""

from __future__ import annotations

from nexus_harness.ids import (
    correlation_id,
    event_id,
    execution_manifest_id,
    execution_package_id,
)

# ---------------------------------------------------------------------------
# execution_package_id
# ---------------------------------------------------------------------------


def test_execution_package_id_format() -> None:
    assert execution_package_id("hreq-x") == "pkg-hreq-x"


def test_execution_package_id_is_deterministic() -> None:
    assert execution_package_id("hreq-abc") == execution_package_id("hreq-abc")


def test_execution_package_id_different_inputs_differ() -> None:
    assert execution_package_id("hreq-a") != execution_package_id("hreq-b")


def test_execution_package_id_preserves_input() -> None:
    seed = "session-goal-1-v1-nodeX"
    result = execution_package_id(seed)
    assert result == f"pkg-{seed}"


# ---------------------------------------------------------------------------
# execution_manifest_id
# ---------------------------------------------------------------------------


def test_execution_manifest_id_format() -> None:
    pkg = execution_package_id("hreq-x")
    assert execution_manifest_id(pkg) == "manifest-pkg-hreq-x"


def test_execution_manifest_id_is_deterministic() -> None:
    pkg = "pkg-hreq-abc"
    assert execution_manifest_id(pkg) == execution_manifest_id(pkg)


def test_execution_manifest_id_different_inputs_differ() -> None:
    assert execution_manifest_id("pkg-a") != execution_manifest_id("pkg-b")


def test_execution_manifest_id_preserves_input() -> None:
    pkg = "pkg-some-long-identity"
    assert execution_manifest_id(pkg) == f"manifest-{pkg}"


# ---------------------------------------------------------------------------
# event_id
# ---------------------------------------------------------------------------


def test_event_id_format_basic() -> None:
    assert event_id("scope", "package", 3) == "evt-scope-package-0003"


def test_event_id_zero_pads_sequence_to_four_digits() -> None:
    assert event_id("s", "k", 1) == "evt-s-k-0001"
    assert event_id("s", "k", 9) == "evt-s-k-0009"
    assert event_id("s", "k", 99) == "evt-s-k-0099"
    assert event_id("s", "k", 999) == "evt-s-k-0999"
    assert event_id("s", "k", 1000) == "evt-s-k-1000"


def test_event_id_is_deterministic() -> None:
    assert event_id("scope", "package", 3) == event_id("scope", "package", 3)


def test_event_id_different_scope_differs() -> None:
    assert event_id("scope-a", "package", 1) != event_id("scope-b", "package", 1)


def test_event_id_different_kind_differs() -> None:
    assert event_id("scope", "kind-a", 1) != event_id("scope", "kind-b", 1)


def test_event_id_different_sequence_differs() -> None:
    assert event_id("scope", "kind", 1) != event_id("scope", "kind", 2)


def test_event_id_sequence_zero() -> None:
    assert event_id("s", "k", 0) == "evt-s-k-0000"


# ---------------------------------------------------------------------------
# correlation_id
# ---------------------------------------------------------------------------


def test_correlation_id_format() -> None:
    assert correlation_id("goal-1") == "cor-goal-1"


def test_correlation_id_is_deterministic() -> None:
    assert correlation_id("goal-1") == correlation_id("goal-1")


def test_correlation_id_different_inputs_differ() -> None:
    assert correlation_id("goal-1") != correlation_id("goal-2")


def test_correlation_id_preserves_seed() -> None:
    seed = "session-abc-xyz"
    assert correlation_id(seed) == f"cor-{seed}"
