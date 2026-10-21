"""Unit tests for the Phase 6 determinism guarantee.

The headline guarantee: given identical HarnessRequests and identical resolution
sources, two independent HarnessService instances (with a FixedTimestampSource)
produce byte-for-byte equal CompilationResults and identical event streams.

Also verifies that reordering skill references on a request does not change the
compiled package (the SkillResolver sorts by identifier before resolving).
"""

from __future__ import annotations

from nexus_harness import CompilationRequest, FixedTimestampSource
from tests.unit.nexus_harness.helpers import (
    capability,
    context_package,
    harness_env,
    hrequest,
    ref,
    skill,
    standard_env,
    strategy,
    work_package,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _two_envs():
    """Return two independent standard environments sharing no state."""
    return standard_env(), standard_env()


def _single_request() -> CompilationRequest:
    return CompilationRequest(
        harness_requests=(
            hrequest(
                "node-research",
                work_package="wp-1",
                skills=(ref("skill", "skill-investigate"),),
            ),
        )
    )


# ---------------------------------------------------------------------------
# Identical packages across two independent environments
# ---------------------------------------------------------------------------


def test_two_runs_produce_equal_packages() -> None:
    """Two compilations of the same request in independent envs yield equal packages."""
    env1, env2 = _two_envs()
    request = _single_request()

    result1 = env1.harness.service.compile(request)
    result2 = env2.harness.service.compile(request)

    assert result1.packages == result2.packages


def test_two_runs_produce_equal_manifests() -> None:
    """Two compilations of the same request in independent envs yield equal manifests."""
    env1, env2 = _two_envs()
    request = _single_request()

    result1 = env1.harness.service.compile(request)
    result2 = env2.harness.service.compile(request)

    assert result1.manifests == result2.manifests


def test_two_runs_produce_equal_package_identities() -> None:
    """Package identities are pure functions of the request identity — no randomness."""
    env1, env2 = _two_envs()
    request = _single_request()

    result1 = env1.harness.service.compile(request)
    result2 = env2.harness.service.compile(request)

    ids1 = tuple(p.identity for p in result1.packages)
    ids2 = tuple(p.identity for p in result2.packages)
    assert ids1 == ids2


def test_two_runs_produce_equal_manifest_identities() -> None:
    """Manifest identities are pure functions of the package identity — no randomness."""
    env1, env2 = _two_envs()
    request = _single_request()

    result1 = env1.harness.service.compile(request)
    result2 = env2.harness.service.compile(request)

    ids1 = tuple(m.identity for m in result1.manifests)
    ids2 = tuple(m.identity for m in result2.manifests)
    assert ids1 == ids2


# ---------------------------------------------------------------------------
# Identical event streams across two independent environments
# ---------------------------------------------------------------------------


def test_two_runs_emit_equal_event_types_in_order() -> None:
    """Both runs emit the same ordered sequence of event types."""
    env1, env2 = _two_envs()
    request = _single_request()

    env1.harness.service.compile(request)
    env2.harness.service.compile(request)

    types1 = [e.type for e in env1.infrastructure.event_store.read_all()]
    types2 = [e.type for e in env2.infrastructure.event_store.read_all()]
    assert types1 == types2


def test_two_runs_emit_equal_event_identifiers() -> None:
    """Both runs emit events with identical identifiers (deterministic event ids)."""
    env1, env2 = _two_envs()
    request = _single_request()

    env1.harness.service.compile(request)
    env2.harness.service.compile(request)

    ids1 = [e.identifier for e in env1.infrastructure.event_store.read_all()]
    ids2 = [e.identifier for e in env2.infrastructure.event_store.read_all()]
    assert ids1 == ids2


def test_two_runs_emit_equal_event_payloads() -> None:
    """Both runs emit events with identical payloads."""
    env1, env2 = _two_envs()
    request = _single_request()

    env1.harness.service.compile(request)
    env2.harness.service.compile(request)

    payloads1 = [e.payload for e in env1.infrastructure.event_store.read_all()]
    payloads2 = [e.payload for e in env2.infrastructure.event_store.read_all()]
    assert payloads1 == payloads2


def test_two_runs_emit_equal_event_timestamps() -> None:
    """Both runs emit events with identical timestamps (FixedTimestampSource)."""
    env1, env2 = _two_envs()
    request = _single_request()

    env1.harness.service.compile(request)
    env2.harness.service.compile(request)

    ts1 = [e.timestamp for e in env1.infrastructure.event_store.read_all()]
    ts2 = [e.timestamp for e in env2.infrastructure.event_store.read_all()]
    assert ts1 == ts2


def test_two_runs_full_event_equality() -> None:
    """All event fields (id, type, payload, timestamp) match between two runs."""
    env1, env2 = _two_envs()
    request = _single_request()

    env1.harness.service.compile(request)
    env2.harness.service.compile(request)

    events1 = list(env1.infrastructure.event_store.read_all())
    events2 = list(env2.infrastructure.event_store.read_all())
    assert events1 == events2


# ---------------------------------------------------------------------------
# Skill-ref order independence — resolvers sort inputs
# ---------------------------------------------------------------------------


def test_reordered_skill_refs_produce_equal_package() -> None:
    """Reversing the order of skill refs on the request does not change the package."""
    skill_a = skill("skill-alpha", capabilities=("cap-analysis",))
    skill_b = skill("skill-beta", capabilities=("cap-analysis",))
    cap = capability("cap-analysis")
    ctx = context_package()
    wp_a = work_package(
        "wp-multi",
        skills=(
            ref("skill", "skill-alpha"),
            ref("skill", "skill-beta"),
        ),
    )
    strat = strategy()

    env1 = harness_env(
        skills=(skill_a, skill_b),
        capabilities=(cap,),
        context_packages=(ctx,),
        work_packages=(wp_a,),
        strategies=(strat,),
    )
    env2 = harness_env(
        skills=(skill_a, skill_b),
        capabilities=(cap,),
        context_packages=(ctx,),
        work_packages=(wp_a,),
        strategies=(strat,),
    )

    request_forward = CompilationRequest(
        harness_requests=(
            hrequest(
                "node-multi",
                work_package="wp-multi",
                skills=(
                    ref("skill", "skill-alpha"),
                    ref("skill", "skill-beta"),
                ),
            ),
        )
    )
    request_reversed = CompilationRequest(
        harness_requests=(
            hrequest(
                "node-multi",
                work_package="wp-multi",
                skills=(
                    ref("skill", "skill-beta"),
                    ref("skill", "skill-alpha"),
                ),
            ),
        )
    )

    result_forward = env1.harness.service.compile(request_forward)
    result_reversed = env2.harness.service.compile(request_reversed)

    assert result_forward.packages == result_reversed.packages


def test_reordered_skill_refs_produce_equal_manifest() -> None:
    """Reversing skill refs produces an equal manifest (sorted resolver)."""
    skill_a = skill("skill-alpha", capabilities=("cap-analysis",))
    skill_b = skill("skill-beta", capabilities=("cap-analysis",))
    cap = capability("cap-analysis")
    ctx = context_package()
    wp_a = work_package("wp-multi")
    strat = strategy()

    env1 = harness_env(
        skills=(skill_a, skill_b),
        capabilities=(cap,),
        context_packages=(ctx,),
        work_packages=(wp_a,),
        strategies=(strat,),
    )
    env2 = harness_env(
        skills=(skill_a, skill_b),
        capabilities=(cap,),
        context_packages=(ctx,),
        work_packages=(wp_a,),
        strategies=(strat,),
    )

    request_forward = CompilationRequest(
        harness_requests=(
            hrequest(
                "node-multi",
                work_package="wp-multi",
                skills=(
                    ref("skill", "skill-alpha"),
                    ref("skill", "skill-beta"),
                ),
            ),
        )
    )
    request_reversed = CompilationRequest(
        harness_requests=(
            hrequest(
                "node-multi",
                work_package="wp-multi",
                skills=(
                    ref("skill", "skill-beta"),
                    ref("skill", "skill-alpha"),
                ),
            ),
        )
    )

    result_forward = env1.harness.service.compile(request_forward)
    result_reversed = env2.harness.service.compile(request_reversed)

    assert result_forward.manifests == result_reversed.manifests


# ---------------------------------------------------------------------------
# Fixed timestamp source pinned value
# ---------------------------------------------------------------------------


def test_fixed_timestamp_source_pins_value() -> None:
    """FixedTimestampSource always returns the same timestamp string."""
    ts = FixedTimestampSource("1970-01-01T00:00:00+00:00")
    assert ts.now() == "1970-01-01T00:00:00+00:00"
    assert ts.now() == ts.now()


def test_two_runs_with_explicit_fixed_source_produce_equal_event_timestamps() -> None:
    """Explicitly constructing two FixedTimestampSource instances pins timestamps."""
    env1, env2 = _two_envs()
    request = _single_request()

    env1.harness.service.compile(request)
    env2.harness.service.compile(request)

    ts1 = {e.timestamp for e in env1.infrastructure.event_store.read_all()}
    ts2 = {e.timestamp for e in env2.infrastructure.event_store.read_all()}
    assert ts1 == ts2
    assert len(ts1) == 1  # Only one distinct timestamp value
