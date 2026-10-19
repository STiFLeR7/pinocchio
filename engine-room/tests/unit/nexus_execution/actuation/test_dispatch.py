"""RC2 unit — ``_project_intake`` mints a goal-scoped Runtime Session identity.

Guards the root-cause fix: ``package_identity`` must incorporate ``session_identity`` (the
Execution Session id, itself a pure function of goal identity), not ``node.identifier`` alone —
otherwise two goals whose plans produce a work item with the same key mint the identical Runtime
Session id and collide on every downstream ``runtime.*``/``validation.*`` event scope.
"""

from __future__ import annotations

from nexus_core.domain.execution_graph import GraphNode
from nexus_core.domain.work_package import WorkPackage
from nexus_execution.actuation.dispatch import _project_intake
from tests.unit.nexus_execution.actuation.fixtures import item, make_plan


def _node_and_package() -> tuple[GraphNode, WorkPackage]:
    plan = make_plan((item("a"),))
    return plan.execution_graph.nodes[0], plan.work_packages[0]


def test_package_identity_is_scoped_by_session_not_node_alone() -> None:
    node, work_package = _node_and_package()

    intake_g1 = _project_intake(
        node, work_package, None, session_identity="session-g1-v1", correlation="cor-g1"
    )
    intake_g2 = _project_intake(
        node, work_package, None, session_identity="session-g2-v1", correlation="cor-g2"
    )

    assert intake_g1.node == intake_g2.node == node.identifier  # same node key, different goals
    assert intake_g1.package_identity != intake_g2.package_identity


def test_package_identity_is_deterministic_for_the_same_session_and_node() -> None:
    node, work_package = _node_and_package()

    first = _project_intake(
        node, work_package, None, session_identity="session-g1-v1", correlation="cor-g1"
    )
    second = _project_intake(
        node, work_package, None, session_identity="session-g1-v1", correlation="cor-g1"
    )

    assert first.package_identity == second.package_identity
