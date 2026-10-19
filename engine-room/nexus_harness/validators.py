"""Harness validation — fail-fast, deterministic, no silent correction.

Guards the compilation pipeline at its boundaries: a Harness Request must be
well-formed (identity, node, and a Work Package reference present), every primary
reference it carries (Work Package, Context Package, Execution Strategy) must
resolve, and the produced structure must be internally consistent (one Execution
Package and one Execution Manifest per Harness Request). A failure raises a
:class:`HarnessError`; the service turns that into a ``harness.failed`` event.
Nothing is auto-corrected.

This module imports no other ``nexus_harness`` module (only the frozen contracts and
the upstream Harness Request) so it remains the dependency-free root of the layer.
"""

from __future__ import annotations

from nexus_orchestration.harness_requests import HarnessRequest


class HarnessError(Exception):
    """Base for every harness compilation failure."""


class InvalidHarnessRequestError(HarnessError):
    """The Harness Request is malformed (missing identity, node, or work package)."""


class UnresolvedReferenceError(HarnessError):
    """A reference could not be resolved against its source/registry (fail-closed)."""


class PackageCompilationError(HarnessError):
    """The produced Execution Packages / Manifests are internally inconsistent."""


def validate_request_shape(request: HarnessRequest) -> None:
    """The Harness Request must name itself, its node, and a Work Package."""
    if not request.identity.strip():
        raise InvalidHarnessRequestError("harness request has an empty identity")
    if not request.node.strip():
        raise InvalidHarnessRequestError(f"harness request {request.identity!r} has an empty node")
    if not request.work_package_ref.identifier.strip():
        raise InvalidHarnessRequestError(
            f"harness request {request.identity!r} references no work package"
        )


def validate_outputs(package_count: int, manifest_count: int, expected: int) -> None:
    """One Execution Package and one Execution Manifest must exist per Harness Request."""
    if package_count != expected:
        raise PackageCompilationError(
            f"expected {expected} execution package(s), produced {package_count}"
        )
    if manifest_count != package_count:
        raise PackageCompilationError(
            f"execution manifests ({manifest_count}) do not match packages ({package_count})"
        )
