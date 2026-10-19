"""``nexus_planning.grounded`` — P10 grounded planning (additive).

Planning is the constitutional owner of converting a grounded engineering objective into an
executable topology. The incumbent ``nexus_planning`` already produces the frozen **Plan**,
**Work Packages**, **Execution Graph**, and **Execution Strategy** (the ``PlanningResult`` bundle)
deterministically. This submodule does **not** create a competing planner. It makes the incumbent
producer *grounding-aware*: it consumes the three canonical inputs — **Goal**, **EngineeringStrategy**
(P5, by value), and **ContextPackage** (P9, by value) — runs the incumbent planner, computes a
deterministic **coordination view** over the resulting graph, and assembles one immutable
:class:`~nexus_planning.grounded.model.ExecutionPlan`.

Constitutional shape:

- The **ExecutionPlan** is the frozen ``Plan`` (which references its sibling Execution Graph by id and
  owns its Work Packages) bundled with the Execution Strategy, capabilities, and coordination metadata
  as a frozen **value** — never a second Plan schema (INV-07). The "Dependency Graph" is the Execution
  Graph's dependency **edges** plus a deterministic dependency view — never a separate object (INV-10).
- Planning consumes the EngineeringStrategy and ContextPackage **by value** and never reasons,
  estimates, evaluates policy, grounds, or assembles context. It imports no reasoning/estimation/policy/
  grounding engine (guardrail-proven; matches the incumbent P6 boundary).
- The assembled ExecutionPlan is recorded in a ``planning.execution_plan_assembled`` fact so replay
  reconstructs it without re-planning; restart reconstructs it identically.
"""

from __future__ import annotations

from nexus_planning.grounded.assembler import (
    PLANNING_EXECUTION_PLAN_ASSEMBLED,
    GroundedPlanner,
    GroundedPlanningObservability,
)
from nexus_planning.grounded.composition import (
    GroundedPlanningContext,
    build_grounded_planning,
)
from nexus_planning.grounded.coordination import analyze_coordination
from nexus_planning.grounded.model import (
    CoordinationView,
    ExecutionPlan,
    PlanningInputs,
)

__all__ = [
    "PLANNING_EXECUTION_PLAN_ASSEMBLED",
    "CoordinationView",
    "ExecutionPlan",
    "GroundedPlanner",
    "GroundedPlanningContext",
    "GroundedPlanningObservability",
    "PlanningInputs",
    "analyze_coordination",
    "build_grounded_planning",
]
