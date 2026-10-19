# Operational Dashboard (Milestone 5)

`build_dashboard(history, knowledge)` computes an `OperationalDashboard` **derived entirely from
persisted state** — the retained submission history and the durable Knowledge store. It stores no
state of its own and decides nothing; it is a pure aggregation.

## Metrics

| Field | Meaning | Derived from |
|---|---|---|
| `running_workflows` | in-flight workflows | always `0` (see below) |
| `completed_workflows` | submissions that fully executed | `run.succeeded` |
| `failed_workflows` | submissions with a failed execution | `not run.succeeded` |
| `validation_passed` / `validation_failed` | per-work-package validation verdicts | `node_outcomes` |
| `recovery_breakdown` | governed recovery decision → count | `node_outcomes` |
| `knowledge_items` | durable Knowledge Items in the store | `items.list_all()` |
| `briefings_generated` / `briefings_publishable` | briefing submissions and publishable ones | `history.briefings()` |
| `total_workflows` | every submission processed | running + completed + failed |

## Why `running_workflows` is always 0

Execution in this control plane is synchronous and deterministic — a submission fully completes
before `submit_goal` / `generate_briefing` returns, so there is never an in-flight workflow to
report. The dashboard states this honestly (`running_workflows == 0`) rather than inventing a
concurrent-execution model the platform does not have; completed / failed counts derive from the
persisted execution outcomes. If asynchronous submission is added later, this field becomes the
count of submissions whose run has not yet terminated — no other field changes.

## Derived, not tracked

Every number is recomputed from persisted state on each access, so the dashboard is always
consistent with the event-sourced truth and needs no separate bookkeeping to keep in sync. Knowledge
growth, for example, is simply the current size of the durable store: as submissions with distinct
Knowledge subjects accumulate, `knowledge_items` rises, and the same store feeds a later
submission's Planning (INV-26). A failed submission shows up as a `failed_workflows` increment, a
`validation_failed` increment per work package, and a `retry` entry in `recovery_breakdown` — all
from the same persisted outcomes the explorer reads.
