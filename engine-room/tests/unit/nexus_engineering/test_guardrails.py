"""Constitutional guardrails for Engineering Intelligence (proven on source, not prose).

Proves: EI **reasons but never executes** (imports no downstream engine); it never reasons via
randomness/LLM; it never *evaluates* policy (no ``PolicyDecision``) and never *estimates*
quantitatively (imports none of Estimation's scoring); only ``nexus_engineering`` owns engineering
reasoning (Planning/Runtime/Policy/Estimation/… neither import it nor construct its Strategy); and
the clock is used only for the injected event timestamp, never in the reasoning.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import nexus_engineering

_REPO_ROOT = Path(__file__).resolve().parents[3]

# EI is upstream of every execution engine; it must import none of them (INV-01, "never executes").
_DOWNSTREAM = (
    "nexus_planning",
    "nexus_orchestration",
    "nexus_execution",
    "nexus_validation",
    "nexus_recovery",
    "nexus_reflection",
    "nexus_knowledge",
    "nexus_context",
    "nexus_runtime",
    "nexus_harness",
    "nexus_operator",
    "nexus_briefings",
    "nexus_research",
    "nexus_workflows",
    "nexus_integration",
)
# Estimation's scoring internals — EI consumes the report, it never re-estimates.
_ESTIMATION_SCORING = (
    "nexus_estimation.rules",
    "nexus_estimation.confidence",
    "nexus_estimation.baseline",
)
# Policy's evaluation internals — EI queries the engine, it never evaluates.
_POLICY_INTERNALS = (
    "nexus_policy.conditions",
    "nexus_policy.precedence",
    "nexus_policy.registry",
    "nexus_policy.engine",
)

# Packages that must NOT perform engineering reasoning (own it or construct the Strategy).
# NB: nexus_planning is a *sanctioned consumer* of the EngineeringStrategy from P6 ("Plan may depend
# on the Engineering Strategy"); its consume-but-never-reason boundary is proven separately in
# tests/unit/nexus_planning/test_p6_ownership.py.
_OTHER_ENGINES = [
    "nexus_runtime",
    "nexus_policy",
    "nexus_estimation",
    "nexus_orchestration",
    "nexus_execution",
    "nexus_validation",
    "nexus_recovery",
    "nexus_reflection",
    "nexus_knowledge",
]
_EI_TYPES = ("EngineeringStrategy", "EngineeringIntelligence")


def _sources(package: str):
    directory = _REPO_ROOT / package
    if not directory.is_dir():
        return []
    return [p for p in directory.rglob("*.py") if "__pycache__" not in p.parts]


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_ei_reasons_but_never_executes() -> None:
    forbidden_top = ("random", "openai", "anthropic")
    for path in _sources("nexus_engineering"):
        for module in _imported_modules(path):
            top = module.split(".")[0]
            assert top not in forbidden_top, f"{path.name} imports {module}"
            assert not module.startswith(_DOWNSTREAM), (
                f"{path.name} imports downstream engine {module}"
            )


def test_ei_never_estimates_quantitatively() -> None:
    # EI consumes the EstimationReport; it imports none of Estimation's scoring modules.
    for path in _sources("nexus_engineering"):
        for module in _imported_modules(path):
            assert module not in _ESTIMATION_SCORING, (
                f"{path.name} imports estimation scoring {module}"
            )


def test_ei_never_evaluates_policy() -> None:
    for path in _sources("nexus_engineering"):
        text = path.read_text(encoding="utf-8")
        assert "PolicyDecision" not in text, (
            f"{path.name} references PolicyDecision — only nexus_policy may"
        )
        for module in _imported_modules(path):
            assert module not in _POLICY_INTERNALS, (
                f"{path.name} imports policy evaluation internal {module}"
            )


def test_clock_used_only_for_event_timestamps_not_reasoning() -> None:
    users = [
        p.name for p in _sources("nexus_engineering") if "datetime" in p.read_text(encoding="utf-8")
    ]
    assert users == ["events.py"], users


@pytest.mark.parametrize("package", _OTHER_ENGINES)
def test_only_engineering_intelligence_owns_engineering_reasoning(package) -> None:
    offenders = []
    for path in _sources(package):
        for module in _imported_modules(path):
            if module.startswith("nexus_engineering"):
                offenders.append(f"{path.name} imports {module}")
        text = path.read_text(encoding="utf-8")
        for type_name in _EI_TYPES:
            if type_name in text:
                offenders.append(f"{path.name}:{type_name}")
    assert offenders == [], f"{package} performs engineering reasoning (INV-02): {offenders}"


def test_engineering_public_surface() -> None:
    for name in (
        "EngineeringIntelligence",
        "EngineeringStrategy",
        "ReasoningInputs",
        "build_engineering",
    ):
        assert hasattr(nexus_engineering, name)
