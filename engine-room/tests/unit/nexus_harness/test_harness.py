"""Unit tests for nexus_harness.harness — HarnessService compilation pipeline.

Covers the full pipeline from CompilationRequest to CompilationResult: output
shape, persistence, event ordering/producer/uniqueness, multi-request batches,
empty batches, and the fail-closed path that raises UnresolvedReferenceError and
emits harness.failed.
"""

from __future__ import annotations

import pytest

from nexus_harness import (
    CompilationRequest,
    CompilationResult,
    UnresolvedReferenceError,
)
from nexus_harness.events import (
    ARTIFACTS_RESOLVED,
    CAPABILITIES_RESOLVED,
    CONTEXT_RESOLVED,
    EXECUTION_MANIFEST_CREATED,
    EXECUTION_PACKAGE_CREATED,
    HARNESS_COMPLETED,
    HARNESS_FAILED,
    HARNESS_REQUEST_VALIDATED,
    POLICIES_RESOLVED,
    SKILLS_RESOLVED,
)
from nexus_harness.manifest_builder import ExecutionManifest
from nexus_harness.package_builder import ExecutionPackage
from tests.unit.nexus_harness.helpers import (
    harness_env,
    hrequest,
    ref,
    standard_env,
)

# ---------------------------------------------------------------------------
# Ordered per-request event types for one compilation
# ---------------------------------------------------------------------------

_PER_REQUEST_EVENT_TYPES = [
    HARNESS_REQUEST_VALIDATED,
    SKILLS_RESOLVED,
    CAPABILITIES_RESOLVED,
    POLICIES_RESOLVED,
    CONTEXT_RESOLVED,
    ARTIFACTS_RESOLVED,
    EXECUTION_PACKAGE_CREATED,
    EXECUTION_MANIFEST_CREATED,
]


# ---------------------------------------------------------------------------
# Output shape — single request
# ---------------------------------------------------------------------------


def test_compile_single_request_returns_compilation_result() -> None:
    """compile() returns a CompilationResult for a single harness request."""
    env = standard_env()
    request = CompilationRequest(
        harness_requests=(
            hrequest(
                "node-research",
                work_package="wp-1",
                skills=(ref("skill", "skill-investigate"),),
            ),
        )
    )

    result = env.harness.service.compile(request)

    assert isinstance(result, CompilationResult)


def test_compile_single_request_produces_one_package() -> None:
    """One harness request yields exactly one ExecutionPackage."""
    env = standard_env()
    request = CompilationRequest(
        harness_requests=(
            hrequest(
                "node-research",
                work_package="wp-1",
                skills=(ref("skill", "skill-investigate"),),
            ),
        )
    )

    result = env.harness.service.compile(request)

    assert len(result.packages) == 1
    assert isinstance(result.packages[0], ExecutionPackage)


def test_compile_single_request_produces_one_manifest() -> None:
    """One harness request yields exactly one ExecutionManifest."""
    env = standard_env()
    request = CompilationRequest(
        harness_requests=(
            hrequest(
                "node-research",
                work_package="wp-1",
                skills=(ref("skill", "skill-investigate"),),
            ),
        )
    )

    result = env.harness.service.compile(request)

    assert len(result.manifests) == 1
    assert isinstance(result.manifests[0], ExecutionManifest)


def test_compile_package_identity_reflects_harness_request() -> None:
    """The package identity is pkg-<harness_request_identity>."""
    env = standard_env()
    hr = hrequest(
        "node-research",
        work_package="wp-1",
        skills=(ref("skill", "skill-investigate"),),
    )
    request = CompilationRequest(harness_requests=(hr,))

    result = env.harness.service.compile(request)

    assert result.packages[0].identity == f"pkg-{hr.identity}"


def test_compile_manifest_identity_reflects_package() -> None:
    """The manifest identity is manifest-pkg-<harness_request_identity>."""
    env = standard_env()
    hr = hrequest(
        "node-research",
        work_package="wp-1",
        skills=(ref("skill", "skill-investigate"),),
    )
    request = CompilationRequest(harness_requests=(hr,))

    result = env.harness.service.compile(request)

    expected = f"manifest-pkg-{hr.identity}"
    assert result.manifests[0].identity == expected


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_compile_stores_package_in_repository() -> None:
    """The resulting ExecutionPackage is persisted in the packages repository."""
    env = standard_env()
    hr = hrequest(
        "node-research",
        work_package="wp-1",
        skills=(ref("skill", "skill-investigate"),),
    )
    request = CompilationRequest(harness_requests=(hr,))

    result = env.harness.service.compile(request)
    package = result.packages[0]

    stored = env.harness.repositories.execution_packages.get(package.identity)
    assert stored is not None
    assert stored.identity == package.identity


def test_compile_stores_manifest_in_repository() -> None:
    """The resulting ExecutionManifest is persisted in the manifests repository."""
    env = standard_env()
    hr = hrequest(
        "node-research",
        work_package="wp-1",
        skills=(ref("skill", "skill-investigate"),),
    )
    request = CompilationRequest(harness_requests=(hr,))

    result = env.harness.service.compile(request)
    manifest = result.manifests[0]

    stored = env.harness.repositories.execution_manifests.get(manifest.identity)
    assert stored is not None
    assert stored.identity == manifest.identity


