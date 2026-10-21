"""Constitutional guardrails for Execution History (proven on source, not prose).

Proves: Execution History imports no decision/execution engine and no other subsystem (grounding
leaf — core + infra only); it never reasons, estimates, or emits any non-``execution_history.*``
event; Repository Intelligence performs no historical reconstruction and Engineering Intelligence
performs no historical lookup itself; and only Execution History owns historical facts.
"""

from __future__ import annotations

import ast
from pathlib import Path

import nexus_history

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Execution History depends on the foundation only (core + infra) and its own package.
_ALLOWED_NEXUS = ("nexus_core", "nexus_infra", "nexus_history")


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


def test_history_is_a_grounding_leaf() -> None:
    # imports no planning/engineering/runtime/orchestration/execution/validation/recovery/reflection
    # (nor any other nexus_* subsystem) — only core + infra.
    for path in _sources("nexus_history"):
        for module in _imported_modules(path):
            if module.startswith("nexus_") and not module.startswith(_ALLOWED_NEXUS):
                raise AssertionError(f"{path.name} imports {module}")


def test_history_never_reasons_or_decides() -> None:
    # facts only — no LLM/random, no engineering/policy/estimation vocabulary constructed.
    for path in _sources("nexus_history"):
        text = path.read_text(encoding="utf-8")
        for module in _imported_modules(path):
            assert module.split(".")[0] not in ("random", "openai", "anthropic"), (
                f"{path.name}:{module}"
            )
        for banned in ("EngineeringStrategy", "PolicyDecision", "EstimationReport", "RecoveryPlan"):
            assert banned not in text, f"{path.name} references {banned}"


def test_history_emits_only_execution_history_events() -> None:
    # the only event type constants it defines are execution_history.*
    text = (_REPO_ROOT / "nexus_history" / "events.py").read_text(encoding="utf-8")
    for family in ("runtime.", "validation.", "recovery.", "reflection.", "knowledge."):
        assert f'"{family}' not in text, f"events.py defines a {family} event"


def test_repository_performs_no_historical_reconstruction() -> None:
    for path in _sources("nexus_repository"):
        for module in _imported_modules(path):
            assert not module.startswith("nexus_history"), f"{path.name} imports {module}"
        text = path.read_text(encoding="utf-8")
        assert "read_all" not in text and "read_stream" not in text, f"{path.name} reads the log"


def test_engineering_performs_no_historical_lookup() -> None:
    for path in _sources("nexus_engineering"):
        for module in _imported_modules(path):
            assert not module.startswith("nexus_history"), f"{path.name} imports {module}"
        text = path.read_text(encoding="utf-8")
        assert "read_all" not in text and "read_stream" not in text, f"{path.name} reads the log"


def test_only_history_owns_historical_facts() -> None:
    # No other package constructs an ExecutionHistoryProfile or emits execution_history.* events.
    for package in (
        "nexus_engineering",
        "nexus_repository",
        "nexus_intent",
        "nexus_planning",
        "nexus_estimation",
        "nexus_policy",
    ):
        for path in _sources(package):
            text = path.read_text(encoding="utf-8")
            assert "ExecutionHistoryProfile(" not in text, f"{package}/{path.name}"
            assert "execution_history.projected" not in text, f"{package}/{path.name}"


def test_history_public_surface() -> None:
    for name in ("ExecutionHistory", "ExecutionHistoryProfile", "HistoryQuery", "build_history"):
        assert hasattr(nexus_history, name)
