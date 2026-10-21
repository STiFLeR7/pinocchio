"""Architecture guardrails — the Approval Exchange owns approval coordination only.

It publishes/records/resumes the approval lifecycle and nothing else: it evaluates no policy (Policy is the
sole evaluator, INV-28), executes nothing (Actuation owns traversal, INV-23 — it resumes only by driving
the pipeline), and plans/reasons/validates/recovers nothing. Structurally: it imports no engine, drives
only ``nexus_workflows.spine``, records single-producer ``approval.*`` facts (INV-02), and adds no frozen
domain object (INV-07).
"""

from __future__ import annotations

import ast
import pathlib

import nexus_approval as approval
from nexus_approval import events as aevents
from nexus_approval import model

_PACKAGE_DIR = pathlib.Path(approval.__file__).parent

# The exchange coordinates approvals — it must reach no engine (its only collaborator is the pipeline).
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


def _imports(path: pathlib.Path) -> set[str]:
    modules: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_exchange_imports_no_engine() -> None:
    for path in _PACKAGE_DIR.glob("*.py"):
        for module in _imports(path):
            assert not module.startswith(_ENGINE_PREFIXES), (
                f"{path.name} reaches an engine directly: {module}"
            )


def test_exchange_drives_only_the_pipeline() -> None:
    # Its one sanctioned collaborator is the single execution coordinator — no competing coordinator.
    assert "nexus_workflows.spine" in _imports(_PACKAGE_DIR / "exchange.py")


def test_exchange_evaluates_no_policy_and_executes_nothing() -> None:
    source = (_PACKAGE_DIR / "exchange.py").read_text(encoding="utf-8")
    for forbidden in (".evaluate(", ".simulate(", ".actuate(", "PolicyDecision"):
        assert forbidden not in source, f"the exchange must not {forbidden}"


def test_approval_events_are_owned_by_one_producer() -> None:
    declared = {
        value
        for name, value in vars(aevents).items()
        if name.startswith("APPROVAL_") and isinstance(value, str) and value.startswith("approval.")
    }
    assert declared >= {
        "approval.requested",
        "approval.pending",
        "approval.approved",
        "approval.denied",
        "approval.expired",
    }
    assert aevents.APPROVAL_PRODUCER == "approval_exchange"  # one owner for every approval.* fact


def test_approval_projections_are_value_objects_no_domain_object() -> None:
    from nexus_core.contracts.base import ValueObject

    assert issubclass(model.ApprovalSession, ValueObject)
    assert issubclass(model.ApprovalRequest, ValueObject)
    for path in _PACKAGE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                assert "DomainObject" not in bases, (
                    f"{path.name}:{node.name} defines a domain object"
                )
