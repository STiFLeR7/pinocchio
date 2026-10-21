"""Unit tests for nexus_harness.manifest_builder.

Covers ExecutionManifestBuilder.build():
- Returns an ExecutionManifest with identity 'manifest-{package.identity}'.
- package_ref has target_type "execution_package" and the package identity.
- node is copied from the package.
- required_capabilities == package.capability_requirements.
- required_skills == package.skill_refs.
- required_artifacts == package.artifact_refs.
- required_context == package.context_view.reference.
- execution_metadata dict contains node, coordination, work_package,
  approval_taxonomy, and policy_count with correct values.
- runtime_requirements == dict(strategy.runtime_policy) when strategy present.
- runtime_requirements == {} when package.execution_strategy is None.
- correlation copied from the package.
- status == ManifestStatus.CREATED.
- The manifest is frozen (mutations are rejected).
- Determinism: building twice from the same package yields equal manifests.
- The manifest is purely descriptive — it carries no executable content.
"""

from __future__ import annotations

import pytest

from nexus_harness import (
    ArtifactResolver,
    CapabilityResolver,
    ContextResolver,
    ExecutionManifestBuilder,
    ExecutionPackageBuilder,
    HarnessValidator,
    ManifestStatus,
    PolicyResolver,
    SkillResolver,
)
from nexus_harness.vocabulary import EXECUTION_PACKAGE_TARGET_TYPE
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

_CORRELATION = "cor-test-manifest"


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


def _build_manifest(env: HarnessEnv, request, *, correlation: str = _CORRELATION):
    """Build a package then build and return its manifest."""
    pkg = _build_package(env, request, correlation=correlation)
    return ExecutionManifestBuilder().build(pkg)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def test_manifest_identity_is_manifest_prefixed() -> None:
    """ExecutionManifest.identity is 'manifest-{package.identity}'."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.identity == f"manifest-{pkg.identity}"


# ---------------------------------------------------------------------------
# package_ref
# ---------------------------------------------------------------------------


def test_package_ref_target_type_is_execution_package() -> None:
    """package_ref.target_type is the canonical 'execution_package' string."""
    env = standard_env()
    manifest = _build_manifest(env, hrequest("node-1"))
    assert manifest.package_ref.target_type == EXECUTION_PACKAGE_TARGET_TYPE


def test_package_ref_identifier_matches_package_identity() -> None:
    """package_ref.identifier equals the package identity."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.package_ref.identifier == pkg.identity


# ---------------------------------------------------------------------------
# node
# ---------------------------------------------------------------------------


def test_node_copied_from_package() -> None:
    """node on the manifest echoes the package's node."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-77"))
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.node == pkg.node


# ---------------------------------------------------------------------------
# required_capabilities
# ---------------------------------------------------------------------------


def test_required_capabilities_equals_package_capability_requirements() -> None:
    """required_capabilities is identical to package.capability_requirements."""
    env = harness_env(
        skills=(skill("skill-investigate", capabilities=("cap-analysis",)),),
        capabilities=(capability("cap-analysis"),),
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1", skills=(ref("skill", "skill-investigate"),)),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", skills=(ref("skill", "skill-investigate"),))
    pkg = _build_package(env, request)
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.required_capabilities == pkg.capability_requirements


def test_required_capabilities_empty_when_none() -> None:
    """required_capabilities is empty when the package has no capability requirements."""
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
        strategies=(strategy(),),
    )
    manifest = _build_manifest(env, hrequest("node-1"))
    assert manifest.required_capabilities == ()


# ---------------------------------------------------------------------------
# required_skills
# ---------------------------------------------------------------------------


def test_required_skills_equals_package_skill_refs() -> None:
    """required_skills is identical to package.skill_refs."""
    env = harness_env(
        skills=(skill("skill-investigate", capabilities=("cap-analysis",)),),
        capabilities=(capability("cap-analysis"),),
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1", skills=(ref("skill", "skill-investigate"),)),),
        strategies=(strategy(),),
    )
    request = hrequest("node-1", skills=(ref("skill", "skill-investigate"),))
    pkg = _build_package(env, request)
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.required_skills == pkg.skill_refs


def test_required_skills_empty_when_none() -> None:
    """required_skills is empty when the package has no skill refs."""
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
        strategies=(strategy(),),
    )
    manifest = _build_manifest(env, hrequest("node-1"))
    assert manifest.required_skills == ()


# ---------------------------------------------------------------------------
# required_artifacts
# ---------------------------------------------------------------------------


def test_required_artifacts_equals_package_artifact_refs() -> None:
    """required_artifacts is identical to package.artifact_refs."""
    art = artifact("art-report-1")
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1", inputs=(ref("artifact", "art-report-1"),)),),
        strategies=(strategy(),),
        artifacts=(art,),
    )
    pkg = _build_package(env, hrequest("node-1"))
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.required_artifacts == pkg.artifact_refs


def test_required_artifacts_empty_when_no_inputs() -> None:
    """required_artifacts is empty when the work package has no artifact inputs."""
    env = standard_env()
    manifest = _build_manifest(env, hrequest("node-1"))
    assert manifest.required_artifacts == ()


# ---------------------------------------------------------------------------
# required_context
# ---------------------------------------------------------------------------


def test_required_context_equals_context_view_reference() -> None:
    """required_context is the Reference from package.context_view.reference."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.required_context == pkg.context_view.reference