def test_compile_repository_list_all_returns_package() -> None:
    """list_all() on the packages repository includes the compiled package."""
    env = standard_env()
    request = CompilationRequest(harness_requests=(hrequest("node-research", work_package="wp-1"),))

    result = env.harness.service.compile(request)
    all_packages = env.harness.repositories.execution_packages.list_all()

    assert result.packages[0] in all_packages


def test_compile_repository_count_after_compile() -> None:
    """The packages repository count is 1 after compiling a single request."""
    env = standard_env()
    request = CompilationRequest(harness_requests=(hrequest("node-research", work_package="wp-1"),))

    env.harness.service.compile(request)

    assert env.harness.repositories.execution_packages.count == 1
    assert env.harness.repositories.execution_manifests.count == 1


# ---------------------------------------------------------------------------
# Events — order, producer, uniqueness
# ---------------------------------------------------------------------------


def test_compile_emits_per_request_events_in_order() -> None:
    """The eight per-request event types appear in pipeline order."""
    env = standard_env()
    request = CompilationRequest(
        harness_requests=(
            hrequest(
                "node-research",
                work_package="wp-1",
                skills=(ref("skill", "skill-investigate"),),
            ),
        )
    )

    env.harness.service.compile(request)
    events = list(env.infrastructure.event_store.read_all())
    event_types = [e.type for e in events]

    for i, expected_type in enumerate(_PER_REQUEST_EVENT_TYPES):
        assert event_types[i] == expected_type, (
            f"position {i}: expected {expected_type!r}, got {event_types[i]!r}"
        )


def test_compile_emits_harness_completed_as_final_event() -> None:
    """harness.completed is always the last emitted event."""
    env = standard_env()
    request = CompilationRequest(harness_requests=(hrequest("node-research", work_package="wp-1"),))

    env.harness.service.compile(request)
    events = list(env.infrastructure.event_store.read_all())

    assert events[-1].type == HARNESS_COMPLETED


def test_compile_all_events_have_harness_producer() -> None:
    """Every emitted event carries producer='harness'."""
    env = standard_env()
    request = CompilationRequest(harness_requests=(hrequest("node-research", work_package="wp-1"),))

    env.harness.service.compile(request)
    events = list(env.infrastructure.event_store.read_all())

    for event in events:
        assert event.producer == "harness", f"event {event.identifier!r} has wrong producer"


def test_compile_event_identifiers_are_unique() -> None:
    """No two emitted events share the same identifier."""
    env = standard_env()
    request = CompilationRequest(harness_requests=(hrequest("node-research", work_package="wp-1"),))

    env.harness.service.compile(request)
    events = list(env.infrastructure.event_store.read_all())
    identifiers = [e.identifier for e in events]

    assert len(identifiers) == len(set(identifiers))


def test_compile_total_event_count_for_single_request() -> None:
    """One harness request emits 8 per-request events + 1 harness.completed = 9."""
    env = standard_env()
    request = CompilationRequest(harness_requests=(hrequest("node-research", work_package="wp-1"),))

    env.harness.service.compile(request)
    events = list(env.infrastructure.event_store.read_all())

    assert len(events) == len(_PER_REQUEST_EVENT_TYPES) + 1


# ---------------------------------------------------------------------------
# Multiple requests
# ---------------------------------------------------------------------------


def test_compile_two_requests_produces_two_packages() -> None:
    """Two harness requests in one batch yield exactly two packages."""
    from tests.unit.nexus_harness.helpers import (
        capability,
        context_package,
        harness_env,
        skill,
        strategy,
        work_package,
    )

    env = harness_env(
        skills=(skill("skill-investigate", capabilities=("cap-analysis",)),),
        capabilities=(capability("cap-analysis"),),
        context_packages=(context_package(),),
        work_packages=(
            work_package("wp-1", skills=(ref("skill", "skill-investigate"),)),
            work_package("wp-2", skills=(ref("skill", "skill-investigate"),)),
        ),
        strategies=(strategy(),),
    )
    request = CompilationRequest(
        harness_requests=(
            hrequest("node-a", work_package="wp-1"),
            hrequest("node-b", work_package="wp-2"),
        )
    )

    result = env.harness.service.compile(request)

    assert len(result.packages) == 2
    assert len(result.manifests) == 2


def test_compile_two_requests_emits_single_trailing_completed() -> None:
    """A two-request batch ends with exactly one harness.completed event."""
    from tests.unit.nexus_harness.helpers import (
        capability,
        context_package,
        harness_env,
        skill,
        strategy,
        work_package,
    )

    env = harness_env(
        skills=(skill("skill-investigate", capabilities=("cap-analysis",)),),
        capabilities=(capability("cap-analysis"),),
        context_packages=(context_package(),),
        work_packages=(
            work_package("wp-1", skills=(ref("skill", "skill-investigate"),)),
            work_package("wp-2", skills=(ref("skill", "skill-investigate"),)),
        ),
        strategies=(strategy(),),
    )
    request = CompilationRequest(
        harness_requests=(
            hrequest("node-a", work_package="wp-1"),
            hrequest("node-b", work_package="wp-2"),
        )
    )

    env.harness.service.compile(request)
    events = list(env.infrastructure.event_store.read_all())
    completed_events = [e for e in events if e.type == HARNESS_COMPLETED]

    assert len(completed_events) == 1
    assert events[-1].type == HARNESS_COMPLETED


