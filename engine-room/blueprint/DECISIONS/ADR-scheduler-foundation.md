# ADR — Scheduler Foundation

- **Status:** PROPOSED (pending AP-103A approval)
- **Date:** 2026-06-24
- **Release:** Nexus v1.0.1 "Alignment"
- **Action Point:** AP-103 (design)
- **Finding:** A-003 (Missing Scheduler Layer)
- **Decided By:** (owner approval required at AP-103A)
- **Supersedes / relates to:** ADR-001 (APScheduler named), ADR-009 (approval expiration cadence),
  ADR-010 (heartbeat cadence), ADR-011 (local-first), ADR-014 (service boundaries)

---

## Context

The Research, Briefing, Approval-expiration, and Metrics-aggregation capabilities exist as service
methods but have **no autonomous trigger** (AP-101 §A-003). `apscheduler` is an installed dependency
but unused; the `nexus/scheduling/` package contains only the event-driven `WorkflowOrchestrator`.
This leaves Nexus an *attended* console rather than the operational control plane its architecture
intends. v1.0.1 is a correctness/safety/operational-completeness release — the goal is to
**operationalize existing capabilities**, not add features.

## Decision

Adopt a **thin scheduler foundation** with these properties:

1. **APScheduler `AsyncIOScheduler`** as the engine, started/stopped in the FastAPI `lifespan`
   alongside the existing background loops.
2. A **`SchedulerPort` Protocol** abstraction with an `APSchedulerAdapter` implementation, so the
   engine is replaceable and a future distributed scheduler can be swapped in without touching jobs
   or services (constraints 4, 6).
3. **Thin job wrappers** (one per capability) that contain **no business logic**: they open a
   session and invoke an **existing service** only; failures are caught and audited (constraints
   2, 7, 8, 9).
4. **Idempotent, declarative jobs** re-registered at every startup using the in-process
   `MemoryJobStore`; correctness relies on each service's existing idempotency (dedup / content-hash
   / per-hour aggregation / read-only), making the scheduler restart-safe without a persistent
   jobstore in v1 (constraint 10).
5. **Audit + metrics** for every job run via the existing `MemoryService.log_event` (immutable
   `audit_log`, `component="scheduler"`) and `record_metric` — no new observability infrastructure.

### Scope of jobs
- **Ship as Existing Capabilities:** J2 Daily Briefings, J3 Approval Expiration Sweep, J4 Metrics
  Aggregation. (Zero new business code.)
- **Existing + small config dependency:** J1 Research Collection — requires an additive feed-config
  source.
- **New (read-only observability) — approve or defer at AP-103A:** J5 Outbox Health, J6 Checkpoint
  Health. These add only thin read-only query methods and emit metrics/audit; they change no
  behavior and add no user-facing feature.

## Alternatives considered

| Option | Rejected because |
|---|---|
| Keep ad-hoc `asyncio` poll loops (status quo) | No cron/calendar semantics, no misfire/coalesce, no per-job audit; doesn't satisfy A-003 |
| External scheduler/queue (Celery, Temporal, OS cron) | Violates local-first MVP (ADR-011); heavyweight; OS cron can't audit in-process or share the app's services/session — breaks constraints 1–3, 9 |
| Persistent `SQLAlchemyJobStore` now | Unnecessary given idempotency; adds SQLite write pressure (RISK-002) for no v1 benefit; kept as a documented future step |
| Business logic inside jobs | Violates constraints 7/8 and the service-boundary model (ADR-014) |

## Consequences

**Positive**
- Operationalizes four already-built engines → closes the largest intent/behavior gap.
- Replaceable + idempotent + auditable by construction; clean path to distributed scheduling.
- No governance/runtime/health behavior changes.

**Negative / costs**
- Adds the scheduler as another concurrent SQLite writer (mitigated by staggering, `busy_timeout`,
  idempotency; fully resolved only by the future PostgreSQL move).
- J5/J6 require a small amount of new read-only code (the only "no new features" tension — gated at
  AP-103A; deferrable).
- Job lifecycle auditing needs additive `EventType` values (or a generic-event fallback).

**Out of scope (explicit)**
- No generic auto-resume recovery supervisor (TD-22) — J6 only observes.
- No change to ADR-009 expiry semantics, governance, or execution.

## Validation

Defined in `scheduler-implementation-plan.md` (AP-103C/D): unit tests proving jobs invoke services
(not models), failure isolation, idempotency, and restart re-registration; operational verification
that each job fires and produces the expected audit/metric/side-effect.

## References

`../implementations/v1.0.1/scheduler-design.md`, `scheduler-event-map.md`,
`scheduler-failure-model.md`, `scheduler-recovery-model.md`, `scheduler-readiness-review.md`,
`scheduler-implementation-plan.md`.
