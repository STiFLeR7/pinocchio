"""Verdict-parity regression vs. Nexus v1 governance defaults (WP-P2.1 acceptance).

v1 (`nexus/execution/governance.py` + `core/policy_defaults.py`) denies execution when
the runtime is not approved, the runtime policy is not ``approved``, or the command
contains a blacklisted pattern, and otherwise allows. The v2 seed policy set (ADR-004 §9)
must reproduce that verdict for the same inputs.
"""

from __future__ import annotations

import pytest

from nexus_core.contracts.enums import PolicyDecision
from nexus_policy import (
    ALLOWED_RUNTIMES,
    GLOBAL_COMMAND_BLACKLIST,
    REQUIRED_RUNTIME_POLICY,
    DecisionRequest,
    InMemoryPolicyRegistry,
    PolicyEngine,
    v1_seed_policies,
)


def _v1_verdict(runtime: str, command: str, runtime_policy: str) -> PolicyDecision:
    """The decision v1's validate_execution would reach (allow = passes; deny = raises)."""
    if runtime.lower() not in {r.lower() for r in ALLOWED_RUNTIMES}:
        return PolicyDecision.DENY
    if runtime_policy != REQUIRED_RUNTIME_POLICY:
        return PolicyDecision.DENY
    if any(pattern in command for pattern in GLOBAL_COMMAND_BLACKLIST):
        return PolicyDecision.DENY
    return PolicyDecision.ALLOW


def _engine() -> PolicyEngine:
    reg = InMemoryPolicyRegistry(now=lambda: "t")
    for policy in v1_seed_policies():
        reg.register(policy)
    return PolicyEngine(reg, now=lambda: "t")


@pytest.mark.parametrize(
    ("runtime", "command", "runtime_policy"),
    [
        ("claude", "pytest -q", "approved"),
        ("gemini", "ls -la", "approved"),
        ("nexus", "echo hi", "approved"),
        ("evil-runtime", "ls", "approved"),
        ("claude", "sudo rm file", "approved"),
        ("claude", "rm -rf /", "approved"),
        ("claude", "mv /etc/passwd .", "approved"),
        ("claude", ":(){ :|:& };:", "approved"),
        ("claude", "ls", "pending"),
        ("evil", "sudo x", "pending"),
    ],
)
def test_v2_matches_v1_verdict(runtime, command, runtime_policy) -> None:
    request = DecisionRequest(
        action_class="execution",
        correlation_identifier="cor",
        attributes={"runtime": runtime, "command": command, "runtime_policy": runtime_policy},
    )
    v2 = _engine().evaluate(request).decision
    assert v2 is _v1_verdict(runtime, command, runtime_policy)
