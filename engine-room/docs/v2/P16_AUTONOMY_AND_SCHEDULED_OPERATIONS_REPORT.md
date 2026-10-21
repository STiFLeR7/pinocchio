# P16 — Constitutional Autonomy & Scheduled Operations — Implementation Report

## Executive Summary

P16 introduces **governed autonomous execution** through **deterministic scheduling** — without adding any
new reasoning, planning, or execution ownership. One additive package (`nexus_scheduler`) plus three small,
passive seams complete the last operational surface: the platform can now begin executions on a schedule,
under Policy control, and run scheduled platform tasks.

- **`nexus_scheduler` — the Constitutional Scheduler.** The sole constitutional owner of execution
  *timing*. It registers durable schedules (one-time / delayed / immediate / interval / cron-like),
  detects which occurrences are due at an **injected clock** (never a wall clock), and dispatches each
  **exactly once** — a Goal through the Policy-mediated Autonomous Execution Coordinator (which drives the
  Constitutional Pipeline), a platform operation through the read-only Operations Plane. It manages the
  schedule lifecycle (cancel / pause / resume / expire / complete) and records durable `scheduler.*` facts.
  It owns *when* an execution begins and nothing else.

- **Governed autonomy.** A due Goal is dispatched in one of three Policy-mediated modes — **Manual**
  (queued for a human, never auto-run), **Governed** (auto-run; approval gates pause for a human via the
  Approval Exchange), **Fully Automatic** (auto-run *and* auto-approve gates — only when Policy permits,
  recording the Policy-delegated authorization exactly as a human one). A Policy **deny** withholds
  execution (fail-closed). Autonomy is *always* mediated by Policy; the Scheduler only requests execution.

- **Scheduled operations.** Platform tasks (health snapshot, diagnostics sweep, runtime-inventory refresh,
  replay verification) can be scheduled deterministically. They are not Goals and never enter the pipeline
  — they invoke the read-only Operations Plane.

**Result:** 30 new P16 tests (+3 new Policy-consumer guardrail parametrizations), all green. Full v2 sweep
**2 918 passed, 1 opt-in skip, 0 regressions** (the lone pre-existing error is `test_state_machines`'s
`db_session` fixture stripped by `--noconftest` — unrelated). mypy-strict clean across 309 source files;
ruff lint + format clean. One new single-owner event producer (`scheduler`); every event names exactly one
producer and every identifier is unique. **No ADR, frozen contract, invariant, or constitutional ownership
changed.**

---

## Constitutional Compliance

Proven structurally (import/AST guardrails) and behaviourally (integration tests).

| Requirement | How P16 honors it |
|---|---|
| **Scheduler owns timing only.** | It reaches no reasoning/execution engine (`test_scheduler_reaches_no_engine`), and its timing core is a pure function of injected time (`test_timing_core_is_a_pure_function_of_time`). It reasons/plans/executes/validates/recovers nothing — it decides *when*, then delegates. |
| **Policy owns governance (INV-28).** | Autonomy is decided by the Policy engine (sole evaluator). The Autonomous Execution Coordinator *submits* a `DecisionRequest` for a governed `autonomous_execution` action and reads the verdict — it constructs no verdict (`test_autonomy_delegates_to_policy_and_evaluates_none`; and `nexus_scheduler` is now in the platform Policy-consumer guardrail, proving it never references the closed verdict set). Autonomy stays fail-closed (INV-30): a deny withholds execution. |
| **Approval Exchange owns approvals.** | Gate decisions still flow through the P15 exchange. Governed runs *publish* pending approvals for a human; Fully-Automatic runs *approve* through the exchange (recorded `decided_by="policy-autonomy"`). The Scheduler owns no approval logic. |
| **Constitutional Pipeline owns execution coordination — no competing coordinator.** | A Goal reaches the platform only via `pipeline.run` (`test_scheduler_drives_execution_only_through_the_pipeline`). The Scheduler and autonomy coordinator sequence no stages; they invoke the one coordinator, exactly as Human Interaction and the Approval Exchange do. |
| **Operations owns observation.** | Scheduled platform tasks invoke only the read-only Operations Plane; the durable `operations.snapshot` stays Operations-owned. The Scheduler records only that the task ran. |
| **Single producer per event (INV-02).** | `scheduler.*` ⇒ producer `scheduler` (`test_scheduler_events_are_owned_by_one_producer`). Verified in a full run: every `scheduler.*` fact carries that producer and all identifiers are unique. |
| **No new frozen domain object (INV-07).** | `Schedule` is a `ValueObject` projection of the log; triggers/outcomes/health are frozen dataclasses. Guardrails assert no `DomainObject` subclass. |
| **Log is truth; replay/restart (INV-13/14/18).** | Every schedule fact is durable and content-addressed; occurrence timing is deterministic from injected time; due-detection skips already-fired occurrences reconstructed from the log — so a restart never double-dispatches. |
| **No wall-clock non-determinism.** | The Scheduler is driven by an injected `now` (an ISO-8601 string); `datetime.fromisoformat` + `timedelta` do the arithmetic on given data only. Same ticks → same dispatches. |

