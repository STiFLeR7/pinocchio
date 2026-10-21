"""Unit tests for nexus_runtime.validators — error hierarchy and validation functions.

Verifies the RuntimeManagerError class hierarchy, validate_intake (shape guards),
and validate_outputs (structural consistency), all fail-fast with no silent correction.
"""

from __future__ import annotations

import pytest

from nexus_runtime.validators import (
    AllocationError,
    CapabilityMismatchError,
    InvalidRuntimeIntakeError,
    NoEligibleRuntimeError,
    RuntimeManagerError,
    UnresolvedRuntimeError,
    validate_intake,
    validate_outputs,
)
from tests.unit.nexus_runtime.helpers import intake

# --------------------------------------------------------------------------- #
# Error class hierarchy                                                         #
# --------------------------------------------------------------------------- #


def test_runtime_manager_error_is_exception_subclass() -> None:
    assert issubclass(RuntimeManagerError, Exception)


def test_runtime_manager_error_is_not_builtin_runtime_error() -> None:
    assert not issubclass(RuntimeManagerError, RuntimeError)


def test_invalid_runtime_intake_error_is_runtime_manager_error() -> None:
    assert issubclass(InvalidRuntimeIntakeError, RuntimeManagerError)


def test_invalid_runtime_intake_error_is_exception_subclass() -> None:
    assert issubclass(InvalidRuntimeIntakeError, Exception)


def test_unresolved_runtime_error_is_runtime_manager_error() -> None:
    assert issubclass(UnresolvedRuntimeError, RuntimeManagerError)


def test_unresolved_runtime_error_is_exception_subclass() -> None:
    assert issubclass(UnresolvedRuntimeError, Exception)


def test_capability_mismatch_error_is_runtime_manager_error() -> None:
    assert issubclass(CapabilityMismatchError, RuntimeManagerError)


def test_capability_mismatch_error_is_exception_subclass() -> None:
    assert issubclass(CapabilityMismatchError, Exception)


def test_no_eligible_runtime_error_is_runtime_manager_error() -> None:
    assert issubclass(NoEligibleRuntimeError, RuntimeManagerError)


def test_no_eligible_runtime_error_is_exception_subclass() -> None:
    assert issubclass(NoEligibleRuntimeError, Exception)


def test_allocation_error_is_runtime_manager_error() -> None:
    assert issubclass(AllocationError, RuntimeManagerError)


def test_allocation_error_is_exception_subclass() -> None:
    assert issubclass(AllocationError, Exception)


# --------------------------------------------------------------------------- #
# validate_intake — passing case                                                #
# --------------------------------------------------------------------------- #


def test_validate_intake_passes_for_valid_intake() -> None:
    valid = intake()
    validate_intake(valid)  # no raise


# --------------------------------------------------------------------------- #
# validate_intake — empty package_identity                                      #
# --------------------------------------------------------------------------- #


def test_validate_intake_raises_for_empty_package_identity() -> None:
    bad = intake(package_identity="")
    with pytest.raises(InvalidRuntimeIntakeError):
        validate_intake(bad)


def test_validate_intake_raises_for_whitespace_package_identity() -> None:
    bad = intake(package_identity="   ")
    with pytest.raises(InvalidRuntimeIntakeError):
        validate_intake(bad)


def test_validate_intake_empty_package_identity_is_runtime_manager_error() -> None:
    bad = intake(package_identity="  ")
    with pytest.raises(InvalidRuntimeIntakeError) as exc_info:
        validate_intake(bad)
    assert isinstance(exc_info.value, RuntimeManagerError)


# --------------------------------------------------------------------------- #
# validate_intake — empty node                                                  #
# --------------------------------------------------------------------------- #


def test_validate_intake_raises_for_empty_node() -> None:
    bad = intake(node="")
    with pytest.raises(InvalidRuntimeIntakeError):
        validate_intake(bad)


def test_validate_intake_raises_for_whitespace_node() -> None:
    bad = intake(node="\t")
    with pytest.raises(InvalidRuntimeIntakeError):
        validate_intake(bad)


def test_validate_intake_empty_node_is_runtime_manager_error() -> None:
    bad = intake(node="  ")
    with pytest.raises(InvalidRuntimeIntakeError) as exc_info:
        validate_intake(bad)
    assert isinstance(exc_info.value, RuntimeManagerError)


# --------------------------------------------------------------------------- #
# validate_intake — empty work_package identifier                               #
# --------------------------------------------------------------------------- #


