"""Unit tests for the Approval Coordinator (Phase 5 — Orchestration, Step 4).

The coordinator *enforces* approval gates identified by Planning: every gated node
gets the strategy's single approval taxonomy (the *kind*) and a deterministic
decision *state*. Gates are discovered from ``policies['approval_gates']`` UNION
nodes carrying a ``Constraint(kind="approval")`` (deduped, restricted to nodes that
exist). There is no UI here — only the decision.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.enums import ApprovalTaxonomy
from nexus_orchestration.approvals import (
    APPROVAL_CONSTRAINT_KIND,
    ApprovalCoordinator,
    ApprovalGate,
    ApprovalState,
)
from nexus_orchestration.vocabulary import ApprovalStatus
from tests.unit.nexus_orchestration.helpers import gnode, make_graph, make_strategy

SESSION = "session-goal-1-v1"

NON_AUTOMATIC = (
    ApprovalTaxonomy.HUMAN_REVIEW,
    ApprovalTaxonomy.MULTI_STAGE,
    ApprovalTaxonomy.DEFERRED,
)


def _coordinate(
    *,
    taxonomy: ApprovalTaxonomy,
    approval_gates: tuple[str, ...] = (),
    constraint_nodes: tuple[str, ...] = (),
    approved: tuple[str, ...] = (),
    rejected: tuple[str, ...] = (),
) -> ApprovalState:
    """Coordinate a small graph whose gates come from policies and/or node constraints."""
    keys = {"build", "test", "deploy"}
    nodes = tuple(gnode(key, approval=(f"node-{key}" in constraint_nodes)) for key in sorted(keys))
    graph = make_graph(nodes, approval_gates=approval_gates)
    strategy = make_strategy(approval_policy=taxonomy)
    return ApprovalCoordinator().coordinate(
        graph, strategy, SESSION, approved=approved, rejected=rejected
    )


# --------------------------------------------------------------------------- #
# Taxonomy → decision state                                                    #
# --------------------------------------------------------------------------- #


def test_automatic_taxonomy_grants_every_gate() -> None:
    state = _coordinate(
        taxonomy=ApprovalTaxonomy.AUTOMATIC, approval_gates=("node-build", "node-deploy")
    )

    assert {gate.node for gate in state.gates} == {"node-build", "node-deploy"}
    assert all(gate.status is ApprovalStatus.GRANTED for gate in state.gates)
    assert all(gate.taxonomy is ApprovalTaxonomy.AUTOMATIC for gate in state.gates)
    assert state.granted == ("node-build", "node-deploy")
    assert state.requested == ()
    assert state.rejected == ()


@pytest.mark.parametrize("taxonomy", NON_AUTOMATIC)
def test_non_automatic_taxonomy_requests_by_default(taxonomy: ApprovalTaxonomy) -> None:
    state = _coordinate(taxonomy=taxonomy, approval_gates=("node-build",))

    (gate,) = state.gates
    assert gate.node == "node-build"
    assert gate.taxonomy is taxonomy
    assert gate.status is ApprovalStatus.REQUESTED
    assert state.requested == ("node-build",)
    assert state.granted == ()
    assert state.rejected == ()


@pytest.mark.parametrize("taxonomy", NON_AUTOMATIC)
def test_non_automatic_grants_node_listed_in_approved(taxonomy: ApprovalTaxonomy) -> None:
    state = _coordinate(
        taxonomy=taxonomy,
        approval_gates=("node-build", "node-deploy"),
        approved=("node-build",),
    )

    statuses = {gate.node: gate.status for gate in state.gates}
    assert statuses["node-build"] is ApprovalStatus.GRANTED
    assert statuses["node-deploy"] is ApprovalStatus.REQUESTED
    assert state.granted == ("node-build",)
    assert state.requested == ("node-deploy",)


@pytest.mark.parametrize(
    "taxonomy",
    (
        ApprovalTaxonomy.AUTOMATIC,
        ApprovalTaxonomy.HUMAN_REVIEW,
        ApprovalTaxonomy.MULTI_STAGE,
        ApprovalTaxonomy.DEFERRED,
    ),
)
def test_rejection_overrides_every_taxonomy(taxonomy: ApprovalTaxonomy) -> None:
    state = _coordinate(
        taxonomy=taxonomy,
        approval_gates=("node-build",),
        rejected=("node-build",),
    )

    (gate,) = state.gates
    assert gate.status is ApprovalStatus.REJECTED
    assert state.rejected == ("node-build",)
    assert state.granted == ()
    assert state.requested == ()


def test_rejection_overrides_approval_for_the_same_node() -> None:
    state = _coordinate(
        taxonomy=ApprovalTaxonomy.HUMAN_REVIEW,
        approval_gates=("node-build",),
        approved=("node-build",),
        rejected=("node-build",),
    )

    (gate,) = state.gates
    assert gate.status is ApprovalStatus.REJECTED
    assert state.rejected == ("node-build",)


# --------------------------------------------------------------------------- #
# Gate discovery                                                               #
# --------------------------------------------------------------------------- #


def test_gates_discovered_from_policies_only() -> None:
    state = _coordinate(taxonomy=ApprovalTaxonomy.HUMAN_REVIEW, approval_gates=("node-deploy",))

    assert tuple(gate.node for gate in state.gates) == ("node-deploy",)


def test_gates_discovered_from_node_constraints_only() -> None:
    state = _coordinate(taxonomy=ApprovalTaxonomy.HUMAN_REVIEW, constraint_nodes=("node-test",))

    assert tuple(gate.node for gate in state.gates) == ("node-test",)


def test_constraint_kind_is_the_approval_kind() -> None:
    # Guards the discovery contract: the constraint that gates a node uses
    # exactly APPROVAL_CONSTRAINT_KIND.
    assert APPROVAL_CONSTRAINT_KIND == "approval"
    node = gnode("build", approval=True)
    assert any(c.kind == APPROVAL_CONSTRAINT_KIND for c in node.constraints)


def test_gates_union_dedupes_overlap() -> None:
    # node-build appears in BOTH policies and as a constraint → counted once.
    state = _coordinate(
        taxonomy=ApprovalTaxonomy.AUTOMATIC,
        approval_gates=("node-build", "node-deploy"),
        constraint_nodes=("node-build", "node-test"),
    )

    nodes = tuple(gate.node for gate in state.gates)
    assert nodes == ("node-build", "node-deploy", "node-test")
    assert len(nodes) == len(set(nodes))


def test_gates_restricted_to_nodes_that_exist() -> None:
    # A policy gate naming a non-existent node is dropped.
    state = _coordinate(
        taxonomy=ApprovalTaxonomy.AUTOMATIC,
        approval_gates=("node-build", "node-ghost"),
    )

    assert tuple(gate.node for gate in state.gates) == ("node-build",)


# --------------------------------------------------------------------------- #
# Empty / partition / ordering / identity                                      #
# --------------------------------------------------------------------------- #


def test_no_gated_nodes_yields_empty_state() -> None:
    state = _coordinate(taxonomy=ApprovalTaxonomy.HUMAN_REVIEW)

    assert state.gates == ()
    assert state.requested == ()
    assert state.granted == ()
    assert state.rejected == ()


def test_gates_sorted_by_node_id() -> None:
    state = _coordinate(
        taxonomy=ApprovalTaxonomy.AUTOMATIC,
        approval_gates=("node-test", "node-deploy", "node-build"),
    )

    nodes = tuple(gate.node for gate in state.gates)
    assert nodes == ("node-build", "node-deploy", "node-test")
    assert nodes == tuple(sorted(nodes))


def test_lists_partition_the_gates() -> None:
    state = _coordinate(
        taxonomy=ApprovalTaxonomy.HUMAN_REVIEW,
        approval_gates=("node-build", "node-deploy", "node-test"),
        approved=("node-build",),
        rejected=("node-deploy",),
    )

    gated = {gate.node for gate in state.gates}
    partitioned = set(state.requested) | set(state.granted) | set(state.rejected)
    assert partitioned == gated
    # Disjoint partition.
    assert len(state.requested) + len(state.granted) + len(state.rejected) == len(gated)
    assert state.granted == ("node-build",)
    assert state.rejected == ("node-deploy",)
    assert state.requested == ("node-test",)


def test_identity_and_session_reference() -> None:
    state = _coordinate(taxonomy=ApprovalTaxonomy.AUTOMATIC, approval_gates=("node-build",))

    assert state.identity == f"approvals-{SESSION}"
    assert state.session_ref.identifier == SESSION
    assert state.session_ref.target_type == "execution_session"


def test_determinism_same_inputs_same_state() -> None:
    first = _coordinate(
        taxonomy=ApprovalTaxonomy.MULTI_STAGE,
        approval_gates=("node-build", "node-deploy"),
        approved=("node-build",),
    )
    second = _coordinate(
        taxonomy=ApprovalTaxonomy.MULTI_STAGE,
        approval_gates=("node-build", "node-deploy"),
        approved=("node-build",),
    )

    assert first == second


# --------------------------------------------------------------------------- #
# Immutability                                                                  #
# --------------------------------------------------------------------------- #


def test_approval_gate_is_frozen() -> None:
    gate = ApprovalGate(
        node="node-build",
        taxonomy=ApprovalTaxonomy.AUTOMATIC,
        status=ApprovalStatus.GRANTED,
    )
    with pytest.raises(ValidationError):
        gate.status = ApprovalStatus.REJECTED  # type: ignore[misc]


def test_approval_state_is_frozen() -> None:
    state = _coordinate(taxonomy=ApprovalTaxonomy.AUTOMATIC, approval_gates=("node-build",))
    with pytest.raises(ValidationError):
        state.gates = ()  # type: ignore[misc]