No architectural conflict was found; implementation evidence is consistent with the Constitution, ADRs,
frozen contracts, and invariants.

**Additive, non-ownership seams (all preserve contracts):**
- `nexus_workflows.spine`: `dump_spine_request` / `load_spine_request` (the spine owns `SpineRequest`, so it owns its durable form) and a `SpineControl.granted_gates`-style read — plus exposing the pipeline's own `PolicyContext` on `SpinePipelineContext` so the Scheduler reuses the one Policy configuration.
- `nexus_policy`: a data-only `autonomous_execution_baseline()` allow-baseline + action-class constant, alongside `v1_seed_policies` / `knowledge_grounding_baseline` (governance owner; additive configuration the coordinator *registers* and *queries*, never evaluates).

---

## Scheduler Architecture

**Package `nexus_scheduler`** (`events`, `model`, `timing`, `registry`, `autonomy`, `scheduled_operations`,
`dispatcher`, `scheduler`, `observability`, `composition`).

**Schedule kinds (deterministic occurrences from injected time):**

| Kind | Occurrence(s) |
|---|---|
| `IMMEDIATE` | one, at the anchor (registration time) |
| `ONE_TIME` | one, at `run_at` |
| `DELAYED` | one, at `anchor + delay_seconds` |
| `INTERVAL` | recurring at `anchor + k·interval_seconds` |
| `CRON` | recurring at a cron alias cadence (`@minutely`/`@hourly`/`@daily`/`@weekly` → a fixed interval) |

Occurrence indices are **stable** (0-based from the anchor) — the index is what keys a dispatch on the log
and prevents duplicate dispatch. `timing.py` is pure occurrence math with a `SAFETY_CAP` backstop (no silent
unbounded loop). Recurring schedules honor `max_occurrences` and `expires_at`.

**The tick (due-detection + dispatch).** `tick(now)` reconstructs every schedule from the log; for each
*active* schedule it computes due occurrences (`≤ now`), skips those already fired (reconstructed from the
durable `scheduler.dispatched` / `_denied` / `_requested` / `operation_ran` facts — the idempotency guard),
dispatches the rest through the **Dispatcher** (Goal → autonomy coordinator; operation → Scheduled
Operations), records the outcome, and marks the schedule `COMPLETED` when exhausted. The tick is driven by
an injected `now`, so a real scheduler process calls it on a cadence while tests call it with fixed
timestamps.

**Lifecycle.** `cancel` / `pause` / `resume` / `expire` are durable transitions; a paused schedule fires no
occurrences until resumed (none are lost), and a resumed schedule fires the occurrences that came due while
it was paused.

**Durable state & the Goal request.** All state is `scheduler.*` facts. The Goal to run is serialized onto
the `scheduler.registered` fact (`dump_spine_request`) and reloaded per occurrence with a per-occurrence
identity (`{schedule_id}-{k}`) — so each occurrence is its own pipeline session and re-running one is
idempotent at the event level.

---

## Autonomous Execution

The **Autonomous Execution Coordinator** (`autonomy.py`) is the one component that turns a due Goal into an
execution, always through Policy:

1. **Consult Policy** — `policy.simulate(DecisionRequest(action_class="autonomous_execution", attributes={mode, schedule}, governed=True))`.
2. **Manual** → record a request a human must run (never auto-run).
3. **Deny** → withhold execution (`scheduler.dispatch_denied`), fail-closed.
4. **Governed** (allowed) → `pipeline.run`; publish any approval gates for a human (they pause) — the run
   is `paused` until the operator approves through the Approval Exchange.
5. **Fully Automatic** (allowed) → `pipeline.run`; auto-approve each gate through the Approval Exchange
   (`decided_by="policy-autonomy"`) — the run completes autonomously.

Every autonomous decision carries **provenance**: the `scheduler.dispatched` fact records the mode, the
policy decision + reasoning, whether it executed, the pipeline status, the resulting session id, and any
auto-granted gates. The coordinator plans/executes/validates/recovers nothing and evaluates no policy — it
requests execution and records what the owners returned.

---

## Policy Integration

Autonomy is a new **governed action class** `autonomous_execution`, permitted by an overridable
allow-baseline (`autonomous_execution_baseline`, registered on the pipeline's own Policy registry at
wiring). Operators withhold autonomy — globally, per mode, per schedule, or per domain — by registering a
higher-specificity **deny** policy; the coordinator then records a denied dispatch and runs nothing
(`test_policy_deny_withholds_execution`). This mirrors the P14 `knowledge_grounding` baseline: a data-only
governance default the consumer registers and queries, evaluated **only** by the Policy engine (INV-28),
fail-closed by construction (INV-30). Fully-Automatic auto-approval is itself Policy-gated — the coordinator
auto-approves gates only on a permitting verdict, so "unattended" execution is never ungoverned.

