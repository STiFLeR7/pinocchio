# Scheduler Event Map (AP-103, design)

> How each scheduled job flows through services → events → outbox → audit log. Design only.
> Confirms constraint 9 (auditable) and that jobs never touch models directly (constraint 2).

---

## 1. Canonical flow

```
Scheduler trigger → Job wrapper → Service method → NexusEvent
       → EventGateway (in-process, ephemeral)         [optional, for live subscribers]
       → MemoryService.log_event → audit_log (durable, immutable)
       → enqueue_outbox → system_events / system_outbox  [only for delivered notifications]
       → existing outbox loops → Discord / Email
```

Audit is **always** the durable record; the EventGateway bus and outbox tables are involved only
where the underlying service already uses them.

## 2. Per-job event map

| Job | Service call | Events emitted (existing) | Outbox touched | Audit record(s) |
|---|---|---|---|---|
| J1 Research Collection | `ResearchService.execute_research_run` | `RESEARCH_STARTED`, `RESEARCH_COMPLETED`/`RESEARCH_FAILED` | none directly (research persists findings; no outbound msg) | engine audits `RESEARCH_*`; **+ scheduler job lifecycle** |
| J2 Daily Briefings | `BriefingService.generate_and_dispatch_briefing` | `REPORT_GENERATED`, `NOTIFICATION_SENT/FAILED` | `system_outbox` (discord/email) | engine audits report + notification; **+ scheduler job lifecycle** |
| J3 Approval Expiry | `ApprovalService.sweep_expired_approvals` | `APPROVAL_EXPIRED` (per expired) | `system_events` → Discord (via existing dispatch) | engine audits each expiry; **+ scheduler job lifecycle** |
| J4 Metrics Aggregation | `metrics.run_aggregation_and_retention` | none | none | **scheduler job lifecycle only** |
| J5 Outbox Health (read-only) | `OutboxHealthService.snapshot` (NEW) | none (or threshold-breach audit) | none | **scheduler job lifecycle + threshold-breach audit** |
| J6 Checkpoint Health (read-only) | `CheckpointHealthService.snapshot` (NEW) | none (or threshold-breach audit) | none | **scheduler job lifecycle + threshold-breach audit** |

## 3. Scheduler job-lifecycle audit (proposed, AP-103B)

Jobs are not currently representable by an existing `EventType`. Proposed **additive** enum values
(implementation-time, not now):

- `SCHEDULER_JOB_STARTED = "scheduler.job.started"`
- `SCHEDULER_JOB_COMPLETED = "scheduler.job.completed"`
- `SCHEDULER_JOB_FAILED = "scheduler.job.failed"`

Each audit record uses `component="scheduler"`, `entity_type="scheduler_job"`, `data={ job_id,
trigger, duration_ms, error? }`, written through `MemoryService.log_event(enqueue_outbox=False)`
(audit-only; job lifecycle is not a user notification). This keeps job observability fully in the
immutable `audit_log` without polluting outbound channels.

> If even additive enum values are considered out of scope at AP-103A, the fallback is to audit with
> an existing generic event and a `component="scheduler"` tag. Decision deferred to AP-103A.

## 4. Metrics emitted (existing `record_metric` mechanism)

Jobs emit operational metrics via the existing `nexus.core.metrics.record_metric` (no new
infrastructure):

| Metric | Source job |
|---|---|
| `scheduler_job_duration_ms{job}` | all jobs |
| `outbox_backlog`, `outbox_dead_letter` | J5 |
| `stale_executions`, `stale_checkpoints` | J6 |

These flow through the **existing** metrics flush/aggregation path (and become J4's input) — no new
pipeline.

## 5. Boundary assertions (verifiable at AP-103C)

- Jobs import from `nexus.scheduling`, `nexus.database` (`get_session`), and service modules only —
  **never** `nexus.memory.models`.
- All event emission happens **inside services**, not in job wrappers (jobs only add a
  failure-audit on exception via the scheduler wrapper).
- The EventGateway remains optional; durability is via `audit_log` + outbox tables, unchanged.
