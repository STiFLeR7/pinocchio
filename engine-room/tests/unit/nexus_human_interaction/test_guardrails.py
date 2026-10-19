"""Architecture guardrails — Human Interaction owns no reasoning and drives only the pipeline.

The façade invokes **only** the constitutional pipeline; it calls no engine directly (no engine is
user-callable), records only single-producer ``interaction.*`` facts (INV-02), and adds no frozen domain
object (INV-07). The single-owner invariants it must not breach — Knowledge single-owner, Context sole
context producer, Planning sole planner, Pipeline sole coordinator — are structural: the façade holds no
engine and drives everything through ``ConstitutionalPipeline``.
"""

from __future__ import annotations

import ast
import pathlib

import nexus_human_interaction as hi
from nexus_human_interaction import events as ievents
from nexus_human_interaction import model

_PACKAGE_DIR = pathlib.Path(hi.__file__).parent

# The façade is the operational surface — it must reach the platform only through the pipeline, never an
# engine. (Value DTOs used by the operator request live in model.py and are not engine invocations.)
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


def test_facade_invokes_only_the_pipeline_no_engine() -> None:
    for module in _imports(_PACKAGE_DIR / "facade.py"):
        assert not module.startswith(_ENGINE_PREFIXES), (
            f"façade reaches an engine directly: {module}"
        )
    # It drives the constitutional pipeline (the single sanctioned entry point).
    assert "nexus_workflows.spine" in _imports(_PACKAGE_DIR / "facade.py")


def test_interaction_defines_no_new_domain_object() -> None:
    for path in _PACKAGE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                assert "DomainObject" not in bases, (
                    f"{path.name}:{node.name} defines a domain object"
                )


def test_interaction_session_is_a_value_object() -> None:
    from nexus_core.contracts.base import ValueObject

    assert issubclass(model.InteractionSession, ValueObject)


def test_interaction_events_are_owned_by_one_producer() -> None:
    declared = {
        value
        for name, value in vars(ievents).items()
        if name.startswith("INTERACTION_")
        and isinstance(value, str)
        and value.startswith("interaction.")
    }
    assert declared >= {
        "interaction.session_started",
        "interaction.request_submitted",
        "interaction.response_recorded",
        "interaction.resumed",
    }
    assert ievents.INTERACTION_PRODUCER == "human_interaction"
