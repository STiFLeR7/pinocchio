"""Constitutional guardrails — the Policy Engine is the *only* evaluator (INV-28/29).

WP-P2.1 acceptance: "no other package emits a policy verdict." These tests statically
prove that no consuming engine (Planning, Runtime, Recovery, Human Interaction / Operator,
Actuation / Execution, Orchestration, Validation, Knowledge, …) references the closed
``PolicyDecision`` verdict set or evaluates policy — only ``nexus_policy`` does. Governance
authority (INV-29) lives outside the engine: the engine returns a decision object and
performs no action.

If a later phase legitimately wires a consumer to *query* the engine, that consumer imports
``nexus_policy`` and passes a ``DecisionRequest`` — it still must not construct a
``PolicyDecision`` itself. This guardrail flags exactly that violation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import nexus_policy

# Engine/consumer packages that must never evaluate policy themselves.
_CONSUMER_PACKAGES = [
    "nexus_planning",
    "nexus_runtime",
    "nexus_runtime_adapters",
    "nexus_runtime_claude",
    "nexus_runtime_gemini",
    "nexus_runtime_shell",
    "nexus_recovery",
    "nexus_operator",
    "nexus_execution",
    "nexus_orchestration",
    "nexus_validation",
    "nexus_knowledge",
    "nexus_reflection",
    "nexus_engineering",
    "nexus_context",
    "nexus_harness",
    "nexus_briefings",
    "nexus_research",
    "nexus_workflows",
    "nexus_approval",
    "nexus_operations",
    "nexus_scheduler",
]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _package_python_files(package: str):
    directory = _REPO_ROOT / package
    if not directory.is_dir():
        return []
    return [p for p in directory.rglob("*.py") if "__pycache__" not in p.parts]


@pytest.mark.parametrize("package", _CONSUMER_PACKAGES)
def test_no_consumer_emits_a_policy_verdict(package) -> None:
    offenders = []
    for path in _package_python_files(package):
        text = path.read_text(encoding="utf-8")
        if "PolicyDecision" in text:
            offenders.append(str(path.relative_to(_REPO_ROOT)))
    assert offenders == [], (
        f"{package} references PolicyDecision — only nexus_policy may (INV-28): {offenders}"
    )


def test_policy_engine_is_the_only_package_returning_a_decision() -> None:
    # Sanity: the engine itself DOES use PolicyDecision (it is the evaluator).
    engine_src = (_REPO_ROOT / "nexus_policy" / "engine.py").read_text(encoding="utf-8")
    assert "PolicyDecision" in engine_src


def test_engine_performs_no_action_only_returns_a_value(tmp_path) -> None:
    # INV-29: evaluate() returns a value and (optionally) emits one fact; it runs no
    # approval workflow and mutates nothing else. With no emitter, the ONLY output is the
    # returned object — zero external effect.
    from nexus_policy import DecisionRequest, InMemoryPolicyRegistry, PolicyEngine, v1_seed_policies

    reg = InMemoryPolicyRegistry(now=lambda: "t")
    for policy in v1_seed_policies():
        reg.register(policy)
    engine = PolicyEngine(reg, now=lambda: "t")  # no emitter, no repo
    result = engine.evaluate(
        DecisionRequest(
            action_class="execution",
            correlation_identifier="cor",
            attributes={"runtime": "claude", "command": "ls", "runtime_policy": "approved"},
        )
    )
    assert result.allowed is True
    assert type(result).__name__ == "PolicyEvaluation"  # a pure value object


def test_nexus_policy_public_surface() -> None:
    # The evaluator, registry, request/result model, and composition are the public API.
    for name in (
        "PolicyEngine",
        "InMemoryPolicyRegistry",
        "DecisionRequest",
        "PolicyEvaluation",
        "build_policy",
    ):
        assert hasattr(nexus_policy, name)