---

## Replay Validation

Replay is exact because scheduling is a pure projection of content-addressed `scheduler.*` facts over
injected time.

- `test_replay_reconstructs_scheduling_history` — a durable recurring run is reconstructed from a
  **reopened** database: the schedule's fired occurrences are identically `(0, 1, 2)` and its status is the
  same terminal `COMPLETED`.
- `test_spine_request_round_trips_through_a_json_payload` — the persisted Goal request round-trips exactly,
  so a replayed schedule dispatches the identical Goal.
- Determinism holds end to end: the same schedules + the same tick sequence reproduce the same dispatches.

---

## Restart Validation

Restart resumes schedules **without duplication** (INV-18).

- `test_restart_never_double_dispatches` — **Process 1** registers a one-time schedule over a durable file
  and ticks (the Goal runs). **Process 2**, a fresh Scheduler over the reopened file, re-detects the
  occurrence as already fired and dispatches nothing — and the Goal's pipeline session shows exactly **one**
  `pipeline.completed` across the restart.
- The guard is structural: due-detection subtracts the fired-occurrence set reconstructed from the log
  before dispatching, and each occurrence maps to a deterministic pipeline session whose events are
  idempotent — double protection against re-execution.

---

## Operational Readiness

The platform can now be operated autonomously under governance:

- **Deterministic scheduling** — one-time / recurring / delayed / immediate / cron-like, all demonstrated
  (`test_one_time_recurring_and_delayed_execution`, `test_recurring_dispatches_every_due_occurrence`).
- **Governed autonomy** — Manual / Governed / Fully-Automatic and Policy-deny, all demonstrated
  (`test_autonomy.py`, `test_policy_controlled_auto_approval`,
  `test_approval_required_execution_is_surfaced_then_completed`).
- **Scheduled operations** — a scheduled health snapshot runs against the live platform and Operations
  records the durable snapshot (`test_scheduled_operation_execution`).
- **Observability** — read-only `schedules` / `active` / `paused` / `completed` / `upcoming` / `health`
  views plus `scheduler.*` counters over the P1 sink; autonomous-execution provenance is on the durable
  `scheduler.dispatched` facts (queryable via Operations `event_lookup`).
- **CI** — `nexus_scheduler` added to the mypy-strict target and the wheel `packages` list; the platform
  Policy-consumer guardrail extended to `nexus_approval` / `nexus_operations` / `nexus_scheduler`.

---

## Remaining Platform Gaps

1. **The tick is externally driven.** The Scheduler is deterministic by design (injected `now`); it does
   not embed a live timer. A host process (or a future scheduled-operations loop) must call `tick(now)` on a
   cadence. This is intentional — no wall clock in the core — and a thin edge-adapter is a future add.
2. **Cron is alias-level.** `CRON` supports `@minutely`/`@hourly`/`@daily`/`@weekly` (mapped to fixed
   intervals with an anchor); full crontab-field expressions are a future extension. Interval + anchor
   already covers most real cadences deterministically.
3. **Autonomy attributes are coarse.** Policy governs autonomy on `{mode, schedule}`; richer attributes
   (domain, cost ceiling, concurrency budget) would let operators write finer autonomy policies — additive,
   no ownership change.
4. **Denied/expired occurrences are terminal, not retried.** A policy-denied occurrence is recorded and not
   re-attempted on later ticks (a decision, not a transient failure); a changed policy affects only future
   occurrences. This keeps replay/restart deterministic.

---

## Recommendation for P17

**P17 — Constitutional Concurrency & Resource Governance.** With timing, autonomy, approvals, and
observation in place, the next seam is *how much* runs at once under governance:

1. **Concurrency control** — a governed limit on simultaneous autonomous executions (per domain / runtime /
   global), enforced where the Scheduler dispatches, so a burst of due occurrences is admitted under a
   Policy-set budget rather than all at once. Deterministic (occurrences queue in index order), fail-closed,
   and owned by Policy — the Scheduler only asks.
2. **Resource governance** — bind execution admission to the existing Resource model (doc 22), so the
   platform can defer or shed load under contention. This is the natural progression from "when may it run"
   (P16) to "how many may run, given resources" — and, as ever, it changes no ownership: Policy governs,
   the pipeline coordinates, the Scheduler times.

---

### Rules honored

Preserved the Constitution, all ADRs, all invariants, and every frozen contract. No architectural redesign,
no protocol change, no hidden coupling — the new package is additive and one-way dependent
(`nexus_scheduler → {nexus_workflows.spine, nexus_approval, nexus_operations, nexus_policy, nexus_core,
nexus_infra}`), and the pipeline/Policy seams are passive, additive configuration. **No commit was made** —
awaiting explicit instruction.
