# Operational Explorer (Milestone 3)

`OperationalExplorer` exposes the operational objects an operator inspects as lightweight, immutable
view records projected from the retained `WorkflowRun`s and the durable Knowledge store. It performs
**no mutation** — every method is a read.

## Supported entities

| Entity | Method | View | Source |
|---|---|---|---|
| Goals | `goals()` / `goal(id)` | `GoalView` | `run.goal_ref`, submission title/status |
| Plans | `plans()` | `PlanView` | `run.plan_ref`, `run.work_package_ids` |
| Work Packages | `work_packages()` | `WorkPackageView` | per-node validation + recovery decision |
| Runtime Sessions | `runtime_sessions()` | `RuntimeSessionView` | `run.session_ids` × `execution_outcomes` |
| Validation Reports | `validation_reports()` | `ValidationReportView` | per-node decision + evidence refs |
| Recovery Plans | `recovery_plans()` | `RecoveryPlanView` | per-node recovery decision |
| Reflection Reports | `reflection_reports()` | `ReflectionReportView` | `run.reflection_ref` + candidates |
| Knowledge Items | `knowledge_items()` | `KnowledgeItemView` | the durable `KnowledgeRepository` |
| Briefings | `briefings()` | `BriefingView` | the composed `Brief` per briefing submission |

Lists are deterministically ordered (by identifier) so the operator sees stable output.

## Correlate by node, never by index

Validation and Recovery views must attribute the right decision to the right work package. For one
run the execution / validation / recovery stages run in **session order**, which is *not* the
declared work-item order, and `validation_decisions` / `recovery_decisions` are index-aligned to
that session order. So the explorer keys on the *node* (via `analysis.node_outcomes`): it pairs each
validation stage with its execution stage by node and reads the decision at the aligned index, then
maps the node back to its work-package id by shared step key. Attributing decisions by
work-package-id index would silently mislabel them.

## Knowledge from the durable store

`knowledge_items()` reads the actual `KnowledgeRepository` (`items.list_all()`), not a projection of
the run — so it reflects the accumulated, subject-keyed understanding the whole session has built,
with each item's type, understanding, and confidence-ladder position. Before the first submission
(no store yet) it returns an empty tuple.

## Navigation

The explorer is designed for drill-down: `goal(goal_id)` → its `PlanView` (via `plans()`) → its
`work_package_ids` → the matching `WorkPackageView` / `ValidationReportView` / `RecoveryPlanView`,
and each validation view's `evidence_refs` point at the persisted evidence the Validation engine
collected. No mutation is possible through any of these paths.
