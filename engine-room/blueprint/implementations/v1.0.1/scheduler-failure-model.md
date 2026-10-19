# Scheduler Failure Model (AP-103, design)

> Failure taxonomy, isolation guarantees, and auditability for the scheduler. Design only.
> Satisfies constraints 9 (auditable) and supports 10 (restart-safe). Pairs with
> `scheduler-recovery-model.md`.

---

## 1. Failure domains

| Domain | Examples | Containment |
|---|---|---|
| **Trigger-level** | scheduler not started; clock skew; missed fire during downtime | APScheduler `coalesce=True` + `misfire_grace_time`; re-registration at boot |
| **Job-wrapper-level** | session open fails; service constructor error | per-job `try/except` → audit `SCHEDULER_JOB_FAILED` + metric; job ends, scheduler unaffected |
| **Service-level** | DB locked; LLM failure; feed fetch error; delivery failure | handled inside the existing service (its own retry/dedup/outbox); surfaces as job success-with-degradation or exception |
| **Engine-level** | scheduler thread/loop dies | `EVENT_JOB_ERROR`/`EVENT_JOB_MISSED` listener audits; lifespan owns scheduler start/stop |

## 2. Isolation guarantees (no cross-job blast radius)

- **`max_instances=1` per job** — a slow/overrunning run never overlaps itself (prevents the
  duplicate-run / contention class).
- **One job's exception never aborts another** — APScheduler runs jobs independently; each wrapper
  catches its own exceptions.
- **A failing job never crashes the application** — the scheduler runs in the lifespan; an
  unhandled job error is caught by the engine error listener and audited, not propagated.
- **No partial-commit corruption** — jobs use `get_session` (commit on success / rollback on
  exception, `database.py:152-192`), so a mid-job failure rolls back cleanly.

## 3. Per-job failure behavior

| Job | Primary failure | Behavior | Auditable? |
|---|---|---|---|
| J1 Research | feed/LLM/DB error | per-feed & per-finding handled in engine; checkpointed; job audits wrapper-level failure | yes (`RESEARCH_FAILED` + job audit) |
| J2 Briefing | aggregation/delivery error | delivery retried by comm-outbox; generation error → job audit | yes (`NOTIFICATION_FAILED` + job audit) |
| J3 Approval expiry | DB locked | job audits failure; next interval retries (idempotent) | yes |
| J4 Metrics aggregation | DB locked | job audits failure; next hour retries (per-hour dedup) | yes |
| J5 Outbox health | DB locked (read) | job audits failure; read-only, no side effects | yes |
| J6 Checkpoint health | DB locked (read) | job audits failure; read-only, no side effects | yes |

## 4. Auditability contract (constraint 9)

Every job run produces a durable trail:
1. `SCHEDULER_JOB_STARTED` (audit-only) at entry.
2. On success: `SCHEDULER_JOB_COMPLETED` + `scheduler_job_duration_ms` metric.
3. On failure: `SCHEDULER_JOB_FAILED` with `error` payload + metric; **plus** the engine-level
   `EVENT_JOB_ERROR` listener writes a backstop audit if the wrapper itself failed.

All via `MemoryService.log_event(..., enqueue_outbox=False)` with `component="scheduler"`.

## 5. Health interaction (no false-unhealthy)

Scheduler/job failures **do not** flip the global `health` flag (which gates execution) — a failed
briefing must not block governed execution. Instead, repeated failures are observable via audit +
metrics (and J5/J6 thresholds). This keeps the existing health semantics (`core/health.py`)
unchanged (constraint: no behavior change to governance/health).

## 6. DB-contention strategy (SQLite single-writer)

Jobs run inside the same process as the existing outbox/metrics loops against one SQLite file. To
avoid amplifying the contention risk (audit RISK-002):
- `misfire_grace_time` + `coalesce` absorb brief lock waits.
- `busy_timeout=5000` (existing pragma) covers transient locks; a job that still hits a lock simply
  fails its run and retries next interval (idempotency guarantees correctness).
- Job intervals are staggered (e.g. health at :00/:05, metrics at :00, briefing at a fixed hour) to
  reduce simultaneous writers — a scheduling concern, not a code change.
