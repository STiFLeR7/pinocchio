"""Architecture guardrails — the spine coordinates owners; it adds no schema and no competing framework.

The constitutional pipeline owns the *orchestration of the constitutional stages only* (the additive
``pipeline.*`` events, one producer — INV-02). It records no new frozen domain object (INV-07), and it
*reuses* the incumbent pipeline wiring and the owners' public composition roots rather than building a
second orchestration framework (F-1 — no competing coordinator).
"""

from __future__ import annotations

import ast
import pathlib

import nexus_workflows.spine as spine
from nexus_workflows.spine import events as pevents
from nexus_workflows.spine import model

_PACKAGE_DIR = pathlib.Path(spine.__file__).parent

_REQUIRED_EVENTS = {
    "pipeline.started",
    "pipeline.stage_started",
    "pipeline.stage_completed",
    "pipeline.paused",
    "pipeline.resumed",
    "pipeline.completed",
}


def test_pipeline_event_namespace_is_owned_and_single_producer() -> None:
    declared = {
        value
        for name, value in vars(pevents).items()
        if name.startswith("PIPELINE_") and isinstance(value, str) and value.startswith("pipeline.")
    }
    assert declared >= _REQUIRED_EVENTS
    assert all(event.startswith("pipeline.") for event in declared)
    assert pevents.PIPELINE_PRODUCER == "pipeline"  # one owner for every pipeline.* fact


def test_pipeline_defines_no_new_domain_object() -> None:
    # The pipeline session is a ValueObject projection of the log — no second frozen schema (INV-07).
    for path in _PACKAGE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                assert "DomainObject" not in bases, (
                    f"{path.name}:{node.name} defines a domain object"
                )


def test_pipeline_session_is_a_value_object() -> None:
    from nexus_core.contracts.base import ValueObject

    assert issubclass(model.PipelineSession, ValueObject)


def test_spine_reuses_public_composition_roots_no_competing_framework() -> None:
    # It integrates only through existing public interfaces and reuses the incumbent pipeline wiring.
    source = (_PACKAGE_DIR / "composition.py").read_text(encoding="utf-8")
    for public_root in (
        "PipelineBuilder",  # reuses the incumbent pipeline (does not replace it)
        "build_intent",
        "build_engineering",
        "build_grounded_planning",
    ):
        assert public_root in source, f"spine must drive owners via the public root {public_root}"
