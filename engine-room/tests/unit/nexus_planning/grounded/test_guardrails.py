"""Architecture guardrails — Planning consumes by value, reasons nothing, owns the ExecutionPlan.

Planning imports no reasoning/estimation/policy/grounding engine (INV-01; matches the incumbent P6
boundary — the EngineeringStrategy and ContextPackage are consumed by value only), and introduces no
alternative Plan/ExecutionPlan domain schema (INV-07). The ExecutionPlan bundles the frozen ``Plan``.
"""

from __future__ import annotations

import ast
import pathlib

import nexus_planning.grounded as grounded

_PACKAGE_DIR = pathlib.Path(grounded.__file__).parent

# Engines Planning must never import (it consumes their VALUE OBJECTS by value, never reasons).
_FORBIDDEN_PREFIXES = (
    "nexus_estimation",
    "nexus_policy",
    "nexus_runtime",
    "nexus_repository",
    "nexus_intent",
    "nexus_history",
    "nexus_knowledge",
    "nexus_context",  # consumes ContextPackage from nexus_core.domain, never the CE engine
)


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


def test_planning_imports_no_reasoning_or_grounding_engine() -> None:
    for module in _imported_modules():
        assert not module.startswith(_FORBIDDEN_PREFIXES), f"forbidden import: {module}"


def test_engineering_strategy_is_consumed_by_value_only() -> None:
    # The only nexus_engineering import is the value-object model — never the reasoning engine.
    engineering = {m for m in _imported_modules() if m.startswith("nexus_engineering")}
    assert engineering == {"nexus_engineering.model"}


def test_grounded_defines_no_new_domain_object() -> None:
    # No second Plan / ExecutionPlan domain schema — grounded models are ValueObjects/dataclasses.
    for path in _PACKAGE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                assert "DomainObject" not in bases, (
                    f"{path.name}:{node.name} defines a domain object"
                )


def test_execution_plan_bundles_the_frozen_plan() -> None:
    from nexus_core.domain.plan import Plan
    from nexus_planning.grounded.model import ExecutionPlan

    assert (
        ExecutionPlan.model_fields["plan"].annotation is Plan
    )  # the one frozen Plan schema (INV-07)