def test_required_context_target_type_is_context_package() -> None:
    """required_context.target_type is 'context_package'."""
    env = standard_env()
    manifest = _build_manifest(env, hrequest("node-1"))
    assert manifest.required_context.target_type == "context_package"


# ---------------------------------------------------------------------------
# execution_metadata
# ---------------------------------------------------------------------------


def test_execution_metadata_contains_node() -> None:
    """execution_metadata['node'] equals the package node."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-5"))
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.execution_metadata["node"] == pkg.node


def test_execution_metadata_contains_coordination() -> None:
    """execution_metadata['coordination'] equals the package coordination value."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.execution_metadata["coordination"] == pkg.coordination.value


def test_execution_metadata_contains_work_package() -> None:
    """execution_metadata['work_package'] equals the work package identifier."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1", work_package="wp-1"))
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.execution_metadata["work_package"] == pkg.work_package.identifier


def test_execution_metadata_contains_approval_taxonomy() -> None:
    """execution_metadata['approval_taxonomy'] equals the policy bundle's taxonomy."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.execution_metadata["approval_taxonomy"] == pkg.policy_bundle.approval_taxonomy


def test_execution_metadata_contains_policy_count() -> None:
    """execution_metadata['policy_count'] equals the number of policies in the bundle."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.execution_metadata["policy_count"] == len(pkg.policy_bundle.policies)


# ---------------------------------------------------------------------------
# runtime_requirements — WITH strategy
# ---------------------------------------------------------------------------


def test_runtime_requirements_populated_from_strategy_runtime_policy() -> None:
    """runtime_requirements == dict(strategy.runtime_policy) when a strategy is present."""
    strat = strategy("strat-runtime", runtime_policy={"timeout": 60, "memory": "2Gi"})
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
        strategies=(strat,),
    )
    request = hrequest("node-1", strategy_ref="strat-runtime")
    pkg = _build_package(env, request)
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.runtime_requirements == dict(strat.runtime_policy)


def test_runtime_requirements_non_empty_when_strategy_has_runtime_policy() -> None:
    """runtime_requirements is non-empty when the strategy's runtime_policy is non-empty."""
    strat = strategy("strat-rich", runtime_policy={"cpu": "500m"})
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
        strategies=(strat,),
    )
    request = hrequest("node-1", strategy_ref="strat-rich")
    pkg = _build_package(env, request)
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.runtime_requirements != {}


# ---------------------------------------------------------------------------
# runtime_requirements — WITHOUT strategy (None branch)
# ---------------------------------------------------------------------------


def test_runtime_requirements_empty_when_no_strategy() -> None:
    """runtime_requirements is {} when package.execution_strategy is None."""
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
    )
    request = hrequest("node-1", strategy_ref=None)
    pkg = _build_package(env, request)
    assert pkg.execution_strategy is None
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.runtime_requirements == {}


