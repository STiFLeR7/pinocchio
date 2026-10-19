"""Step 4 — Policy Resolver (resolve applicable policies; never evaluate them).

Produces a deterministic *policy bundle* for one Harness Request: the platform's
enabled governance policies (from the Policy Registry) unioned with any policy a
request constraint references explicitly, plus the declared approval taxonomy carried
on the governing Execution Strategy. It only *gathers* the rules a runtime/Policy
Engine will later evaluate — it computes no decision and produces no outcome
(ADR-004: declaration ≠ evaluation; recovery strategies are never Policy Decisions).
An explicitly referenced policy that does not resolve is a fail-closed error
(INV-30).
"""

from __future__ import annotations

from nexus_core.contracts.base import Constraint, Reference, ValueObject
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.policy import Policy
from nexus_core.registries.interfaces import PolicyRegistry
from nexus_harness.validators import UnresolvedReferenceError
from nexus_harness.vocabulary import POLICY_TARGET_TYPE
from nexus_orchestration.harness_requests import HarnessRequest

_POLICY_CONSTRAINT_KIND = "policy"


class ResolvedPolicy(ValueObject):
    """One resolved Policy in the bundle — its reference plus declarative metadata."""

    reference: Reference
    identity: str
    version: str
    decision: str
    category: str | None = None


class PolicyBundle(ValueObject):
    """The deterministic set of applicable policies, plus the declared approval taxonomy."""

    policies: tuple[ResolvedPolicy, ...] = ()
    approval_taxonomy: str | None = None


class PolicyResolver:
    """Gathers applicable policies into a bundle; never evaluates a decision."""

    def __init__(self, registry: PolicyRegistry) -> None:
        self._registry = registry

    def resolve(self, request: HarnessRequest, strategy: ExecutionStrategy | None) -> PolicyBundle:
        """Bundle enabled + explicitly-referenced policies; carry the approval taxonomy."""
        resolved: dict[tuple[str, str], Policy] = {
            (policy.identity, policy.version): policy for policy in self._registry.enabled()
        }
        for identifier, version in self._referenced(request.constraints):
            resolved[identifier, version] = self._require(request, identifier, version)
        policies = tuple(
            self._describe(policy) for _, policy in sorted(resolved.items(), key=lambda kv: kv[0])
        )
        approval = strategy.approval_policy.value if strategy is not None else None
        return PolicyBundle(policies=policies, approval_taxonomy=approval)

    def _referenced(self, constraints: tuple[Constraint, ...]) -> tuple[tuple[str, str], ...]:
        out: list[tuple[str, str]] = []
        for constraint in constraints:
            if constraint.kind != _POLICY_CONSTRAINT_KIND:
                continue
            identifier = constraint.detail.get("policy") or constraint.detail.get("identity")
            if identifier is None:
                continue
            version = constraint.detail.get("version")
            out.append((str(identifier), str(version) if version is not None else ""))
        return tuple(out)

    def _require(self, request: HarnessRequest, identifier: str, version: str) -> Policy:
        policy = self._registry.get(identifier, version or None)
        if policy is None:
            raise UnresolvedReferenceError(
                f"policy {identifier!r} for harness request {request.identity!r} is not resolvable"
            )
        return policy

    def _describe(self, policy: Policy) -> ResolvedPolicy:
        return ResolvedPolicy(
            reference=Reference(target_type=POLICY_TARGET_TYPE, identifier=policy.identity),
            identity=policy.identity,
            version=policy.version,
            decision=policy.decision.value,
            category=policy.category.value if policy.category is not None else None,
        )
