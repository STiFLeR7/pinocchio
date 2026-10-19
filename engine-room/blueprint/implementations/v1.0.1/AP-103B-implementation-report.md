# AP-103B — Scheduler Foundation Implementation Report

> **Release:** Nexus v1.0.1 "Alignment" · **AP:** AP-103B · **Finding:** A-003
> **Type:** Implementation under TDD · **Status:** ✅ Complete · 143 tests pass, ruff + mypy clean.
> **Approval basis:** AP-103A (J5/J6 approved as read-only observability; feeds config approved;
> 4 scheduler event types approved; cadences fixed).

---

## 1. Scope

Implement the approved Scheduler Foundation: an APScheduler-backed scheduler behind a replaceable
port, six thin job wrappers invoking existing services, the four scheduler audit events, additive
scheduling config, and two read-only health services (J5/J6). No migrations, no behavior changes to
governance/runtime/execution.

## 2. What was built

### New modules
| File | Purpose |
|---|---|
| `nexus/scheduling/scheduler.py` | `SchedulerPort` Protocol + `APSchedulerAdapter` (AsyncIOScheduler) + `build_scheduler` |
| `nexus/scheduling/jobs.py` | `JobSkippedError`, audited `run_scheduled_job`, 6 thin job bodies |
| `nexus/gateway/outbox_health.py` | `OutboxHealthService.snapshot()` — read-only outbox counts (J5) |
| `nexus/memory/checkpoint_health.py` | `CheckpointHealthService.snapshot()` — read-only stale-execution/checkpoint counts (J6) |

### Modified (additive only)
| File | Change |
|---|---|
| `nexus/core/types.py` | +4 `EventType`: `SCHEDULER_JOB_STARTED/COMPLETED/FAILED/SKIPPED` |
| `nexus/config.py` | +`SchedulingConfig` (toggles, cadences, feeds, thresholds, tz); attached to `NexusSettings` |
| `nexus/scheduling/__init__.py` | export `build_scheduler`, `APSchedulerAdapter`, `SchedulerPort` |
| `nexus/api.py` | start scheduler in lifespan after the existing loops; shut it down cleanly |

**No migration** was needed — J5/J6 read existing tables (`system_outbox`, `system_events`,
`workflow_checkpoints`, `executions`, `agent_steps`); metrics use the existing `record_metric` path.

## 3. Approved decisions — how each was honored

| AP-103A decision | Implementation |
|---|---|
| J5 Outbox Health = read-only, metrics+audit only | `OutboxHealthService.snapshot()` is SELECT-only; `run_outbox_health_job` records metrics + returns snapshot (no mutation/repair/retry). Test `test_outbox_health_service_snapshot_readonly` asserts row count unchanged. |
| J6 Checkpoint Health = read-only, metrics+audit only | `CheckpointHealthService.snapshot()` SELECT-only; no rewrite/cleanup. |
| J1 feeds = additive config | `SchedulingConfig.research_feeds: dict[str,str]`; job **skips** (audited) when empty. |
| 4 explicit scheduler events (no overloading) | Added the 4 `EventType` values; `run_scheduled_job` emits them with `component="scheduler"`, `enqueue_outbox=False` (audit-only, no outbound noise). |
| Cadences | research 2h, briefing 08:00 Asia/Kolkata (cron), approval 15m, metrics 5m, outbox 10m, checkpoint 30m — all defaults in `SchedulingConfig`; verified operationally (§5). |

## 4. Constraint compliance (AP-103 design constraints)

- **No service-boundary violations / no model access by scheduler:** jobs import services + `get_session` only — **never** `nexus.memory.models`. (Health *services* own model access.) Verified by inspection + the boundary-focused tests.
- **Services only / no business logic in jobs:** each job body opens a session, constructs a service, calls one method. Audit/timing is centralized in `run_scheduled_job`.
- **Replaceable / distributed-ready:** `SchedulerPort` Protocol; APScheduler is one adapter.
- **Failures auditable + isolated:** `run_scheduled_job` never raises; emits `SCHEDULER_JOB_FAILED` + metric; `max_instances=1`, `coalesce=True`, `misfire_grace_time=300`.
- **Restart-safe:** declarative re-registration each boot; idempotent jobs.

## 5. Operational verification (real event loop)

Started the scheduler on an asyncio loop; all six jobs registered with correct next-run times in
**Asia/Kolkata**:
```
approval_expiration_sweep    next=+15m
checkpoint_health            next=+30m
daily_briefing               next=next day 08:00:00+05:30   (cron, correct tz)
metrics_aggregation          next=+5m
outbox_health                next=+10m
research_collection          next=+2h
SCHEDULER SHUTDOWN OK
```
Confirms the scheduler **exists and is operational**, cadences match the approved decisions, and
start/stop are clean. (Full detail in `scheduler-operational-readiness.md`.)

## 6. TDD evidence

Red→green: new tests failed on missing `SchedulingConfig`/modules, then passed after
implementation. One failure during development was a **test seed** bug (`system_outbox.source_type`
NOT NULL), fixed in the test — not the implementation. (Detail in `scheduler-validation-report.md`.)

## 7. Verification gates

| Gate | Result |
|---|---|
| New scheduler tests | 17 passed |
| Full suite | **143 passed** (126 prior + 17), 0 regressions |
| ruff `nexus/ tests/` | All checks passed |
| mypy `nexus/ --ignore-missing-imports` | Success: no issues in 57 files |

## 8. Diff scope

New: 4 source modules + 1 test module. Modified: `core/types.py` (+6), `config.py` (+36),
`scheduling/__init__.py` (+8), `api.py` (+56 scheduler wiring). No migrations, no governance/runtime
changes, no documentation (README/STATUS/ROADMAP) changes (that is AP-104).

## 9. Deviations from the illustrative design

The design tree showed a `jobs/` package; implementation consolidated the six thin wrappers into a
single `nexus/scheduling/jobs.py` for a tighter diff (the tree was explicitly illustrative). No
functional difference.

## 10. Next

Proceed to AP-103C (validation report — included here) and AP-103D (operational readiness — included
here). Documentation alignment (README/STATUS/ROADMAP) remains AP-104.
