"""Tests for :mod:`nexus_infra.identifiers`.

Two factories implement the foundation's ``IdentifierFactory``:

- :class:`DeterministicIdentifierFactory` — monotonic, reproducible per kind, with
  independent event/correlation/execution counters and an applied prefix. Captured
  *as recorded data* on every Event, so byte-identical replay is possible (INV-17).
- :class:`UuidIdentifierFactory` — unique per call, prefixed by kind.
"""

from __future__ import annotations

from nexus_infra import DeterministicIdentifierFactory, UuidIdentifierFactory

# -- DeterministicIdentifierFactory ------------------------------------------ #


def test_deterministic_event_identifiers_are_monotonic() -> None:
    factory = DeterministicIdentifierFactory()

    sequence = [factory.new_event_identifier() for _ in range(3)]

    assert sequence == ["evt-00000001", "evt-00000002", "evt-00000003"]


def test_two_fresh_factories_yield_identical_sequences() -> None:
    a = DeterministicIdentifierFactory(prefix="nx-")
    b = DeterministicIdentifierFactory(prefix="nx-")

    seq_a = [a.new_event_identifier() for _ in range(5)]
    seq_b = [b.new_event_identifier() for _ in range(5)]

    assert seq_a == seq_b


def test_deterministic_counters_are_independent_per_kind() -> None:
    factory = DeterministicIdentifierFactory()

    # Interleave the kinds; each must advance on its own counter only.
    first_event = factory.new_event_identifier()
    first_correlation = factory.new_correlation_identifier()
    first_execution = factory.new_execution_identifier()
    second_event = factory.new_event_identifier()

    assert first_event == "evt-00000001"
    assert second_event == "evt-00000002"
    assert first_correlation == "cor-00000001"
    assert first_execution == "exe-00000001"


def test_deterministic_prefix_is_applied() -> None:
    factory = DeterministicIdentifierFactory(prefix="test-")

    assert factory.new_event_identifier() == "test-evt-00000001"
    assert factory.new_correlation_identifier() == "test-cor-00000001"
    assert factory.new_execution_identifier() == "test-exe-00000001"


# -- UuidIdentifierFactory --------------------------------------------------- #


def test_uuid_event_identifiers_are_unique() -> None:
    factory = UuidIdentifierFactory()

    identifiers = {factory.new_event_identifier() for _ in range(1000)}

    assert len(identifiers) == 1000


def test_uuid_identifiers_carry_kind_prefix() -> None:
    factory = UuidIdentifierFactory()

    assert factory.new_event_identifier().startswith("evt-")
    assert factory.new_correlation_identifier().startswith("cor-")
    assert factory.new_execution_identifier().startswith("exe-")


def test_uuid_identifiers_are_unique_across_kinds() -> None:
    factory = UuidIdentifierFactory()

    identifiers = set()
    for _ in range(500):
        identifiers.add(factory.new_event_identifier())
        identifiers.add(factory.new_correlation_identifier())
        identifiers.add(factory.new_execution_identifier())

    assert len(identifiers) == 1500
