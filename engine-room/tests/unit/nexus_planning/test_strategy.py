"""Unit tests for the Execution Strategy assigner (Step 5, ADR-004, INV-05).

The Strategy is derived deterministically from the declared topology: the
coordination model from the dependency shape (or an explicit hint), the approval
policy from the count of approval-gated items, and the checkpoint policy from
checkpoint-flagged items. The Strategy declares; it never executes (runtime_policy
is empty per INV-05/INV-37; retry is NEVER_RETRY).
"""

from __future__ import annotations

from nexus_core.contracts.enums import (
    ApprovalTaxonomy,
    CoordinationModel,
    RetryBehavior,
)
from nexus_planning import PlanningRequest, StrategyAssigner

from .helpers import item, make_goal

GOAL = "goal-1"


def _assign(*items, version: str = "1", coordination_hint=None):
    """Assign an ExecutionStrategy directly from work items via the assigner."""
    goal = make_goal(GOAL)
    request = PlanningRequest(
        work_items=tuple(items),
        plan_version=version,
        coordination_hint=coordination_hint,
    )
    return StrategyAssigner().assign(goal, request, correlation_identifier=f"cor-{GOAL}")


# --------------------------------------------------------------------------- #
# Coordination derivation                                                     #
# --------------------------------------------------------------------------- #


def test_single_item_no_deps_is_sequential():
    strategy = _assign(item("a"))

    assert strategy.coordination is CoordinationModel.SEQUENTIAL


def test_multiple_items_no_deps_is_parallel():
    strategy = _assign(item("a"), item("b"), item("c"))

    assert strategy.coordination is CoordinationModel.PARALLEL


def test_linear_chain_is_sequential():
    strategy = _assign(
        item("a"),
        item("b", depends_on=("a",)),
        item("c", depends_on=("b",)),
    )

    assert strategy.coordination is CoordinationModel.SEQUENTIAL


def test_branching_join_is_hybrid():
    strategy = _assign(
        item("a"),
        item("b"),
        item("c", depends_on=("a", "b")),
    )

    assert strategy.coordination is CoordinationModel.HYBRID


def test_any_approval_is_approval_driven():
    # Approval takes precedence over the dependency-derived model.
    strategy = _assign(
        item("a"),
        item("b", depends_on=("a",), requires_approval=True),
    )

    assert strategy.coordination is CoordinationModel.APPROVAL_DRIVEN


def test_coordination_hint_overrides_derivation():
    # Topology alone would derive PARALLEL; the hint must win.
    strategy = _assign(
        item("a"),
        item("b"),
        coordination_hint=CoordinationModel.PIPELINE,
    )

    assert strategy.coordination is CoordinationModel.PIPELINE


# --------------------------------------------------------------------------- #
# Approval policy                                                             #
# --------------------------------------------------------------------------- #


def test_no_approvals_is_automatic():
    strategy = _assign(item("a"), item("b"))

    assert strategy.approval_policy is ApprovalTaxonomy.AUTOMATIC


def test_single_approval_is_human_review():
    strategy = _assign(item("a", requires_approval=True), item("b"))

    assert strategy.approval_policy is ApprovalTaxonomy.HUMAN_REVIEW


def test_multiple_approvals_is_multi_stage():
    strategy = _assign(
        item("a", requires_approval=True),
        item("b", requires_approval=True),
    )

    assert strategy.approval_policy is ApprovalTaxonomy.MULTI_STAGE


# --------------------------------------------------------------------------- #
# Retry / runtime / checkpoint policy                                         #
# --------------------------------------------------------------------------- #


def test_retry_policy_is_never_retry():
    strategy = _assign(item("a"))

    assert strategy.retry_policy is RetryBehavior.NEVER_RETRY


def test_runtime_policy_is_empty():
    # INV-05 / INV-37: the Strategy never names a runtime.
    strategy = _assign(item("a"))

    assert strategy.runtime_policy == {}


def test_checkpoint_policy_lists_checkpoint_keys():
    strategy = _assign(
        item("a", is_checkpoint=True),
        item("b"),
        item("c", is_checkpoint=True),
    )

    assert strategy.checkpoint_policy["required_checkpoints"] == ["a", "c"]


def test_checkpoint_policy_empty_when_no_checkpoints():
    strategy = _assign(item("a"), item("b"))

    assert strategy.checkpoint_policy["required_checkpoints"] == []


# --------------------------------------------------------------------------- #
# Identity / version                                                          #
# --------------------------------------------------------------------------- #


def test_identity_and_version():
    strategy = _assign(item("a"), version="3")

    assert strategy.identity == f"strategy-{GOAL}-v3"
    assert strategy.version == "3"
