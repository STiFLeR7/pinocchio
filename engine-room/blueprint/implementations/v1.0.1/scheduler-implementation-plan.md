# Scheduler Implementation Plan (AP-103 → AP-103A/B/C/D)

> The staged plan to take the Scheduler Foundation from design to operational verification.
> **AP-103 produces this plan only. No implementation occurs until AP-103A approval.**

---

## AP-103A — Architecture Approval (gate)

**Goal:** Owner reviews and approves the design + resolves open decisions. No code.

**Inputs:** `scheduler-design.md`, `scheduler-event-map.md`, `scheduler-failure-model.md`,
`scheduler-recovery-model.md`, `scheduler-readiness-review.md`, `ADR-scheduler-foundation.md`.

**Decisions required (from `scheduler-readiness-review.md §3`):**
1. **J5/J6 (Outbox/Checkpoint Health):** approve as read-only observability **or** defer.
2. **J1 research feeds:** approve an additive `scheduling.research.feeds` config source.
3. **Scheduler audit events:** approve additive `SCHEDULER_JOB_*` `EventType` values, or use the
   generic-audit fallback.
4. **Job set & cadences:** confirm the proposed frequencies (or amend).

**Exit criteria:** ADR marked **Accepted**; J5/J6 and feeds/enum decisions recorded. Without this,
AP-103B does not start.

---

## AP-103B — Implementation

**Goal:** Build the approved scheduler and jobs. Strict scope = approved design only.

**Work items (contingent on AP-103A):**
1. `nexus/scheduling/scheduler.py` — `SchedulerPort` Protocol + `APSchedulerAdapter`
   (AsyncIOScheduler, `coalesce=True`, `max_instances=1`, `misfire_grace_time`, error/missed
   listener → audit).
2. `nexus/scheduling/jobs/*.py` — thin wrappers for the **approved** jobs (J2–J4 minimum; J1 if
   feeds approved; J5/J6 if approved).
3. `nexus/api.py` lifespan — start scheduler after the existing loops; shut it down cleanly.
4. **Additive config** — `scheduling` section (per-job enable + cron/interval; `research.feeds`).
5. **Additive `EventType`** — `SCHEDULER_JOB_STARTED/COMPLETED/FAILED` (if approved).
6. **Thin read-only health services** (only if J5/J6 approved) — `OutboxHealthService.snapshot`,
   `CheckpointHealthService.snapshot` (read-only counts; no model access from the scheduler).

**Constraints carried forward:** no business logic in jobs; jobs invoke services only; no changes to
governance/health/expiry semantics; no auto-resume supervisor.

**Exit criteria:** scheduler starts in lifespan; approved jobs registered; ruff + mypy clean.

---

## AP-103C — Validation

**Goal:** Prove correctness under TDD before claiming done.

**Tests:**
- Job wrappers call the correct service method with a valid session and **import no models**
  (boundary assertion).
- Scheduler registers exactly the approved job set at startup.
- **Failure isolation:** a job raising does not crash the scheduler or other jobs; a
  `SCHEDULER_JOB_FAILED` audit is written.
- **Idempotency:** running J1/J2/J4 twice produces no duplicate findings/briefings/aggregates.
- **Restart re-registration:** re-creating the scheduler re-registers all jobs.
- **J5/J6 (if built):** snapshot methods are read-only and emit the expected metrics/threshold
  audits.
- Full regression suite + ruff + mypy remain green.

**Exit criteria:** all new tests pass; no regressions; evidence captured in an AP-103C report.

---

## AP-103D — Operational Verification

**Goal:** Observe the scheduler working in a running instance (local-first, ADR-011).

**Checks:**
- Start Nexus with owners configured (A-001 gate passes) and a real/temp DB.
- Confirm each approved job **fires on its trigger** (logs + `SCHEDULER_JOB_*` audit rows +
  `scheduler_job_duration_ms` metric).
- J2: a briefing is generated and dispatched via the outbox.
- J3: an overdue pending approval is expired (audit `APPROVAL_EXPIRED`).
- J4: `system_metrics_aggregates` rows appear; retention purge runs.
- J1 (if enabled): findings persisted from configured feeds.
- J5/J6 (if enabled): backlog/stale metrics recorded; threshold audit on induced backlog.

**Exit criteria:** documented operational run showing autonomous execution with full audit trail;
no false-unhealthy; no regressions.

---

## Sequencing & dependencies

```
AP-103 (design, done) → AP-103A (approve) → AP-103B (build) → AP-103C (validate) → AP-103D (verify)
```

- AP-103B blocked on AP-103A.
- J1 blocked on feeds-config decision; J5/J6 blocked on observability approval.
- Minimum viable scheduler if new code is declined: **J2 + J3 + J4** only.
