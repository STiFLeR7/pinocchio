"""Deterministic identifier derivation for the Harness.

Every identifier the Harness produces is a pure function of the Harness Request
identity (and node keys) it compiles — no clock, no counter, no randomness. This is
what makes compilation reproducible: the same Harness Requests always yield the same
Execution Packages, Execution Manifests, and event identifiers (doc 11; the headline
Phase 6 determinism guarantee).
"""

from __future__ import annotations


def execution_package_id(harness_request_identity: str) -> str:
    return f"pkg-{harness_request_identity}"


def execution_manifest_id(package_identity: str) -> str:
    return f"manifest-{package_identity}"


def event_id(scope_identity: str, kind: str, sequence: int) -> str:
    return f"evt-{scope_identity}-{kind}-{sequence:04d}"


def correlation_id(seed_identity: str) -> str:
    return f"cor-{seed_identity}"
