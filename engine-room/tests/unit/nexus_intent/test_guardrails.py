"""Constitutional guardrails for Intent Resolution (proven on source, not prose).

Proves: Intent Resolution understands but **never decides how** — it imports no estimation,
engineering, policy, planning, orchestration, execution, validation, recovery, reflection, or
runtime engine, and no randomness/LLM; the clock is used only for the injected event timestamp; and
it introduces no competing schema for intent (it uses the frozen ``nexus_core.domain.Intent``).
"""

from __future__ import annotations

import ast
from pathlib import Path

import nexus_intent

_REPO_ROOT = Path(__file__).resolve().parents[3]

# "never decides how": Intent Resolution imports none of these downstream/decision engines.
_FORBIDDEN = (
    "nexus_estimation",
    "nexus_engineering",
    "nexus_policy",
    "nexus_planning",
    "nexus_orchestration",
    "nexus_execution",
    "nexus_validation",
    "nexus_recovery",
    "nexus_reflection",
    "nexus_knowledge",
    "nexus_runtime",
    "nexus_harness",
)
_FORBIDDEN_TOP = ("random", "openai", "anthropic")


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


def test_intent_understands_but_never_decides_how() -> None:
    for path in _sources("nexus_intent"):
        for module in _imported_modules(path):
            top = module.split(".")[0]
            assert top not in _FORBIDDEN_TOP, f"{path.name} imports {module}"
            assert not module.startswith(_FORBIDDEN), (
                f"{path.name} imports decision engine {module}"
            )


def test_intent_performs_no_planning() -> None:
    for path in _sources("nexus_intent"):
        text = path.read_text(encoding="utf-8")
        for banned in ("PlanningRequest", "WorkPackage", "ExecutionGraph", "PlanBuilder"):
            assert banned not in text, f"{path.name} references planning type {banned}"


def test_clock_used_only_for_event_timestamps() -> None:
    users = [
        p.name for p in _sources("nexus_intent") if "datetime" in p.read_text(encoding="utf-8")
    ]
    assert users == ["events.py"], users


def test_intent_uses_the_frozen_intent_schema() -> None:
    # INV-07: no competing representation — the canonical Intent is imported, not redefined.
    model_src = (_REPO_ROOT / "nexus_intent" / "model.py").read_text(encoding="utf-8")
    assert "from nexus_core.domain.intent import Intent" in model_src


def test_intent_public_surface() -> None:
    for name in (
        "IntentResolution",
        "IntentAnalysis",
        "IntentRequest",
        "ClarificationRequest",
        "build_intent",
    ):
        assert hasattr(nexus_intent, name)
