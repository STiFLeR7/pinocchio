"""Migration fixtures — sample legacy/constitutional decisions for two determinism classes.

These live in the tests (not the substrate — the substrate has no business logic). They
exercise the ADR-008 §9 entry gate on one deterministic owner (Policy: v2 engine verdict vs
a v1-style verdict, exact-match) and one probabilistic owner (intent classification, an
equivalence band). The Policy fixture reuses the real ``nexus_policy`` engine as the shadow —
proving the shadow computes an actual constitutional decision, side-effect-free.
"""

from __future__ import annotations

from collections.abc import Callable

from nexus_policy import (
    ALLOWED_RUNTIMES,
    GLOBAL_COMMAND_BLACKLIST,
    REQUIRED_RUNTIME_POLICY,
    DecisionRequest,
    InMemoryPolicyRegistry,
    PolicyEngine,
    v1_seed_policies,
)

POLICY_OWNER = "policy_engine"
INTENT_OWNER = "intent_resolution"


def v1_policy_verdict(runtime: str, command: str, runtime_policy: str) -> str:
    """A v1-style governance verdict (the legacy decision) as a plain string."""
    if runtime.lower() not in {r.lower() for r in ALLOWED_RUNTIMES}:
        return "deny"
    if runtime_policy != REQUIRED_RUNTIME_POLICY:
        return "deny"
    if any(pattern in command for pattern in GLOBAL_COMMAND_BLACKLIST):
        return "deny"
    return "allow"


def constitutional_policy_engine() -> PolicyEngine:
    """A real, side-effect-free ``nexus_policy`` engine (no emitter) for the shadow."""
    registry = InMemoryPolicyRegistry(now=lambda: "t")
    for policy in v1_seed_policies():
        registry.register(policy)
    return PolicyEngine(registry, now=lambda: "t")  # no emitter → pure decision


def policy_decision_pair(
    engine: PolicyEngine, *, runtime: str, command: str, runtime_policy: str
) -> tuple[Callable[[], str], Callable[[], str]]:
    """(legacy, shadow) decision callables for the Policy owner over identical recorded inputs."""

    def legacy() -> str:
        return v1_policy_verdict(runtime, command, runtime_policy)

    def shadow() -> str:
        request = DecisionRequest(
            action_class="execution",
            correlation_identifier="shadow",
            attributes={"runtime": runtime, "command": command, "runtime_policy": runtime_policy},
        )
        return engine.evaluate(request).decision.value

    return legacy, shadow


def intent_equivalence(legacy: str, shadow: str) -> bool:
    """A tolerant equivalence band for the (probabilistic) intent-type decision."""
    normalize = {"code": "software", "coding": "software", "dev": "software"}
    a = normalize.get(legacy.lower().strip(), legacy.lower().strip())
    b = normalize.get(shadow.lower().strip(), shadow.lower().strip())
    return a == b