def test_validate_intake_raises_for_whitespace_work_package_identifier() -> None:
    # WorkPackage.identifier has min_length=1 so we use whitespace-only (passes
    # Pydantic, fails validate_intake's .strip() check).
    bad = intake(work_package_id="   ")
    with pytest.raises(InvalidRuntimeIntakeError):
        validate_intake(bad)


def test_validate_intake_raises_for_single_space_work_package_identifier() -> None:
    bad = intake(work_package_id=" ")
    with pytest.raises(InvalidRuntimeIntakeError):
        validate_intake(bad)


def test_validate_intake_empty_work_package_identifier_is_runtime_manager_error() -> None:
    bad = intake(work_package_id="  ")
    with pytest.raises(InvalidRuntimeIntakeError) as exc_info:
        validate_intake(bad)
    assert isinstance(exc_info.value, RuntimeManagerError)


# --------------------------------------------------------------------------- #
# validate_intake — empty candidate_harness_refs                                #
# --------------------------------------------------------------------------- #


def test_validate_intake_raises_for_empty_candidates() -> None:
    bad = intake(candidates=())
    with pytest.raises(InvalidRuntimeIntakeError):
        validate_intake(bad)


def test_validate_intake_empty_candidates_is_runtime_manager_error() -> None:
    bad = intake(candidates=())
    with pytest.raises(InvalidRuntimeIntakeError) as exc_info:
        validate_intake(bad)
    assert isinstance(exc_info.value, RuntimeManagerError)


# --------------------------------------------------------------------------- #
# validate_intake — attempt < 1                                                 #
# --------------------------------------------------------------------------- #


def test_validate_intake_raises_for_attempt_zero() -> None:
    bad = intake(attempt=0)
    with pytest.raises(InvalidRuntimeIntakeError):
        validate_intake(bad)


def test_validate_intake_raises_for_negative_attempt() -> None:
    bad = intake(attempt=-1)
    with pytest.raises(InvalidRuntimeIntakeError):
        validate_intake(bad)


def test_validate_intake_attempt_below_one_is_runtime_manager_error() -> None:
    bad = intake(attempt=0)
    with pytest.raises(InvalidRuntimeIntakeError) as exc_info:
        validate_intake(bad)
    assert isinstance(exc_info.value, RuntimeManagerError)


def test_validate_intake_passes_for_attempt_one() -> None:
    valid = intake(attempt=1)
    validate_intake(valid)  # no raise


def test_validate_intake_passes_for_attempt_greater_than_one() -> None:
    valid = intake(attempt=5)
    validate_intake(valid)  # no raise


# --------------------------------------------------------------------------- #
# validate_outputs — passing cases                                              #
# --------------------------------------------------------------------------- #


def test_validate_outputs_passes_for_zero_zero_zero() -> None:
    validate_outputs(0, 0, 0)  # no raise


def test_validate_outputs_passes_for_one_one_one() -> None:
    validate_outputs(1, 1, 1)  # no raise


def test_validate_outputs_passes_when_allocation_equals_session() -> None:
    validate_outputs(3, 3, 3)  # no raise


def test_validate_outputs_passes_when_allocation_less_than_session() -> None:
    # allocation_count <= session_count is legal
    validate_outputs(2, 1, 2)  # no raise


def test_validate_outputs_passes_allocation_zero_sessions_two() -> None:
    validate_outputs(2, 0, 2)  # no raise


# --------------------------------------------------------------------------- #
# validate_outputs — session_count mismatch                                     #
# --------------------------------------------------------------------------- #


def test_validate_outputs_raises_when_session_count_less_than_expected() -> None:
    with pytest.raises(AllocationError):
        validate_outputs(1, 1, 2)


def test_validate_outputs_raises_when_session_count_greater_than_expected() -> None:
    with pytest.raises(AllocationError):
        validate_outputs(3, 3, 2)


def test_validate_outputs_session_mismatch_is_runtime_manager_error() -> None:
    with pytest.raises(AllocationError) as exc_info:
        validate_outputs(0, 0, 1)
    assert isinstance(exc_info.value, RuntimeManagerError)


# --------------------------------------------------------------------------- #
# validate_outputs — allocation_count > session_count                           #
# --------------------------------------------------------------------------- #


def test_validate_outputs_raises_when_allocations_exceed_sessions() -> None:
    with pytest.raises(AllocationError):
        validate_outputs(2, 3, 2)


def test_validate_outputs_allocation_excess_is_runtime_manager_error() -> None:
    with pytest.raises(AllocationError) as exc_info:
        validate_outputs(1, 2, 1)
    assert isinstance(exc_info.value, RuntimeManagerError)
