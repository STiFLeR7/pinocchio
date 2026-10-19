"""Architecture guardrails — the Scheduler owns timing only.

It determines *when* an execution begins and nothing else: it reaches no reasoning/execution engine, drives
a Goal only through the Constitutional Pipeline, delegates governance to Policy (it evaluates none itself —
no ``PolicyDecision``), delegates approvals to the Approval Exchange, and delegates observation to
Operations. It records single-producer ``scheduler.*`` facts (INV-02) and adds no frozen domain object
(INV-07).
"""

from __future__ import annotations

import ast
import pathlib

import nexus_scheduler as scheduler
from nexus_scheduler import events as sevents
from nexus_scheduler import model

_PACKAGE_DIR = pathlib.Path(scheduler.__file__).parent

# The reasoning/execution engines the Scheduler must never reach directly (it owns timing, not their work).
# It legitimately *consults* Policy, *drives* the pipeline, and *delegates* to the Approval / Operations
# surfaces — those are not in this set.
_ENGINE_PREFIXES = (
    "nexus_intent",
    "nexus_engineering",
    "nexus_estimation",
    "nexus_context",
    "nexus_planning",
    "nexus_knowledge",
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


def test_scheduler_reaches_no_engine() -> None:
    for path in _PACKAGE_DIR.glob("*.py"):
        for module in _imports(path):
            assert not module.startswith(_ENGINE_PREFIXES), (
                f"{path.name} reaches an engine directly: {module}"
            )


def test_timing_core_is_a_pure_function_of_time() -> None:
    # The timing core touches no platform surface at all — it is pure occurrence math over injected time.
    for module in _imports(_PACKAGE_DIR / "timing.py"):
        assert not module.startswith("nexus_") or module.startswith("nexus_scheduler"), (
            f"timing.py reaches a platform surface: {module}"
        )


def test_scheduler_drives_execution_only_through_the_pipeline() -> None:
    assert "nexus_workflows.spine" in _imports(_PACKAGE_DIR / "autonomy.py")


def test_autonomy_delegates_to_policy_and_evaluates_none() -> None:
    source = (_PACKAGE_DIR / "autonomy.py").read_text(encoding="utf-8")
    assert "nexus_policy" in _imports(_PACKAGE_DIR / "autonomy.py")  # it consults Policy
    assert ".simulate(" in source  # by asking the sole evaluator
    for forbidden in ("PolicyDecision", ".evaluate("):
        assert forbidden not in source, (
            f"the scheduler must not {forbidden} (Policy owns evaluation)"
        )


def test_scheduler_events_are_owned_by_one_producer() -> None:
    declared = {
        value
        for name, value in vars(sevents).items()
        if name.startswith("SCHEDULER_")
        and isinstance(value, str)
        and value.startswith("scheduler.")
    }
    assert declared >= {
        "scheduler.registered",
        "scheduler.dispatched",
        "scheduler.dispatch_denied",
        "scheduler.dispatch_requested",
        "scheduler.operation_ran",
    }
    assert sevents.SCHEDULER_PRODUCER == "scheduler"


def test_schedule_is_a_value_object_no_domain_object() -> None:
    from nexus_core.contracts.base import ValueObject

    assert issubclass(model.Schedule, ValueObject)
    for path in _PACKAGE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                assert "DomainObject" not in bases, (
                    f"{path.name}:{node.name} defines a domain object"
                )
