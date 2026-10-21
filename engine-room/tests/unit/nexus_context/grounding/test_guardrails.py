"""Architecture guardrails — grounding is upstream-only and introduces no second schema.

Context Engineering (the incumbent) remains the *only* producer of the Context Package
(INV-02, INV-07). This submodule consumes upstream grounding/reasoning value objects read-only
and imports no downstream engine (INV-01), and it defines no alternative context object.
"""

from __future__ import annotations

import ast
import pathlib

import nexus_context.grounding as grounding

_PACKAGE_DIR = pathlib.Path(grounding.__file__).parent

# Downstream capabilities Contextualize must never import (INV-01 one-way spine).
_FORBIDDEN_PREFIXES = (
    "nexus_planning",
    "nexus_orchestration",
    "nexus_execution",
    "nexus_validation",
    "nexus_recovery",
    "nexus_reflection",
    "nexus_runtime",
    "nexus_harness",
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


def test_grounding_imports_no_downstream_engine() -> None:
    for module in _imported_modules():
        assert not module.startswith(_FORBIDDEN_PREFIXES), f"forbidden downstream import: {module}"


def test_grounding_consumes_upstream_models_only() -> None:
    # It reads the upstream producers' value objects, never their engines.
    modules = _imported_modules()
    assert "nexus_engineering.model" in modules
    assert "nexus_history.model" in modules
    assert "nexus_repository.profile" in modules
    assert "nexus_engineering" not in modules  # the engine package itself is never imported
    assert "nexus_history" not in modules
    assert "nexus_repository" not in modules


def test_grounding_defines_no_new_domain_object() -> None:
    # No second Context Package / domain schema — grounding models are ValueObjects/dataclasses.
    for path in _PACKAGE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                assert "DomainObject" not in bases, (
                    f"{path.name}:{node.name} defines a domain object"
                )
