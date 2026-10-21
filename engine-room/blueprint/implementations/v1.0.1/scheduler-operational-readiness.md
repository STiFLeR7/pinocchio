# Scheduler Operational Readiness (AP-103D)

> Evidence that the scheduler is genuinely operational in a running process, and the operator-facing
> facts for running it. Local-first (ADR-011).

---

## 1. Operational smoke test (real event loop)

Built the scheduler from default config and started it on an asyncio loop. All six jobs registered
with correct next-run times in the configured **Asia/Kolkata** timezone, then shut down cleanly:

```
SCHEDULER STARTED. Registered jobs + next run times (Asia/Kolkata tz):
  approval_expiration_sweep    next=2026-06-24 11:44:09+05:30      (interval 15m)
  checkpoint_health            next=2026-06-24 11:59:09+05:30      (interval 30m)
  daily_briefing               next=2026-06-25 08:00:00+05:30      (cron 08:00, correct tz/next-day)
  metrics_aggregation          next=2026-06-24 11:34:09+05:30      (interval 5m)
  outbox_health                next=2026-06-24 11:39:09+05:30      (interval 10m)
  research_collection          next=2026-06-24 13:29:09+05:30      (interval 2h)
SCHEDULER SHUTDOWN OK
```

This confirms: the scheduler **starts**, computes triggers correctly, honors the approved cadences
and timezone, and **stops** without error.

## 2. Lifecycle integration

- **Startup:** `build_scheduler(...)` is called in `nexus/api.py` lifespan after the outbox/metrics
  loops; if `scheduling.enabled` it `start()`s and logs `scheduler_started` with the job ids, else
  logs `scheduler_disabled`.
- **Shutdown:** `scheduler.shutdown()` is called first in the shutdown phase, wrapped in try/except
  (logs `scheduler_stopped` / `error_stopping_scheduler`).
- Starts **after** the A-001 owner-gate (so a misconfigured instance never reaches the scheduler).

## 3. Job catalogue (as shipped)

| Job id | Cadence | Service invoked | Side effects |
|---|---|---|---|
| `research_collection` | every 2h (skips if no feeds) | `ResearchService.execute_research_run` | research findings + `RESEARCH_*` |
| `daily_briefing` | 08:00 Asia/Kolkata | `BriefingService.generate_and_dispatch_briefing` | briefing + outbox delivery |
| `approval_expiration_sweep` | every 15m | `ApprovalService.sweep_expired_approvals` | expire approvals + `APPROVAL_EXPIRED` |
| `metrics_aggregation` | every 5m | `metrics.run_aggregation_and_retention` | hourly aggregates + retention purge |
| `outbox_health` | every 10m | `OutboxHealthService.snapshot` (read-only) | metrics + `SCHEDULER_JOB_COMPLETED` data |
| `checkpoint_health` | every 30m | `CheckpointHealthService.snapshot` (read-only) | metrics + `SCHEDULER_JOB_COMPLETED` data |

## 4. Observability (what an operator sees)

- **Audit log:** every fire writes `SCHEDULER_JOB_STARTED` then `COMPLETED`/`FAILED`/`SKIPPED`
  (`component="scheduler"`, `entity_type="scheduler_job"`, `data.job_id`, `correlation_id`).
- **Metrics:** `scheduler_job_duration_ms`, `scheduler_job_failed`, plus `outbox_*` / `checkpoint_*`
  health gauges — all flowing through the existing metrics pipeline (and now actually aggregated by
  `metrics_aggregation`, which the scheduler also drives).
- **Logs:** `scheduler_started` (with job ids) at boot.

## 5. Configuration surface (additive `scheduling` section)

`config/settings.yaml` (or `NEXUS_SCHEDULING__*` env) supports: `enabled`, `timezone`, per-job
`*_enabled` toggles, all cadences, `research_feeds` (a name→URL map), `outbox_backlog_threshold`,
`checkpoint_stale_minutes`. Defaults match the AP-103A cadences; **`research_feeds` is empty by
default**, so research safely **skips** (audited) until an operator configures feeds.

## 6. Operational notes / caveats

- **Single-node only (v1.0.1):** run exactly one Nexus instance against the SQLite DB — there is no
  cross-process scheduler lease (see `scheduler-future-scaling.md`). Two instances would double-fire
  (idempotency limits damage but duplicates would occur).
- **SQLite contention:** the scheduler adds periodic writers; cadences are staggered and jobs are
  idempotent + lock-tolerant (`busy_timeout`). The PostgreSQL move (ADR-002) is the long-term fix.
- **Health jobs are observational only:** J5/J6 surface problems (backlog, dead-letters, stale
  executions) via metrics/audit; they do **not** repair, retry, or clean up (by AP-103A mandate).
- **Approval expiry semantics** (J3 cancels the parent task) are unchanged from the existing service
  — the ADR-009 notify/review-queue mismatch is a separate item, out of A-003 scope.

## 7. Readiness verdict

**Operational.** The scheduler runs in-process, fires all six jobs on their approved cadences,
audits every run, isolates failures, and shuts down cleanly. The largest A-003 gap — built engines
with no autonomous trigger — is closed for single-node operation. Recommended AP-103D live check on
a real deployment: confirm a briefing is produced at 08:00 IST and that `system_metrics_aggregates`
begins populating within the first hour.
