# Scheduler Validation

> v1.1.0 bring-up · APScheduler job execution + audit + metrics.

## Build
`build_scheduler(...)` constructs an `APSchedulerAdapter` with **6 jobs** (NOT auto-started in the
harness): `research_collection, daily_briefing, approval_expiration_sweep, metrics_aggregation,
outbox_health, checkpoint_health`.

## Live job execution (audited runner)
`run_scheduled_job(job_id, …)` executed against the live DB:

| Job | Ran | Audit |
|---|---|---|
| `outbox_health` (J5, read-only) | ✅ | started + completed |
| `checkpoint_health` (J6, read-only) | ✅ | started + completed |
| `metrics_aggregation` (J4) | ✅ | started + completed |
| `approval_expiration_sweep` (J3) | ✅ | started + completed |

**Audit evidence (immutable log):** `scheduler.job.started: 4`, `scheduler.job.completed: 4`.
**Metrics:** `scheduler_job_duration_ms` recorded; J5/J6 recorded `outbox_*` / `checkpoint_*` health
gauges. Failure isolation confirmed by design (`run_scheduled_job` never raises; failures audited as
`SCHEDULER_JOB_FAILED`).

## Verdict
Scheduler: **Pilot Ready** — jobs start, finish, audit, and record metrics with failure isolation.
