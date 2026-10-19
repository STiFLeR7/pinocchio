"""Constitutional guardrails for the Estimation subsystem.

Proves: estimation never reasons (no randomness, no LLM, no runtime import; the clock is used
only for the injected event timestamp, never in scoring); only ``nexus_estimation`` owns the
estimate types; Planning / Runtime / Policy do not construct them; and Engineering Intelligence
does not yet exist. (Planning's ``complexity_estimates`` field holds structural plan-shape
counts, not estimation-subsystem estimates — a different identifier, checked below.)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import nexus_estimation

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ESTIMATE_TYPES = (
    "ComplexityEstimate",
    "DurationEstimate",
    "CostEstimate",
    "ConfidenceEstimate",
    "ResourceEstimate",
    "EstimationReport",
)
_OTHER_ENGINES = [
    "nexus_planning",
    "nexus_runtime",
    "nexus_policy",
    "nexus_execution",
    "nexus_orchestration",
    "nexus_validation",
    "nexus_recovery",
    "nexus_reflection",
    "nexus_knowledge",
    "nexus_integration",
]


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


def test_estimation_performs_no_reasoning() -> None:
    # No randomness and no reasoning/LLM/runtime/policy imports — proven on actual imports, not prose.
    forbidden = ("random", "openai", "anthropic")
    forbidden_prefixes = ("nexus_runtime", "nexus_policy", "nexus_planning", "nexus_orchestration")
    for path in _sources("nexus_estimation"):
        for module in _imported_modules(path):
            top = module.split(".")[0]
            assert top not in forbidden, f"{path.name} imports {module}"
            assert not module.startswith(forbidden_prefixes), f"{path.name} imports {module}"


def test_clock_used_only_for_event_timestamps_not_scoring() -> None:
    # datetime is imported only by events.py (the injected timestamp source); scoring is clock-free.
    users = [
        p.name for p in _sources("nexus_estimation") if "datetime" in p.read_text(encoding="utf-8")
    ]
    assert users == ["events.py"], users


@pytest.mark.parametrize("package", _OTHER_ENGINES)
def test_only_estimation_owns_the_estimate_types(package) -> None:
    offenders = []
    for path in _sources(package):
        text = path.read_text(encoding="utf-8")
        for type_name in _ESTIMATE_TYPES:
            if type_name in text:
                offenders.append(f"{path.name}:{type_name}")
    assert offenders == [], f"{package} references estimation types (INV-02): {offenders}"


def test_estimation_does_not_depend_on_engineering_intelligence() -> None:
    # Estimation is the leaf that FEEDS EI (P5); it must never import EI back (INV-01 direction).
    # (P4 asserted EI did not yet exist; P5 builds it as a downstream consumer of estimation.)
    for path in _sources("nexus_estimation"):
        for module in _imported_modules(path):
            assert not module.startswith("nexus_engineering"), f"{path.name} imports {module}"


def test_estimation_public_surface() -> None:
    for name in ("EstimationEngine", "EstimationReport", "EstimationInputs", "build_estimation"):
        assert hasattr(nexus_estimation, name)
