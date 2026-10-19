"""Durable grounded Context Engineering (P9) — replay + restart acceptance gate.

Proves the grounding facts are durable and correlated, that replaying the ``context.grounding.*``
stream reconstructs the ExecutionContext (the Context Package) and the selection without
rebuilding, and that restart reconstructs an identical Context Package. Rides P1/ADR-007 unchanged
through the incumbent Context Engineering producer.
"""

from __future__ import annotations

from nexus_context import FixedTimestampSource
from nexus_context.grounding import (
    GroundingSelection,
    build_grounded_context_engineering,
)
from nexus_context.grounding.assembler import (
    CONTEXT_GROUNDING_ASSEMBLED,
    CONTEXT_GROUNDING_SELECTED,
)
from nexus_core.domain.context_package import ContextPackage
from nexus_infra import build_durable_infrastructure
from tests.unit.nexus_context.grounding.fixtures import make_inputs

_FIXED = "1970-01-01T00:00:00+00:00"


def _grounded(db: str):
    infra = build_durable_infrastructure(db)
    return infra, build_grounded_context_engineering(infra, timestamps=FixedTimestampSource(_FIXED))


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def test_grounding_facts_are_durable_and_correlated(tmp_path) -> None:
    db = str(tmp_path / "g.db")
    _, ctx = _grounded(db)
    result = ctx.assembler.assemble(make_inputs(_repo(tmp_path)))

    reopened = build_durable_infrastructure(db)
    grounding = [
        e for e in reopened.event_store.read_all() if e.type.startswith("context.grounding.")
    ]
    assert {e.type for e in grounding} == {CONTEXT_GROUNDING_SELECTED, CONTEXT_GROUNDING_ASSEMBLED}
    assert all(
        e.correlation_identifier == result.package.correlation.correlation_identifier
        for e in grounding
    )


def test_replay_reconstructs_context_without_rebuilding(tmp_path) -> None:
    db = str(tmp_path / "g.db")
    _, ctx = _grounded(db)
    original = ctx.assembler.assemble(make_inputs(_repo(tmp_path)))

    reopened = build_durable_infrastructure(db)
    assembled = next(
        e for e in reopened.event_store.read_all() if e.type == CONTEXT_GROUNDING_ASSEMBLED
    )
    selected = next(
        e for e in reopened.event_store.read_all() if e.type == CONTEXT_GROUNDING_SELECTED
    )
    reconstructed_pkg = ContextPackage.model_validate(assembled.payload["package"])
    reconstructed_sel = GroundingSelection.model_validate(selected.payload)
    assert reconstructed_pkg == original.package  # from the log, no re-assembly
    assert reconstructed_sel == original.selection


def test_restart_reconstruction_is_identical(tmp_path) -> None:
    db = str(tmp_path / "g.db")
    inputs = make_inputs(_repo(tmp_path))  # built once; immutable

    _, ctx_before = _grounded(db)
    before = ctx_before.assembler.assemble(inputs)

    _, ctx_after = _grounded(db)  # fresh engines over the reopened file
    after = ctx_after.assembler.assemble(inputs)

    assert before.package == after.package
    assert before.selection == after.selection
