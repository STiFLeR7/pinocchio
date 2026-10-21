"""Deterministic, explainable relevance selection — the heart of P9 Context Selection."""

from __future__ import annotations

from nexus_context.grounding import GroundingInputs, GroundingSelector
from tests.unit.nexus_context.grounding.fixtures import make_goal, make_inputs


def test_selects_relevant_repository_artifacts(tmp_path) -> None:
    selection = GroundingSelector().select(make_inputs(tmp_path))
    selected = {(r.artifact_type, r.identifier) for r in selection.selected}
    # goal/objective keywords (pkg, thing, contract) select these …
    assert ("contract", "contracts/thing.md") in selected
    assert ("module", "pkg_a") in selected
    assert ("package", "pkg_a") in selected


def test_irrelevant_artifacts_are_omitted_with_a_reason(tmp_path) -> None:
    selection = GroundingSelector().select(make_inputs(tmp_path))
    omitted = {r.identifier: r for r in selection.omitted}
    # … and the ADR / invariant, which no keyword matched, are omitted with a stated reason.
    assert omitted["adr/ADR-001.md"].reason == "no objective/goal keyword matched"
    assert omitted["99_INVARIANTS.md"].reason == "no objective/goal keyword matched"
    assert not omitted["adr/ADR-001.md"].selected


def test_knowledge_is_admitted_by_default(tmp_path) -> None:
    selection = GroundingSelector().select(make_inputs(tmp_path))
    knowledge = {r.identifier for r in selection.selected if r.artifact_type == "knowledge"}
    assert knowledge == {"k1", "k2"}


def test_prior_executions_select_by_relevance(tmp_path) -> None:
    selection = GroundingSelector().select(make_inputs(tmp_path))
    priors = {
        r.identifier: r.selected
        for r in selection.selected + selection.omitted
        if r.artifact_type == "prior_execution"
    }
    assert priors["pkg-a-fix"] is True  # correlation keyword-related to the goal
    assert priors["billing-run"] is False  # unrelated → omitted


def test_every_record_is_fully_explained(tmp_path) -> None:
    selection = GroundingSelector().select(make_inputs(tmp_path))
    for record in (*selection.selected, *selection.omitted):
        assert record.reason  # every inclusion AND omission carries a reason
        assert record.relationship
        assert record.source
        assert record.priority >= 0
    assert all(r.selected for r in selection.selected)
    assert not any(r.selected for r in selection.omitted)


def test_absent_sources_are_explained(tmp_path) -> None:
    inputs = GroundingInputs(goal=make_goal())  # no repo, history, strategy, or knowledge
    selection = GroundingSelector().select(inputs)
    absent = {r.source: r.reason for r in selection.omitted if r.identifier == "(source absent)"}
    assert set(absent) == {"repository", "execution_history", "engineering_strategy", "knowledge"}
    assert "no repository profile" in absent["repository"]


def test_objectives_drive_the_criteria(tmp_path) -> None:
    inputs = make_inputs(tmp_path)
    selection = GroundingSelector().select(inputs)
    assert selection.objectives == tuple(inputs.engineering_strategy.context_objectives.selection)
    # objective tokens contribute to the keyword set.
    assert any(kw in selection.keywords for kw in ("map", "code", "tests"))


def test_cap_demotes_overflow_with_a_rank_reason(tmp_path) -> None:
    selection = GroundingSelector(caps={"module": 1}).select(make_inputs(tmp_path))
    modules_selected = [r for r in selection.selected if r.artifact_type == "module"]
    demoted = [r for r in selection.omitted if r.artifact_type == "module" and "cap" in r.reason]
    assert len(modules_selected) == 1
    assert demoted and "rank 2 of 2" in demoted[0].reason


def test_selection_is_deterministic(tmp_path) -> None:
    inputs = make_inputs(tmp_path)
    assert GroundingSelector().select(inputs) == GroundingSelector().select(inputs)
