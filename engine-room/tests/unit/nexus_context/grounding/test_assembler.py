"""The grounded assembler — feeds the incumbent producer; emits grounding facts; deterministic."""

from __future__ import annotations

from nexus_context.grounding.assembler import (
    CONTEXT_GROUNDING_ASSEMBLED,
    CONTEXT_GROUNDING_SELECTED,
)
from nexus_core.domain.context_package import ContextPackage
from tests.unit.nexus_context.grounding.fixtures import make_inputs, wired_grounded


def _types(infra):
    return [e.type for e in infra.event_store.read_all()]


def test_assemble_produces_the_one_context_package(tmp_path) -> None:
    inputs = make_inputs(tmp_path)
    infra, ctx = wired_grounded()
    result = ctx.assembler.assemble(inputs)
    assert isinstance(result.package, ContextPackage)  # the frozen object, not a new schema
    assert result.package.goal_ref.identifier == inputs.goal.identity
    assert result.package.validation_status  # packaged by the incumbent producer


def test_selected_artifacts_surface_in_the_package(tmp_path) -> None:
    inputs = make_inputs(tmp_path)
    _, ctx = wired_grounded()
    package = ctx.assembler.assemble(inputs).package
    assert "contract:contracts/thing.md" in package.references
    assert any(ref.startswith("module:") for ref in package.references)
    assert any(ref.startswith("knowledge:") for ref in package.references)
    supporting = {(r.target_type, r.identifier) for r in package.supporting_artifacts}
    assert ("contract", "contracts/thing.md") in supporting
    assert ("knowledge", "k1") in supporting


def test_grounding_facts_are_emitted(tmp_path) -> None:
    inputs = make_inputs(tmp_path)
    infra, ctx = wired_grounded()
    result = ctx.assembler.assemble(inputs)
    types = _types(infra)
    assert CONTEXT_GROUNDING_SELECTED in types
    assert CONTEXT_GROUNDING_ASSEMBLED in types
    assembled = next(
        e for e in infra.event_store.read_all() if e.type == CONTEXT_GROUNDING_ASSEMBLED
    )
    assert assembled.payload["context"] == result.package.identity
    assert assembled.payload["selected"] == len(result.selection.selected)


def test_absent_source_becomes_a_known_unknown(tmp_path) -> None:
    inputs = make_inputs(tmp_path, repo=False)
    _, ctx = wired_grounded()
    package = ctx.assembler.assemble(inputs).package
    assert any(g.startswith("grounding_gap:repository:") for g in package.known_unknowns)


def test_assembly_is_deterministic(tmp_path) -> None:
    inputs = make_inputs(tmp_path)
    _, ctx_a = wired_grounded()
    _, ctx_b = wired_grounded()
    a = ctx_a.assembler.assemble(inputs)
    b = ctx_b.assembler.assemble(inputs)
    assert a.package == b.package  # identical inputs → byte-identical Context Package
    assert a.selection == b.selection


def test_result_reexposes_the_incumbent_package(tmp_path) -> None:
    inputs = make_inputs(tmp_path)
    _, ctx = wired_grounded()
    result = ctx.assembler.assemble(inputs)
    assert result.package is result.result.package
