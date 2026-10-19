"""Constitutional guardrails for Repository Intelligence (proven on source, not prose).

Proves: Repository Intelligence imports no planning/engineering/orchestration/runtime/execution/
validation/recovery/reflection/policy (and never EI/Planning); Engineering Intelligence and Planning
never scan repositories themselves; and only Repository Intelligence owns repository understanding.
"""

from __future__ import annotations

import ast
from pathlib import Path

import nexus_repository

_REPO_ROOT = Path(__file__).resolve().parents[3]

_FORBIDDEN = (
    "nexus_planning",
    "nexus_engineering",
    "nexus_orchestration",
    "nexus_runtime",
    "nexus_execution",
    "nexus_validation",
    "nexus_recovery",
    "nexus_reflection",
    "nexus_policy",
    "nexus_intent",
    "nexus_estimation",
    "nexus_workflows",
)


def _sources(package: str):
    directory = _REPO_ROOT / package
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


def test_repository_imports_no_decision_engine() -> None:
    for path in _sources("nexus_repository"):
        for module in _imported_modules(path):
            assert not module.startswith(_FORBIDDEN), f"{path.name} imports {module}"


def test_repository_never_reasons_or_estimates() -> None:
    # facts only — no LLM, no random, no policy/estimation/engineering vocabulary constructed.
    for path in _sources("nexus_repository"):
        text = path.read_text(encoding="utf-8")
        for module in _imported_modules(path):
            assert module.split(".")[0] not in ("random", "openai", "anthropic"), (
                f"{path.name}:{module}"
            )
        for banned in ("EngineeringStrategy", "PolicyDecision", "EstimationReport"):
            assert banned not in text, f"{path.name} references {banned}"


def test_engineering_intelligence_never_scans_repositories() -> None:
    for path in _sources("nexus_engineering"):
        for module in _imported_modules(path):
            assert not module.startswith("nexus_repository"), f"{path.name} imports {module}"
        text = path.read_text(encoding="utf-8")
        assert "scan_tree" not in text and "os.walk" not in text, f"{path.name} scans a repository"


def test_planning_never_scans_repositories() -> None:
    for path in _sources("nexus_planning"):
        for module in _imported_modules(path):
            assert not module.startswith("nexus_repository"), f"{path.name} imports {module}"
        text = path.read_text(encoding="utf-8")
        assert "scan_tree" not in text and "os.walk" not in text, f"{path.name} scans a repository"


def test_only_repository_owns_repository_understanding() -> None:
    # No other package constructs a RepositoryProfile.
    for package in (
        "nexus_engineering",
        "nexus_intent",
        "nexus_planning",
        "nexus_estimation",
        "nexus_policy",
    ):
        for path in _sources(package):
            assert "RepositoryProfile(" not in path.read_text(encoding="utf-8"), (
                f"{package}/{path.name}"
            )


def test_repository_public_surface() -> None:
    for name in ("RepositoryIntelligence", "RepositoryProfile", "build_repository", "scan_tree"):
        assert hasattr(nexus_repository, name)
