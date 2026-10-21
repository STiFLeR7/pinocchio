"""The graph walker + dependency resolver — dependency ordering, parallel waves, determinism."""

from __future__ import annotations

from nexus_execution.actuation.traversal import checkpoint_nodes
from tests.unit.nexus_execution.actuation.fixtures import item, make_plan, walker_context


def _wave(plan, completed=(), blocked=()):
    walker, session, approvals, correlation = walker_context(plan)
    return walker.next_wave(
        plan.execution_graph,
        plan.execution_strategy,
        session,
        approvals,
        completed=completed,
        blocked_sources=blocked,
        correlation=correlation,
    )


def test_entry_node_is_the_only_initial_ready_node() -> None:
    plan = make_plan((item("a"), item("b", depends_on=("a",))))
    wave = _wave(plan)
    assert wave.ready == ("node-a",)  # node-b's dependency is unmet → not ready
    assert "node-b" in wave.blocked


def test_dependents_become_ready_only_after_predecessor_completes() -> None:
    plan = make_plan((item("a"), item("b", depends_on=("a",)), item("c", depends_on=("b",))))
    assert _wave(plan, completed=("node-a",)).ready == ("node-b",)
    assert _wave(plan, completed=("node-a", "node-b")).ready == ("node-c",)


def test_diamond_fan_out_is_one_parallel_wave() -> None:
    # a → {b, c} → d : once a completes, b and c are ready together (parallel execution).
    plan = make_plan(
        (
            item("a"),
            item("b", depends_on=("a",)),
            item("c", depends_on=("a",)),
            item("d", depends_on=("b", "c")),
        )
    )
    assert _wave(plan, completed=("node-a",)).ready == ("node-b", "node-c")
    # d waits for BOTH b and c (fan-in / synchronization barrier): with only b done, c is still ready
    # and d is not.
    assert _wave(plan, completed=("node-a", "node-b")).ready == ("node-c",)
    assert _wave(plan, completed=("node-a", "node-b", "node-c")).ready == ("node-d",)


def test_a_blocked_source_transitively_blocks_its_dependents() -> None:
    plan = make_plan((item("a"), item("b", depends_on=("a",))))
    # a failed/paused → its dependent b cannot become ready.
    wave = _wave(plan, blocked=("node-a",))
    assert "node-b" in wave.blocked
    assert wave.ready == ("node-a",)  # a itself is still ready; the block is on its successors


def test_next_wave_is_deterministic() -> None:
    plan = make_plan((item("a"), item("b", depends_on=("a",)), item("c", depends_on=("a",))))
    assert _wave(plan, completed=("node-a",)) == _wave(plan, completed=("node-a",))


def test_checkpoint_nodes_strip_the_prefix() -> None:
    plan = make_plan((item("a"), item("b", depends_on=("a",), is_checkpoint=True)))
    assert checkpoint_nodes(plan.execution_graph) == frozenset({"node-b"})