def test_compile_two_requests_repositories_hold_two_entries() -> None:
    """Two requests: both packages and manifests appear in their repositories."""
    from tests.unit.nexus_harness.helpers import (
        capability,
        context_package,
        harness_env,
        skill,
        strategy,
        work_package,
    )

    env = harness_env(
        skills=(skill("skill-investigate", capabilities=("cap-analysis",)),),
        capabilities=(capability("cap-analysis"),),
        context_packages=(context_package(),),
        work_packages=(
            work_package("wp-1", skills=(ref("skill", "skill-investigate"),)),
            work_package("wp-2", skills=(ref("skill", "skill-investigate"),)),
        ),
        strategies=(strategy(),),
    )
    request = CompilationRequest(
        harness_requests=(
            hrequest("node-a", work_package="wp-1"),
            hrequest("node-b", work_package="wp-2"),
        )
    )

    env.harness.service.compile(request)

    assert env.harness.repositories.execution_packages.count == 2
    assert env.harness.repositories.execution_manifests.count == 2


# ---------------------------------------------------------------------------
# Empty batch
# ---------------------------------------------------------------------------


def test_compile_empty_batch_does_not_raise() -> None:
    """An empty harness_requests tuple does not raise."""
    env = standard_env()
    request = CompilationRequest(harness_requests=())

    result = env.harness.service.compile(request)

    assert isinstance(result, CompilationResult)


def test_compile_empty_batch_returns_empty_packages() -> None:
    """An empty batch yields an empty packages tuple."""
    env = standard_env()
    request = CompilationRequest(harness_requests=())

    result = env.harness.service.compile(request)

    assert result.packages == ()
    assert result.manifests == ()


def test_compile_empty_batch_emits_harness_completed() -> None:
    """An empty batch still emits harness.completed."""
    env = standard_env()
    request = CompilationRequest(harness_requests=())

    env.harness.service.compile(request)
    events = list(env.infrastructure.event_store.read_all())

    assert len(events) == 1
    assert events[0].type == HARNESS_COMPLETED


# ---------------------------------------------------------------------------
# Fail path — UnresolvedReferenceError + harness.failed
# ---------------------------------------------------------------------------


def test_compile_raises_unresolved_reference_error_when_work_package_missing() -> None:
    """compile() raises UnresolvedReferenceError when the work package is absent."""
    env = harness_env()  # empty — nothing registered
    request = CompilationRequest(
        harness_requests=(hrequest("node-ghost", work_package="wp-missing"),)
    )

    with pytest.raises(UnresolvedReferenceError):
        env.harness.service.compile(request)


def test_compile_emits_harness_failed_on_unresolved_reference() -> None:
    """On UnresolvedReferenceError, harness.failed is emitted to the event store."""
    env = harness_env()  # empty — nothing registered
    request = CompilationRequest(
        harness_requests=(hrequest("node-ghost", work_package="wp-missing"),)
    )

    with pytest.raises(UnresolvedReferenceError):
        env.harness.service.compile(request)

    events = list(env.infrastructure.event_store.read_all())
    failed_events = [e for e in events if e.type == HARNESS_FAILED]
    assert len(failed_events) == 1


def test_compile_harness_failed_event_has_harness_producer() -> None:
    """The harness.failed event carries producer='harness'."""
    env = harness_env()
    request = CompilationRequest(
        harness_requests=(hrequest("node-ghost", work_package="wp-missing"),)
    )

    with pytest.raises(UnresolvedReferenceError):
        env.harness.service.compile(request)

    events = list(env.infrastructure.event_store.read_all())
    failed = next(e for e in events if e.type == HARNESS_FAILED)
    assert failed.producer == "harness"


def test_compile_raises_and_emits_failed_on_missing_context() -> None:
    """compile() raises and emits harness.failed when the context package is absent."""
    from tests.unit.nexus_harness.helpers import harness_env, work_package

    env = harness_env(work_packages=(work_package("wp-1"),))
    request = CompilationRequest(
        harness_requests=(hrequest("node-ghost", work_package="wp-1", context="ctx-missing"),)
    )

    with pytest.raises(UnresolvedReferenceError):
        env.harness.service.compile(request)

    events = list(env.infrastructure.event_store.read_all())
    assert any(e.type == HARNESS_FAILED for e in events)


def test_compile_does_not_persist_on_failure() -> None:
    """When compile() fails, nothing is stored in the repositories."""
    env = harness_env()
    request = CompilationRequest(
        harness_requests=(hrequest("node-ghost", work_package="wp-missing"),)
    )

    with pytest.raises(UnresolvedReferenceError):
        env.harness.service.compile(request)

    assert env.harness.repositories.execution_packages.count == 0
    assert env.harness.repositories.execution_manifests.count == 0
