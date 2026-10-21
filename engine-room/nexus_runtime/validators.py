"""Runtime validation — fail-fast, deterministic, no silent correction.

Guards the preparation pipeline at its boundaries: a :class:`RuntimeIntake` must be
well-formed (package identity, node, a Work Package, and a non-empty candidate set), and
the pipeline's funnel must never improvise — if a stage empties the survivor set, that is
a typed error, never a lowered requirement or a picked non-candidate (doc 06 §3). A
failure raises a :class:`RuntimeManagerError`; the service turns that into a
``runtime.failed`` event and releases any reservation.

This module imports only the frozen contracts and the runtime *inputs*
(:mod:`nexus_runtime.requests`) — no other ``nexus_runtime`` module — so it remains the
dependency-light root of the layer. The base error is named ``RuntimeManagerError`` (not
``RuntimeError``) so it never shadows the Python builtin.
"""

from __future__ import annotations

from nexus_runtime.requests import RuntimeIntake


class RuntimeManagerError(Exception):
    """Base for every runtime preparation failure."""


class InvalidRuntimeIntakeError(RuntimeManagerError):
    """The intake is malformed (missing identity, node, work package, or candidates)."""


class UnresolvedRuntimeError(RuntimeManagerError):
    """A candidate reference could not be resolved to a Registry descriptor (fail-closed)."""


class CapabilityMismatchError(RuntimeManagerError):
    """No candidate advertises every required capability — the eligible set is empty (doc 05)."""


class NoEligibleRuntimeError(RuntimeManagerError):
    """The funnel emptied after health/policy filtering — no runtime to allocate (doc 06)."""


class AllocationError(RuntimeManagerError):
    """Allocation bookkeeping was violated (e.g. double-booking, illegal release)."""


def validate_intake(intake: RuntimeIntake) -> None:
    """An intake must name itself, its node, a Work Package, and at least one candidate."""
    if not intake.package_identity.strip():
        raise InvalidRuntimeIntakeError("runtime intake has an empty package identity")
    if not intake.node.strip():
        raise InvalidRuntimeIntakeError(
            f"runtime intake {intake.package_identity!r} has an empty node"
        )
    if not intake.work_package.identifier.strip():
        raise InvalidRuntimeIntakeError(
            f"runtime intake {intake.package_identity!r} references no work package"
        )
    if not intake.candidate_harness_refs:
        raise InvalidRuntimeIntakeError(
            f"runtime intake {intake.package_identity!r} carries no candidate runtimes (INV-37)"
        )
    if intake.attempt < 1:
        raise InvalidRuntimeIntakeError(
            f"runtime intake {intake.package_identity!r} has a non-positive attempt ordinal"
        )


def validate_outputs(session_count: int, allocation_count: int, expected: int) -> None:
    """One Runtime Session per intake; at most one allocation per session."""
    if session_count != expected:
        raise AllocationError(f"expected {expected} runtime session(s), produced {session_count}")
    if allocation_count > session_count:
        raise AllocationError(f"allocations ({allocation_count}) exceed sessions ({session_count})")
