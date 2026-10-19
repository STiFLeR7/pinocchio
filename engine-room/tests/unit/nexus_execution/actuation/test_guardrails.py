"""Architecture guardrails — Actuation owns traversal, imports no reasoning/provider, adds no schema.

Execution Actuation consumes the frozen Plan bundle by value and drives Orchestration + Runtime +
Execution; it imports no reasoning/estimation/context/knowledge/policy engine, no Planning/Harness
producer, and no runtime provider (INV-01; INV-03/05; Runtime independence). It introduces no second
Plan/Execution-State domain schema (INV-07) — its output is a ``ValueObject`` projection of the log.
"""

from __future__ import annotations

import ast
import pathlib

import nexus_execution.actuation as actuation
from nexus_execution.actuation import model

_PACKAGE_DIR = pathlib.Path(actuation.__file__).parent

# Actuation drives Orchestration + Runtime + the Execution engine; it must import none of these:
_FORBIDDEN_PREFIXES = (
    "nexus_engineering",
    "nexus_estimation",
    "nexus_context",
    "nexus_repository",
    "nexus_knowledge",
    "nexus_intent",
    "nexus_history",
    "nexus_policy",
    "nexus_reflection",
    "nexus_validation",
    "nexus_recovery",
    "nexus_planning",  # consumes the frozen Plan bundle (nexus_core.domain), never the planner
    "nexus_harness",
    "nexus_workflows",
    "nexus_runtime_claude",  # the runtime adapter is injected — no provider is imported
    "nexus_runtime_gemini",
    "nexus_runtime_shell",
)

_REQUIRED_EVENTS = {
    "execution.started",
    "execution.node_started",
    "execution.node_completed",
    "execution.node_failed",
    "execution.checkpoint_entered",
    "execution.checkpoint_completed",
    "execution.approval_waiting",
    "execution.approval_received",
    "execution.completed",
}


def _imported_modules() -> set[str]:
    modules: set[str] = set()
    for path in _PACKAGE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
    return modules


def test_actuation_imports_no_reasoning_provider_or_producer() -> None:
    for module in _imported_modules():
        assert not module.startswith(_FORBIDDEN_PREFIXES), f"forbidden import: {module}"


def test_actuation_defines_no_new_domain_object() -> None:
    # No second Plan / Execution-State domain schema — the state is a ValueObject projection (INV-07).
    for path in _PACKAGE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                assert "DomainObject" not in bases, (
                    f"{path.name}:{node.name} defines a domain object"
                )


def test_execution_state_is_a_value_object() -> None:
    from nexus_core.contracts.base import ValueObject

    assert issubclass(model.ExecutionState, ValueObject)
    assert issubclass(model.NodeState, ValueObject)


def test_the_execution_event_namespace_is_owned_and_complete() -> None:
    declared = {
        value
        for name, value in vars(model).items()
        if name.startswith("EXECUTION_") and isinstance(value, str)
    }
    assert declared >= _REQUIRED_EVENTS
    assert all(event.startswith("execution.") for event in declared)
