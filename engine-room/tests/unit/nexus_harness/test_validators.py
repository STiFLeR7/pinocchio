"""Unit tests for nexus_harness.validators — error hierarchy and validation functions.

Verifies the HarnessError class hierarchy, validate_request_shape (shape guards),
and validate_outputs (structural consistency), all fail-fast with no silent correction.
"""

from __future__ import annotations

import pytest

from nexus_harness.validators import (
    HarnessError,
    InvalidHarnessRequestError,
    PackageCompilationError,
    UnresolvedReferenceError,
    validate_outputs,
    validate_request_shape,
)
from tests.unit.nexus_harness.helpers import hrequest

# --------------------------------------------------------------------------- #
# Error class hierarchy                                                         #
# --------------------------------------------------------------------------- #


def test_harness_error_is_exception_subclass() -> None:
    assert issubclass(HarnessError, Exception)


def test_invalid_harness_request_error_is_harness_error_subclass() -> None:
    assert issubclass(InvalidHarnessRequestError, HarnessError)


def test_unresolved_reference_error_is_harness_error_subclass() -> None:
    assert issubclass(UnresolvedReferenceError, HarnessError)


def test_package_compilation_error_is_harness_error_subclass() -> None:
    assert issubclass(PackageCompilationError, HarnessError)


def test_invalid_harness_request_error_is_exception_subclass() -> None:
    assert issubclass(InvalidHarnessRequestError, Exception)


def test_unresolved_reference_error_is_exception_subclass() -> None:
    assert issubclass(UnresolvedReferenceError, Exception)


def test_package_compilation_error_is_exception_subclass() -> None:
    assert issubclass(PackageCompilationError, Exception)


# --------------------------------------------------------------------------- #
# validate_request_shape — passing case                                         #
# --------------------------------------------------------------------------- #


def test_validate_request_shape_passes_for_valid_request() -> None:
    request = hrequest("node-1", work_package="wp-1", context="ctx-1")

    validate_request_shape(request)  # no raise


# --------------------------------------------------------------------------- #
# validate_request_shape — empty identity                                       #
# --------------------------------------------------------------------------- #


def test_validate_request_shape_raises_for_empty_identity() -> None:
    request = hrequest("node-1", identity="   ", work_package="wp-1")

    with pytest.raises(InvalidHarnessRequestError):
        validate_request_shape(request)


def test_validate_request_shape_empty_identity_is_invalid_harness_request_error() -> None:
    request = hrequest("node-1", identity="   ", work_package="wp-1")

    with pytest.raises(InvalidHarnessRequestError) as exc_info:
        validate_request_shape(request)

    assert isinstance(exc_info.value, HarnessError)


# --------------------------------------------------------------------------- #
# validate_request_shape — empty node                                           #
# --------------------------------------------------------------------------- #


def test_validate_request_shape_raises_for_empty_node() -> None:
    request = hrequest("   ", work_package="wp-1")

    with pytest.raises(InvalidHarnessRequestError):
        validate_request_shape(request)


def test_validate_request_shape_raises_for_whitespace_only_node() -> None:
    request = hrequest("\t", work_package="wp-1")

    with pytest.raises(InvalidHarnessRequestError):
        validate_request_shape(request)


# --------------------------------------------------------------------------- #
# validate_request_shape — empty work-package identifier                        #
# --------------------------------------------------------------------------- #


def test_validate_request_shape_raises_for_empty_work_package_identifier() -> None:
    request = hrequest("node-1", work_package="   ")

    with pytest.raises(InvalidHarnessRequestError):
        validate_request_shape(request)


def test_validate_request_shape_empty_work_package_is_invalid_harness_request_error() -> None:
    request = hrequest("node-1", work_package="   ")

    with pytest.raises(InvalidHarnessRequestError) as exc_info:
        validate_request_shape(request)

    assert isinstance(exc_info.value, HarnessError)


# --------------------------------------------------------------------------- #
# validate_outputs — passing cases                                              #
# --------------------------------------------------------------------------- #


def test_validate_outputs_passes_for_zero_zero_zero() -> None:
    validate_outputs(0, 0, 0)  # no raise


def test_validate_outputs_passes_when_counts_are_consistent() -> None:
    validate_outputs(3, 3, 3)  # no raise


def test_validate_outputs_passes_for_single_package() -> None:
    validate_outputs(1, 1, 1)  # no raise


# --------------------------------------------------------------------------- #
# validate_outputs — package count mismatch                                     #
# --------------------------------------------------------------------------- #


def test_validate_outputs_raises_when_packages_fewer_than_expected() -> None:
    with pytest.raises(PackageCompilationError):
        validate_outputs(2, 2, 3)


def test_validate_outputs_raises_when_packages_exceed_expected() -> None:
    with pytest.raises(PackageCompilationError):
        validate_outputs(4, 4, 3)


def test_validate_outputs_package_mismatch_is_package_compilation_error() -> None:
    with pytest.raises(PackageCompilationError) as exc_info:
        validate_outputs(0, 0, 1)

    assert isinstance(exc_info.value, HarnessError)


# --------------------------------------------------------------------------- #
# validate_outputs — manifest count mismatch                                    #
# --------------------------------------------------------------------------- #


def test_validate_outputs_raises_when_manifests_fewer_than_packages() -> None:
    with pytest.raises(PackageCompilationError):
        validate_outputs(3, 2, 3)


def test_validate_outputs_raises_when_manifests_exceed_packages() -> None:
    with pytest.raises(PackageCompilationError):
        validate_outputs(2, 3, 2)


def test_validate_outputs_manifest_mismatch_is_package_compilation_error() -> None:
    with pytest.raises(PackageCompilationError) as exc_info:
        validate_outputs(1, 0, 1)

    assert isinstance(exc_info.value, HarnessError)
