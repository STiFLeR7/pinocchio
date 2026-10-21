"""Unit tests for nexus_harness.package_builder.

Covers ExecutionPackageBuilder.build():
- Returns an ExecutionPackage with the correct identity (pkg-{request.identity}).
- harness_request_ref has target_type "harness_request" and the request identity.
- session_ref is copied from the request.
- node is copied from the request.
- work_package is the resolved WorkPackage embedded directly.
- context_view is the ContextView produced by the context resolver.
- skill_refs is a tuple of References derived from ResolvedSkills.
- capability_requirements is a tuple of References derived from ResolvedCapabilities.
- policy_bundle is the PolicyBundle produced by the policy resolver.
- artifact_refs is a tuple of References derived from ResolvedArtifacts.
- execution_strategy is the ValidatedRequest.strategy (may be None).
- coordination is copied from the request.
- metadata dict contains all seven expected keys with correct values.
- correlation carries the given correlation_identifier.
- status is PackageStatus.COMPILED.
- The package is frozen (mutations are rejected).
- Determinism: building twice with the same inputs yields equal packages.
- Empty resolved collections produce empty tuples (not None).
"""

from __future__ import annotations

import pytest

from nexus_harness import (
    ArtifactResolver,
    CapabilityResolver,
    ContextResolver,
    ExecutionPackageBuilder,
    HarnessValidator,
    PackageStatus,
    PolicyResolver,
    SkillResolver,
)
from nexus_harness.vocabulary import HARNESS_REQUEST_TARGET_TYPE
from tests.unit.nexus_harness.helpers import (
    HarnessEnv,
    artifact,
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

_CORRELATION = "cor-test-package"


def _build_package(env: HarnessEnv, request, *, correlation: str = _CORRELATION):
    """Run the full resolve → build pipeline and return the ExecutionPackage."""
    sources = env.harness.sources
    validated = HarnessValidator(sources).validate(request)
    resolved_skills = SkillResolver(sources.skills).resolve(request)
    resolved_capabilities = CapabilityResolver(sources.capabilities).resolve(
        request, resolved_skills
    )
    policies = PolicyResolver(sources.policies).resolve(request, validated.strategy)
    context_view = ContextResolver().resolve(validated.context_package)
    artifacts = ArtifactResolver(sources).resolve(request.identity, validated.work_package)
    return ExecutionPackageBuilder().build(
        validated,
        skills=resolved_skills,
        capabilities=resolved_capabilities,
        policies=policies,
        context=context_view,
        artifacts=artifacts,
        correlation_identifier=correlation,
    )


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def test_package_identity_is_pkg_prefixed() -> None:
    """ExecutionPackage.identity is 'pkg-{request.identity}'."""
    env = standard_env()
    request = hrequest("node-1")
    pkg = _build_package(env, request)
    assert pkg.identity == f"pkg-{request.identity}"


# ---------------------------------------------------------------------------
# harness_request_ref
# ---------------------------------------------------------------------------


def test_harness_request_ref_target_type() -> None:
    """harness_request_ref.target_type is the canonical 'harness_request' string."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    assert pkg.harness_request_ref.target_type == HARNESS_REQUEST_TARGET_TYPE


def test_harness_request_ref_identifier_matches_request() -> None:
    """harness_request_ref.identifier equals the Harness Request identity."""
    env = standard_env()
    request = hrequest("node-1", identity="hreq-custom-42")
    pkg = _build_package(env, request)
    assert pkg.harness_request_ref.identifier == "hreq-custom-42"


# ---------------------------------------------------------------------------
# session_ref
# ---------------------------------------------------------------------------


def test_session_ref_copied_from_request() -> None:
    """session_ref on the package is the same Reference as on the request."""
    env = standard_env()
    request = hrequest("node-1")
    pkg = _build_package(env, request)
    assert pkg.session_ref == request.session_ref


# ---------------------------------------------------------------------------
# node
# ---------------------------------------------------------------------------


def test_node_copied_from_request() -> None:
    """node on the package echoes the request's node identifier."""
    env = standard_env()
    request = hrequest("node-42")
    pkg = _build_package(env, request)
    assert pkg.node == "node-42"


# ---------------------------------------------------------------------------
# work_package (embedded)
# ---------------------------------------------------------------------------


def test_work_package_is_embedded_directly() -> None:
    """The resolved WorkPackage is embedded (not referenced) in the package."""
    env = standard_env()
    request = hrequest("node-1")
    pkg = _build_package(env, request)
    assert pkg.work_package.identifier == "wp-1"


# ---------------------------------------------------------------------------
# context_view
# ---------------------------------------------------------------------------


def test_context_view_identity_matches_context_package() -> None:
    """context_view.identity echoes the Context Package identity."""
    env = harness_env(
        context_packages=(context_package("ctx-custom"),),
        work_packages=(work_package("wp-1"),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", context="ctx-custom")
    pkg = _build_package(env, request)
    assert pkg.context_view.identity == "ctx-custom"


# ---------------------------------------------------------------------------
# skill_refs
# ---------------------------------------------------------------------------


def test_skill_refs_empty_when_no_skills_resolved() -> None:
    """skill_refs is an empty tuple when the request carries no skill refs."""
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", skills=())
    pkg = _build_package(env, request)
    assert pkg.skill_refs == ()


def test_skill_refs_tuple_of_references() -> None:
    """skill_refs contains one Reference per resolved skill."""
    env = harness_env(
        skills=(skill("skill-alpha", capabilities=("cap-x",)),),
        capabilities=(capability("cap-x"),),
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1", skills=(ref("skill", "skill-alpha"),)),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", skills=(ref("skill", "skill-alpha"),))
    pkg = _build_package(env, request)
    assert len(pkg.skill_refs) == 1
    assert pkg.skill_refs[0].target_type == "skill"
    assert pkg.skill_refs[0].identifier == "skill-alpha"


def test_skill_refs_target_types_are_skill() -> None:
    """Every Reference in skill_refs has target_type 'skill'."""
    env = harness_env(
        skills=(
            skill("skill-a"),
            skill("skill-b"),
        ),
        context_packages=(context_package(),),
        work_packages=(
            work_package(
                "wp-1",
                skills=(ref("skill", "skill-a"), ref("skill", "skill-b")),
            ),
        ),
        strategies=(strategy(),),
    )
    request = hrequest(
        "node-1",
        skills=(ref("skill", "skill-a"), ref("skill", "skill-b")),
    )
    pkg = _build_package(env, request)
    assert all(r.target_type == "skill" for r in pkg.skill_refs)


# ---------------------------------------------------------------------------
# capability_requirements
# ---------------------------------------------------------------------------


def test_capability_requirements_empty_when_no_capabilities() -> None:
    """capability_requirements is empty when no capabilities are required."""
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1")
    pkg = _build_package(env, request)
    assert pkg.capability_requirements == ()


def test_capability_requirements_populated_from_skills() -> None:
    """capability_requirements carries the refs for capabilities implied by skills."""
    env = harness_env(
        skills=(skill("skill-investigate", capabilities=("cap-analysis",)),),
        capabilities=(capability("cap-analysis"),),
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1", skills=(ref("skill", "skill-investigate"),)),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", skills=(ref("skill", "skill-investigate"),))
    pkg = _build_package(env, request)
    assert len(pkg.capability_requirements) == 1
    assert pkg.capability_requirements[0].identifier == "cap-analysis"


# ---------------------------------------------------------------------------
# policy_bundle
# ---------------------------------------------------------------------------


def test_policy_bundle_is_present() -> None:
    """policy_bundle is a PolicyBundle on the compiled package."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    assert pkg.policy_bundle is not None


def test_policy_bundle_approval_taxonomy_from_strategy() -> None:
    """policy_bundle.approval_taxonomy echoes the strategy's approval policy."""
    from nexus_core.contracts.enums import ApprovalTaxonomy

    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
        strategies=(strategy(approval_policy=ApprovalTaxonomy.HUMAN_REVIEW),),
    )
    request = hrequest("node-1")
    pkg = _build_package(env, request)
    assert pkg.policy_bundle.approval_taxonomy == ApprovalTaxonomy.HUMAN_REVIEW.value


# ---------------------------------------------------------------------------
# artifact_refs
# ---------------------------------------------------------------------------


def test_artifact_refs_empty_when_no_inputs() -> None:
    """artifact_refs is empty when the work package has no artifact inputs."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    assert pkg.artifact_refs == ()


def test_artifact_refs_populated_from_work_package_inputs() -> None:
    """artifact_refs contains one Reference per artifact input on the work package."""
    art = artifact("art-doc-1")
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1", inputs=(ref("artifact", "art-doc-1"),)),),
        strategies=(strategy(),),
        artifacts=(art,),
    )
    request = hrequest("node-1")
    pkg = _build_package(env, request)
    assert len(pkg.artifact_refs) == 1
    assert pkg.artifact_refs[0].identifier == "art-doc-1"


# ---------------------------------------------------------------------------
# execution_strategy
# ---------------------------------------------------------------------------


def test_execution_strategy_is_none_when_no_strategy_ref() -> None:
    """execution_strategy is None when the request carries no strategy reference."""
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
    )
    request = hrequest("node-1", strategy_ref=None)
    pkg = _build_package(env, request)
    assert pkg.execution_strategy is None


def test_execution_strategy_populated_from_validated_request() -> None:
    """execution_strategy is the resolved ExecutionStrategy from the validated request."""
    strat = strategy("strat-explicit")
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
        strategies=(strat,),
    )
    request = hrequest("node-1", strategy_ref="strat-explicit")
    pkg = _build_package(env, request)
    assert pkg.execution_strategy is not None
    assert pkg.execution_strategy.identity == "strat-explicit"


# ---------------------------------------------------------------------------
# coordination
# ---------------------------------------------------------------------------


def test_coordination_copied_from_request() -> None:
    """coordination on the package matches the request's coordination model."""
    from nexus_core.contracts.enums import CoordinationModel

    env = standard_env()
    request = hrequest("node-1", coordination=CoordinationModel.SEQUENTIAL)
    pkg = _build_package(env, request)
    assert pkg.coordination == CoordinationModel.SEQUENTIAL


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------


def test_metadata_contains_node_key() -> None:
    """metadata['node'] equals the request node."""
    env = standard_env()
    request = hrequest("node-99")
    pkg = _build_package(env, request)
    assert pkg.metadata["node"] == "node-99"


def test_metadata_contains_session_key() -> None:
    """metadata['session'] equals the session reference identifier."""
    env = standard_env()
    request = hrequest("node-1")
    pkg = _build_package(env, request)
    assert pkg.metadata["session"] == request.session_ref.identifier


def test_metadata_contains_work_package_key() -> None:
    """metadata['work_package'] equals the work package reference identifier."""
    env = standard_env()
    request = hrequest("node-1", work_package="wp-1")
    pkg = _build_package(env, request)
    assert pkg.metadata["work_package"] == "wp-1"


def test_metadata_contains_context_key() -> None:
    """metadata['context'] equals the context view identity."""
    env = standard_env()
    request = hrequest("node-1")
    pkg = _build_package(env, request)
    assert pkg.metadata["context"] == pkg.context_view.identity


def test_metadata_skill_count_matches_skill_refs() -> None:
    """metadata['skill_count'] equals the number of skill_refs."""
    env = standard_env()
    request = hrequest("node-1", skills=(ref("skill", "skill-investigate"),))
    pkg = _build_package(env, request)
    assert pkg.metadata["skill_count"] == len(pkg.skill_refs)


def test_metadata_capability_count_matches_capability_requirements() -> None:
    """metadata['capability_count'] equals the number of capability_requirements."""
    env = standard_env()
    request = hrequest("node-1", skills=(ref("skill", "skill-investigate"),))
    pkg = _build_package(env, request)
    assert pkg.metadata["capability_count"] == len(pkg.capability_requirements)


def test_metadata_policy_count_matches_bundle() -> None:
    """metadata['policy_count'] equals the number of policies in the bundle."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    assert pkg.metadata["policy_count"] == len(pkg.policy_bundle.policies)


def test_metadata_artifact_count_when_no_artifacts() -> None:
    """metadata['artifact_count'] is 0 when no artifacts are required."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    assert pkg.metadata["artifact_count"] == 0


# ---------------------------------------------------------------------------
# correlation
# ---------------------------------------------------------------------------


def test_correlation_identifier_set_from_argument() -> None:
    """correlation.correlation_identifier matches the correlation_identifier argument."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"), correlation="cor-explicit-99")
    assert pkg.correlation.correlation_identifier == "cor-explicit-99"


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_is_compiled() -> None:
    """A successfully built package always has status PackageStatus.COMPILED."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    assert pkg.status == PackageStatus.COMPILED


# ---------------------------------------------------------------------------
# Immutability (frozen)
# ---------------------------------------------------------------------------


def test_package_rejects_mutation_of_identity() -> None:
    """ExecutionPackage.identity is immutable — assignment raises ValueError."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    with pytest.raises(ValueError):
        pkg.identity = "tampered"  # type: ignore[misc]


def test_package_rejects_mutation_of_status() -> None:
    """ExecutionPackage.status is immutable — assignment raises ValueError."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    with pytest.raises(ValueError):
        pkg.status = None  # type: ignore[misc]


def test_package_rejects_mutation_of_skill_refs() -> None:
    """ExecutionPackage.skill_refs is immutable — assignment raises ValueError."""
    env = harness_env(
        skills=(skill("skill-investigate", capabilities=("cap-analysis",)),),
        capabilities=(capability("cap-analysis"),),
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1", skills=(ref("skill", "skill-investigate"),)),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", skills=(ref("skill", "skill-investigate"),))
    pkg = _build_package(env, request)
    with pytest.raises(ValueError):
        pkg.skill_refs = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_building_twice_yields_equal_packages() -> None:
    """Building with identical inputs twice produces structurally equal packages."""
    env = standard_env()
    request = hrequest("node-1")
    pkg1 = _build_package(env, request)
    pkg2 = _build_package(env, request)
    assert pkg1 == pkg2


def test_determinism_with_skill_and_capability() -> None:
    """Determinism holds for a request with skills and capabilities resolved."""
    env = harness_env(
        skills=(skill("skill-investigate", capabilities=("cap-analysis",)),),
        capabilities=(capability("cap-analysis"),),
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1", skills=(ref("skill", "skill-investigate"),)),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", skills=(ref("skill", "skill-investigate"),))
    assert _build_package(env, request) == _build_package(env, request)


def test_determinism_with_artifact_input() -> None:
    """Determinism holds when the work package carries an artifact input."""
    art = artifact("art-doc-1")
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1", inputs=(ref("artifact", "art-doc-1"),)),),
        strategies=(strategy(),),
        artifacts=(art,),
    )
    request = hrequest("node-1")
    assert _build_package(env, request) == _build_package(env, request)


# ---------------------------------------------------------------------------
# No strategy branch
# ---------------------------------------------------------------------------


def test_package_without_strategy_has_none_execution_strategy() -> None:
    """When the request has no strategy ref, execution_strategy is None."""
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
    )
    request = hrequest("node-1", strategy_ref=None)
    pkg = _build_package(env, request)
    assert pkg.execution_strategy is None


def test_package_without_strategy_is_still_compiled() -> None:
    """Status is COMPILED even when no strategy is attached."""
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
    )
    request = hrequest("node-1", strategy_ref=None)
    pkg = _build_package(env, request)
    assert pkg.status == PackageStatus.COMPILED
