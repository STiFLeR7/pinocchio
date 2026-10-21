"""Architecture guardrails — the Operations Plane owns observation only.

It projects the shared log read-only and derives health; it never controls execution (no ``run`` /
``approve`` / ``deny`` / ``actuate``), never mutates an engine (imports none), and records only
single-producer ``operations.*`` instrumentation (INV-02) — producing no Supervision ``Observation``
domain object (INV-11 stays with Supervision) and no frozen domain object (INV-07).
"""

from __future__ import annotations

import ast
import pathlib

import nexus_operations as operations
from nexus_operations import events as oevents

_PACKAGE_DIR = pathlib.Path(operations.__file__).parent

_ENGINE_PREFIXES = (
    "nexus_intent",
    "nexus_engineering",
    "nexus_estimation",
    "nexus_context",
    "nexus_planning",
    "nexus_knowledge",
    "nexus_policy",
    "nexus_orchestration",
    "nexus_harness",
    "nexus_runtime",
    "nexus_validation",
    "nexus_recovery",
    "nexus_reflection",
    "nexus_execution",
)

# Operations observes; it drives nothing. These are the execution/approval-control verbs it must not call.
_CONTROL_CALLS = (
    ".run(",
    ".approve(",
    ".deny(",
    ".expire(",
    ".publish(",
    ".actuate(",
    ".sweep_expired(",
)


def _imports(path: pathlib.Path) -> set[str]:
    modules: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_operations_imports_no_engine() -> None:
    for path in _PACKAGE_DIR.glob("*.py"):
        for module in _imports(path):
            assert not module.startswith(_ENGINE_PREFIXES), (
                f"{path.name} reaches an engine directly: {module}"
            )


def test_operations_controls_nothing() -> None:
    for path in _PACKAGE_DIR.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for call in _CONTROL_CALLS:
            assert call not in source, f"{path.name} controls execution via {call}"


def test_operations_events_are_owned_by_one_producer() -> None:
    declared = {
        value
        for name, value in vars(oevents).items()
        if name.startswith("OPERATIONS_")
        and isinstance(value, str)
        and value.startswith("operations.")
    }
    assert declared >= {"operations.snapshot"}
    assert oevents.OPERATIONS_PRODUCER == "operations"


def test_operations_defines_no_domain_object() -> None:
    for path in _PACKAGE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                assert "DomainObject" not in bases, (
                    f"{path.name}:{node.name} defines a domain object"
                )
