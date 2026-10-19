"""Unit tests for the Resource domain model (contract: resource.md)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import (
    ResourceAllocationState,
    ResourceAvailability,
    ResourceType,
)
from nexus_core.domain.resource import Resource
from nexus_core.state.transitions import MACHINES


def _valid_resource() -> Resource:
    return Resource(
        identity="res-1",
        type_category=ResourceType.RUNTIME,
        allocation_state=ResourceAllocationState.AVAILABLE,
        capability_reference=Reference(target_type="capability", identifier="cap-1"),
        backing_reference=Reference(target_type="harness", identifier="harness-1"),
    )


def test_construction() -> None:
    res = _valid_resource()
    assert res.identity == "res-1"
    assert res.allocation_state is ResourceAllocationState.AVAILABLE
    assert res.availability is None
    assert res.relationships == ()


def test_construction_with_optionals() -> None:
    res = Resource(
        identity="res-2",
        type_category=ResourceType.COMPUTE,
        allocation_state=ResourceAllocationState.ALLOCATED,
        capability_reference=Reference(target_type="capability", identifier="cap-2"),
        backing_reference=Reference(target_type="infrastructure", identifier="quota-1"),
        availability=ResourceAvailability.BUSY,
        allocation_holder=Reference(target_type="work_package", identifier="wp-1"),
    )
    assert res.availability is ResourceAvailability.BUSY
    assert res.allocation_holder is not None
    assert res.allocation_holder.identifier == "wp-1"


def test_immutable() -> None:
    res = _valid_resource()
    with pytest.raises(ValidationError):
        res.allocation_state = ResourceAllocationState.RELEASED  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        Resource(  # type: ignore[call-arg]
            identity="res-1",
            type_category=ResourceType.RUNTIME,
            allocation_state=ResourceAllocationState.AVAILABLE,
            capability_reference=Reference(target_type="capability", identifier="cap-1"),
            # backing_reference missing
        )


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Resource(
            identity="res-1",
            type_category=ResourceType.RUNTIME,
            allocation_state=ResourceAllocationState.AVAILABLE,
            capability_reference=Reference(target_type="capability", identifier="cap-1"),
            backing_reference=Reference(target_type="harness", identifier="harness-1"),
            health="healthy",  # type: ignore[call-arg]
        )


def test_serialization_round_trip() -> None:
    res = _valid_resource()
    assert Resource.model_validate(res.model_dump()) == res


def test_lifecycle_name() -> None:
    assert Resource.LIFECYCLE_NAME == "resource"
    assert Resource.LIFECYCLE_NAME in MACHINES