def test_manifest_status_created_when_no_strategy() -> None:
    """Status is ManifestStatus.CREATED even when no strategy is attached."""
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
    )
    request = hrequest("node-1", strategy_ref=None)
    manifest = _build_manifest(env, request)
    assert manifest.status == ManifestStatus.CREATED


# ---------------------------------------------------------------------------
# correlation
# ---------------------------------------------------------------------------


def test_correlation_copied_from_package() -> None:
    """manifest.correlation equals package.correlation."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"), correlation="cor-explicit-77")
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.correlation == pkg.correlation


def test_correlation_identifier_value() -> None:
    """manifest.correlation.correlation_identifier matches the original identifier."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"), correlation="cor-explicit-abc")
    manifest = ExecutionManifestBuilder().build(pkg)
    assert manifest.correlation.correlation_identifier == "cor-explicit-abc"


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_is_created() -> None:
    """A successfully built manifest always has status ManifestStatus.CREATED."""
    env = standard_env()
    manifest = _build_manifest(env, hrequest("node-1"))
    assert manifest.status == ManifestStatus.CREATED


# ---------------------------------------------------------------------------
# Descriptive — no executable content
# ---------------------------------------------------------------------------


def test_manifest_has_no_work_package_embedded() -> None:
    """The manifest is purely descriptive — it carries no embedded WorkPackage."""
    env = standard_env()
    manifest = _build_manifest(env, hrequest("node-1"))
    assert not hasattr(manifest, "work_package")


def test_manifest_has_no_policy_bundle_embedded() -> None:
    """The manifest is purely descriptive — it carries no embedded PolicyBundle."""
    env = standard_env()
    manifest = _build_manifest(env, hrequest("node-1"))
    assert not hasattr(manifest, "policy_bundle")


def test_manifest_has_no_context_view_embedded() -> None:
    """The manifest is purely descriptive — it carries no embedded ContextView."""
    env = standard_env()
    manifest = _build_manifest(env, hrequest("node-1"))
    assert not hasattr(manifest, "context_view")


# ---------------------------------------------------------------------------
# Immutability (frozen)
# ---------------------------------------------------------------------------


def test_manifest_rejects_mutation_of_identity() -> None:
    """ExecutionManifest.identity is immutable — assignment raises ValueError."""
    env = standard_env()
    manifest = _build_manifest(env, hrequest("node-1"))
    with pytest.raises(ValueError):
        manifest.identity = "tampered"  # type: ignore[misc]


def test_manifest_rejects_mutation_of_status() -> None:
    """ExecutionManifest.status is immutable — assignment raises ValueError."""
    env = standard_env()
    manifest = _build_manifest(env, hrequest("node-1"))
    with pytest.raises(ValueError):
        manifest.status = None  # type: ignore[misc]


def test_manifest_rejects_mutation_of_required_skills() -> None:
    """ExecutionManifest.required_skills is immutable — assignment raises ValueError."""
    env = standard_env()
    manifest = _build_manifest(env, hrequest("node-1"))
    with pytest.raises(ValueError):
        manifest.required_skills = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_building_twice_yields_equal_manifests() -> None:
    """Building the manifest from the same package twice yields equal results."""
    env = standard_env()
    pkg = _build_package(env, hrequest("node-1"))
    m1 = ExecutionManifestBuilder().build(pkg)
    m2 = ExecutionManifestBuilder().build(pkg)
    assert m1 == m2


def test_determinism_with_strategy_runtime_policy() -> None:
    """Determinism holds when runtime_requirements is populated from the strategy."""
    strat = strategy("strat-det", runtime_policy={"timeout": 30})
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
        strategies=(strat,),
    )
    request = hrequest("node-1", strategy_ref="strat-det")
    pkg = _build_package(env, request)
    assert ExecutionManifestBuilder().build(pkg) == ExecutionManifestBuilder().build(pkg)


def test_determinism_with_no_strategy() -> None:
    """Determinism holds when execution_strategy is None."""
    env = harness_env(
        context_packages=(context_package(),),
        work_packages=(work_package("wp-1"),),
    )
    request = hrequest("node-1", strategy_ref=None)
    pkg = _build_package(env, request)
    assert ExecutionManifestBuilder().build(pkg) == ExecutionManifestBuilder().build(pkg)
