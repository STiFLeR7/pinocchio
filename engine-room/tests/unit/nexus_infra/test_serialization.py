"""Tests for :mod:`nexus_infra.serialization`.

Three concerns are covered:

- :class:`VersionedSerializer` — envelope-based, identity-preserving round-trips,
  plus backward-compatible deserialization of bare (un-enveloped) data, and a hard
  failure on corrupt data.
- :func:`canonical_json` — deterministic, key-order-insensitive byte image, with a
  :class:`~pydantic.BaseModel` rendering equal to its ``model_dump(mode="json")``.
- :func:`content_hash` — stable for equal values, distinct for different values.
"""

from __future__ import annotations

import pytest

from nexus_core.domain import Goal
from nexus_infra import (
    IntegrityError,
    VersionedSerializer,
    canonical_json,
    content_hash,
)
from tests.unit.nexus_infra.factories import make_goal

# -- VersionedSerializer ----------------------------------------------------- #


def test_serialize_produces_versioned_envelope() -> None:
    serializer = VersionedSerializer()
    goal = make_goal("goal-1")

    envelope = serializer.serialize(goal)

    assert envelope["schema_version"] == "1"
    assert envelope["type"] == "Goal"
    assert envelope["data"] == goal.model_dump(mode="json")


def test_serialize_uses_injected_schema_version() -> None:
    serializer = VersionedSerializer(schema_version="7")

    envelope = serializer.serialize(make_goal("goal-1"))

    assert envelope["schema_version"] == "7"


def test_round_trip_is_identity_preserving() -> None:
    serializer = VersionedSerializer()
    goal = make_goal("goal-1", outcome="Ship the release")

    restored = serializer.deserialize(Goal, serializer.serialize(goal))

    assert restored == goal
    assert restored.identity == "goal-1"


def test_deserialize_accepts_bare_data_mapping() -> None:
    # Backward compatibility: an un-enveloped object dump must still deserialize.
    serializer = VersionedSerializer()
    goal = make_goal("goal-1")

    restored = serializer.deserialize(Goal, goal.model_dump(mode="json"))

    assert restored == goal


def test_deserialize_invalid_data_raises_integrity_error() -> None:
    serializer = VersionedSerializer()

    with pytest.raises(IntegrityError):
        serializer.deserialize(Goal, {"data": {"identity": "goal-1"}})


# -- canonical_json ---------------------------------------------------------- #


def test_canonical_json_is_ordering_insensitive() -> None:
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_canonical_json_sorts_keys() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonical_json_is_deterministic_across_calls() -> None:
    value = {"z": [3, 2, 1], "a": {"y": 1, "x": 2}}

    assert canonical_json(value) == canonical_json(value)


def test_canonical_json_of_model_equals_its_json_dump() -> None:
    goal = make_goal("goal-1")

    assert canonical_json(goal) == canonical_json(goal.model_dump(mode="json"))


# -- content_hash ------------------------------------------------------------ #


def test_content_hash_is_stable_for_equal_values() -> None:
    assert content_hash(make_goal("g1")) == content_hash(make_goal("g1"))


def test_content_hash_differs_for_different_values() -> None:
    assert content_hash(make_goal("g1")) != content_hash(make_goal("g2"))


def test_content_hash_differs_when_one_field_changes() -> None:
    base = content_hash(make_goal("g1", outcome="Original outcome"))
    changed = content_hash(make_goal("g1", outcome="Different outcome"))

    assert base != changed
