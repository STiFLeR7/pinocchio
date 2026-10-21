"""Deterministic coordination analysis — parallel groups, merge boundaries, dependency edges."""

from __future__ import annotations

from tests.unit.nexus_planning.grounded.fixtures import item, make_inputs, wired_grounded


def _plan(work_items):
    _, ctx = wired_grounded()
    return ctx.planner.plan(make_inputs(work_items=work_items)).coordination


def test_diamond_topology_yields_parallel_and_merge() -> None:
    # a → {b, c} → d : fan-out at a, parallel b/c, fan-in (merge) at d.
    coord = _plan(
        (
            item("a"),
            item("b", depends_on=("a",)),
            item("c", depends_on=("a",)),
            item("d", depends_on=("b", "c")),
        )
    )
    assert coord.dependency_edges == (
        ("node-a", "node-b"),
        ("node-a", "node-c"),
        ("node-b", "node-d"),
        ("node-c", "node-d"),
    )
    assert coord.parallel_groups == (("node-b", "node-c"),)
    assert coord.fan_out_points == ("node-a",)
    assert coord.merge_boundaries == ("node-d",)
    assert coord.sequential_levels == (("node-a",), ("node-b", "node-c"), ("node-d",))


def test_linear_chain_has_no_parallel_groups() -> None:
    coord = _plan((item("a"), item("b", depends_on=("a",)), item("c", depends_on=("b",))))
    assert coord.parallel_groups == ()
    assert coord.merge_boundaries == ()
    assert coord.fan_out_points == ()
    assert coord.sequential_levels == (("node-a",), ("node-b",), ("node-c",))


def test_independent_items_are_one_parallel_group() -> None:
    coord = _plan((item("a"), item("b"), item("c")))
    assert coord.parallel_groups == (("node-a", "node-b", "node-c"),)
    assert coord.dependency_edges == ()
    assert coord.sequential_levels == (("node-a", "node-b", "node-c"),)


def test_governed_boundaries_are_read_from_the_graph() -> None:
    coord = _plan(
        (item("a"), item("b", depends_on=("a",), is_checkpoint=True, requires_approval=True))
    )
    assert coord.checkpoint_boundaries == ("node-b",)
    assert coord.approval_boundaries == ("node-b",)
    assert coord.recovery_boundaries == ("node-b",)  # recovery resumes from checkpoints (INV-18)


def test_coordination_is_deterministic() -> None:
    items = (item("a"), item("b", depends_on=("a",)), item("c", depends_on=("a",)))
    assert _plan(items) == _plan(items)
