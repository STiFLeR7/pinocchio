"""Unit tests for nexus_harness.policy_resolver.

Covers PolicyResolver.resolve():
- Empty registry + no constraints + None strategy → empty bundle, no approval taxonomy.
- Enabled policies from registry are bundled.
- Explicit policy constraint merges in an additional policy.
- Duplicate (identity, version) pairs are deduped (union semantics).
- Bundle is sorted deterministically by (identity, version).
- ResolvedPolicy carries the correct fields: reference, identity, version, decision,
  category.
- approval_taxonomy comes from strategy.approval_policy.value; None when strategy=None.
- A "policy" constraint referencing a missing policy raises UnresolvedReferenceError.
- A non-"policy" constraint is silently ignored.
- A "policy" constraint with no identifier in detail is silently ignored.
- category is None when the Policy has no category.
- Resolve is deterministic: two calls with identical inputs return equal bundles.
- PolicyBundle and ResolvedPolicy are frozen (mutation rejected).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Constraint
from nexus_core.contracts.enums import ApprovalTaxonomy, PolicyCategory, PolicyDecision
from nexus_harness import InMemoryPolicyRegistry
from nexus_harness.policy_resolver import PolicyBundle, PolicyResolver
from nexus_harness.validators import UnresolvedReferenceError
from nexus_harness.vocabulary import POLICY_TARGET_TYPE
from tests.unit.nexus_harness.helpers import hrequest, policy, strategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolver(*policies_to_register) -> PolicyResolver:
    """Return a PolicyResolver whose registry holds the given policies."""
    reg = InMemoryPolicyRegistry()
    for pol in policies_to_register:
        reg.register(pol)
    return PolicyResolver(reg)


# ---------------------------------------------------------------------------
# Empty / baseline
# ---------------------------------------------------------------------------


def test_empty_registry_no_constraints_no_strategy_gives_empty_bundle() -> None:
    """Empty registry + no constraints + None strategy → empty bundle."""
    resolver = _resolver()
    bundle = resolver.resolve(hrequest("node-a"), None)

    assert isinstance(bundle, PolicyBundle)
    assert bundle.policies == ()
    assert bundle.approval_taxonomy is None


def test_empty_registry_no_constraints_with_strategy_gives_approval_taxonomy() -> None:
    """approval_taxonomy is taken from strategy.approval_policy.value."""
    resolver = _resolver()
    strat = strategy(approval_policy=ApprovalTaxonomy.HUMAN_REVIEW)
    bundle = resolver.resolve(hrequest("node-a"), strat)

    assert bundle.policies == ()
    assert bundle.approval_taxonomy == ApprovalTaxonomy.HUMAN_REVIEW.value


def test_approval_taxonomy_is_none_when_strategy_is_none() -> None:
    resolver = _resolver(policy("pol-x"))
    bundle = resolver.resolve(hrequest("node-a"), None)
    assert bundle.approval_taxonomy is None


def test_approval_taxonomy_automatic() -> None:
    resolver = _resolver()
    strat = strategy(approval_policy=ApprovalTaxonomy.AUTOMATIC)
    bundle = resolver.resolve(hrequest("node-a"), strat)
    assert bundle.approval_taxonomy == "automatic"


def test_approval_taxonomy_multi_stage() -> None:
    resolver = _resolver()
    strat = strategy(approval_policy=ApprovalTaxonomy.MULTI_STAGE)
    bundle = resolver.resolve(hrequest("node-a"), strat)
    assert bundle.approval_taxonomy == "multi_stage"


# ---------------------------------------------------------------------------
# Bundling from registry
# ---------------------------------------------------------------------------


def test_single_enabled_policy_appears_in_bundle() -> None:
    pol = policy("pol-a")
    resolver = _resolver(pol)
    bundle = resolver.resolve(hrequest("node-a"), None)

    assert len(bundle.policies) == 1
    rp = bundle.policies[0]
    assert rp.identity == "pol-a"
    assert rp.version == pol.version
    assert rp.decision == pol.decision.value
    assert rp.category == pol.category.value


def test_resolved_policy_reference_target_type() -> None:
    pol = policy("pol-a")
    resolver = _resolver(pol)
    bundle = resolver.resolve(hrequest("node-a"), None)

    rp = bundle.policies[0]
    assert rp.reference.target_type == POLICY_TARGET_TYPE
    assert rp.reference.identifier == "pol-a"


def test_multiple_enabled_policies_all_appear() -> None:
    pol_a = policy("pol-a")
    pol_b = policy("pol-b")
    pol_c = policy("pol-c")
    resolver = _resolver(pol_a, pol_b, pol_c)
    bundle = resolver.resolve(hrequest("node-a"), None)

    identities = [rp.identity for rp in bundle.policies]
    assert set(identities) == {"pol-a", "pol-b", "pol-c"}


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def test_bundle_is_sorted_by_identity_ascending() -> None:
    """Policies are sorted by (identity, version) regardless of registration order."""
    resolver = _resolver(policy("pol-c"), policy("pol-a"), policy("pol-b"))
    bundle = resolver.resolve(hrequest("node-a"), None)

    identities = [rp.identity for rp in bundle.policies]
    assert identities == sorted(identities)


def test_bundle_sort_is_deterministic_across_calls() -> None:
    resolver = _resolver(policy("pol-z"), policy("pol-a"), policy("pol-m"))
    req = hrequest("node-a")
    strat = strategy()

    bundle_1 = resolver.resolve(req, strat)
    bundle_2 = resolver.resolve(req, strat)

    assert bundle_1 == bundle_2


# ---------------------------------------------------------------------------
# Explicit policy constraints (union + dedup)
# ---------------------------------------------------------------------------


def test_constraint_references_registered_policy_adds_it_to_bundle() -> None:
    """A policy constraint whose target is in the registry merges into the bundle."""
    pol_b = policy("pol-b")
    reg = InMemoryPolicyRegistry()
    reg.register(pol_b)
    resolver = PolicyResolver(reg)

    req = hrequest(
        "node-a",
        constraints=(Constraint(kind="policy", detail={"policy": "pol-b", "version": "1"}),),
    )
    bundle = resolver.resolve(req, None)

    identities = [rp.identity for rp in bundle.policies]
    assert "pol-b" in identities


def test_constraint_brings_in_policy_not_in_enabled_set() -> None:
    """A constraint can reference an additional policy not already enabled."""
    pol_a = policy("pol-a")
    pol_extra = policy("pol-extra")

    reg = InMemoryPolicyRegistry()
    reg.register(pol_a)
    reg.register(pol_extra)
    resolver = PolicyResolver(reg)

    req = hrequest(
        "node-a",
        constraints=(Constraint(kind="policy", detail={"policy": "pol-extra", "version": "1"}),),
    )
    bundle = resolver.resolve(req, None)

    identities = {rp.identity for rp in bundle.policies}
    assert "pol-a" in identities
    assert "pol-extra" in identities


def test_constraint_using_identity_key_resolves_policy() -> None:
    """detail={"identity": ..., "version": ...} is also accepted."""
    pol = policy("pol-id-key")
    reg = InMemoryPolicyRegistry()
    reg.register(pol)
    resolver = PolicyResolver(reg)

    req = hrequest(
        "node-a",
        constraints=(Constraint(kind="policy", detail={"identity": "pol-id-key", "version": "1"}),),
    )
    bundle = resolver.resolve(req, None)

    assert any(rp.identity == "pol-id-key" for rp in bundle.policies)


def test_same_policy_referenced_by_registry_and_constraint_is_deduped() -> None:
    """If the registry already contains a policy that a constraint also names, it appears once."""
    pol = policy("pol-dup")
    reg = InMemoryPolicyRegistry()
    reg.register(pol)
    resolver = PolicyResolver(reg)

    req = hrequest(
        "node-a",
        constraints=(Constraint(kind="policy", detail={"policy": "pol-dup", "version": "1"}),),
    )
    bundle = resolver.resolve(req, None)

    identities = [rp.identity for rp in bundle.policies]
    assert identities.count("pol-dup") == 1


# ---------------------------------------------------------------------------
# Constraint edge cases (ignored / skipped)
# ---------------------------------------------------------------------------


def test_non_policy_constraint_is_ignored() -> None:
    """A constraint whose kind is not 'policy' does not trigger policy resolution."""
    resolver = _resolver()
    req = hrequest(
        "node-a",
        constraints=(Constraint(kind="time_limit", detail={"hours": 2}),),
    )
    bundle = resolver.resolve(req, None)
    assert bundle.policies == ()


def test_policy_constraint_with_no_identifier_is_ignored() -> None:
    """A 'policy' constraint missing both 'policy' and 'identity' keys is skipped."""
    resolver = _resolver()
    req = hrequest(
        "node-a",
        constraints=(Constraint(kind="policy", detail={"version": "1"}),),
    )
    bundle = resolver.resolve(req, None)
    assert bundle.policies == ()


def test_mixed_constraints_only_policy_kind_resolved() -> None:
    """Non-policy constraints are skipped; only policy-kind ones are processed."""
    pol = policy("pol-a")
    reg = InMemoryPolicyRegistry()
    reg.register(pol)
    resolver = PolicyResolver(reg)

    req = hrequest(
        "node-a",
        constraints=(
            Constraint(kind="time_limit", detail={"hours": 1}),
            Constraint(kind="policy", detail={"policy": "pol-a", "version": "1"}),
            Constraint(kind="budget", detail={"usd": 50}),
        ),
    )
    bundle = resolver.resolve(req, None)

    assert len(bundle.policies) == 1
    assert bundle.policies[0].identity == "pol-a"


# ---------------------------------------------------------------------------
# Missing-policy fail-closed
# ---------------------------------------------------------------------------


def test_missing_policy_constraint_raises_unresolved_reference_error() -> None:
    """A constraint referencing a policy absent from the registry is a hard error."""
    resolver = _resolver()  # empty registry
    req = hrequest(
        "node-a",
        constraints=(
            Constraint(kind="policy", detail={"policy": "does-not-exist", "version": "1"}),
        ),
    )
    with pytest.raises(UnresolvedReferenceError):
        resolver.resolve(req, None)


def test_unresolved_error_message_contains_policy_identity() -> None:
    resolver = _resolver()
    req = hrequest(
        "node-a",
        constraints=(Constraint(kind="policy", detail={"policy": "missing-pol", "version": "1"}),),
    )
    with pytest.raises(UnresolvedReferenceError, match="missing-pol"):
        resolver.resolve(req, None)


# ---------------------------------------------------------------------------
# ResolvedPolicy field values
# ---------------------------------------------------------------------------


def test_resolved_policy_decision_is_string() -> None:
    pol = policy("pol-a", decision=PolicyDecision.DENY)
    resolver = _resolver(pol)
    bundle = resolver.resolve(hrequest("node-a"), None)

    rp = bundle.policies[0]
    assert rp.decision == "deny"
    assert isinstance(rp.decision, str)


def test_resolved_policy_category_is_string_when_set() -> None:
    pol = policy("pol-a", category=PolicyCategory.EXECUTION)
    resolver = _resolver(pol)
    bundle = resolver.resolve(hrequest("node-a"), None)

    rp = bundle.policies[0]
    assert rp.category == "execution"
    assert isinstance(rp.category, str)


def test_resolved_policy_category_is_none_when_policy_has_no_category() -> None:
    pol = policy("pol-a", category=None)
    resolver = _resolver(pol)
    bundle = resolver.resolve(hrequest("node-a"), None)

    rp = bundle.policies[0]
    assert rp.category is None


def test_resolved_policy_version_matches_source() -> None:
    pol = policy("pol-v", version="42")
    resolver = _resolver(pol)
    bundle = resolver.resolve(hrequest("node-a"), None)

    assert bundle.policies[0].version == "42"


# ---------------------------------------------------------------------------
# Frozen value objects
# ---------------------------------------------------------------------------


def test_policy_bundle_is_frozen() -> None:
    resolver = _resolver(policy("pol-a"))
    bundle = resolver.resolve(hrequest("node-a"), None)

    with pytest.raises(ValidationError):
        bundle.approval_taxonomy = "mutated"  # type: ignore[misc]


def test_resolved_policy_is_frozen() -> None:
    resolver = _resolver(policy("pol-a"))
    bundle = resolver.resolve(hrequest("node-a"), None)
    rp = bundle.policies[0]

    with pytest.raises(ValidationError):
        rp.identity = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Never computes a decision
# ---------------------------------------------------------------------------


def test_resolver_does_not_alter_policy_decision() -> None:
    """The resolver gathers only; it never sets, overrides, or computes a decision."""
    pol = policy("pol-a", decision=PolicyDecision.REQUIRE_APPROVAL)
    resolver = _resolver(pol)
    bundle = resolver.resolve(hrequest("node-a"), strategy())

    assert bundle.policies[0].decision == PolicyDecision.REQUIRE_APPROVAL.value
