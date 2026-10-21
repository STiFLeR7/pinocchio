# P15 — Constitutional Approval Exchange & Operations Plane — Implementation Report

## Executive Summary

P15 operationalizes the constitutional platform without adding any new reasoning, planning, or execution
ownership. It closes the governance loop around approval-gated execution and gives operators a durable,
read-only view of the platform. Two additive packages were introduced, and the constitutional pipeline was
given one small, passive seam:

- **`nexus_approval` — the Constitutional Approval Exchange.** The sole constitutional owner of approval
  *coordination*. Execution Actuation already pauses at an approval boundary (a gated node left `WAITING`);
  the exchange completes the exchange — it **publishes** the approval request, **awaits** the operator
  decision, **records** it as immutable audit (durable `approval.*` facts), **resumes** execution on
  approval by re-driving the pipeline with the now-granted gate, **denies** execution, and **expires**
  stale approvals. It owns exactly the deterministic lifecycle `Requested → Pending → Approved | Denied |
  Expired` and nothing else.

- **`nexus_operations` — the Constitutional Operations Plane.** The sole constitutional owner of platform
  *observation* for operators. A read-only surface over the one shared log: active sessions, pipeline /
  execution status, the approval queue, runtime / replay / restart inventories, deterministic diagnostics,
  and a platform health summary (recordable as a durable `operations.snapshot`). It observes; it controls
  nothing.

The approval surface is exposed **through Human Interaction only** (the façade gained `pending_approvals`
/ `approve` / `deny` / `approval_explanation` / `approval_history`, each delegating to the exchange and
never bypassing it). The Constitutional Pipeline remains the only execution coordinator; the Approval
Exchange integrates *through* it, Actuation, and Human Interaction — there is no competing coordinator.

**Result:** 32 new tests (approval: 12 unit + 5 integration; operations: 13 unit + 2 integration),
all green. Full v2 sweep **2 885 passed, 1 opt-in skip, 0 regressions** (the lone pre-existing error is
`tests/integration/test_state_machines.py`'s `db_session` fixture, stripped by `--noconftest` — unrelated).
mypy-strict clean across 297 source files; ruff lint + format clean. Two new single-owner event producers
(`approval_exchange`, `operations`); every event still names exactly one producer and every identifier is
unique. No ADR, frozen contract, invariant, or constitutional ownership changed.

---

## Constitutional Compliance

The program's guardrails are proven structurally (import/AST guardrail tests) and behaviourally
(integration tests).

| Requirement | How P15 honors it |
|---|---|
| **Policy remains sole policy owner (INV-28).** | The exchange evaluates **no** policy. *Whether* a node needs approval and its taxonomy is the `ExecutionStrategy`'s `approval_policy` — authored by Planning/Engineering-Intelligence and owned by Policy. `test_exchange_evaluates_no_policy_and_executes_nothing` asserts `exchange.py` contains no `.evaluate(` / `.simulate(` / `PolicyDecision`; `test_exchange_imports_no_engine` asserts it imports `nexus_policy` never. |
| **Governance remains sole governance owner (INV-29).** | The exchange records the operator's authorization as *immutable audit* (durable `approval.*` log events) — exactly Governance's "returns decisions and writes immutable audit as log events." It executes/plans/validates nothing. |
| **Execution Actuation owns traversal only (INV-23).** | The exchange never drives a runtime. On approval it hands *resumption* to the pipeline, which drives Actuation; Actuation still owns the pause/resume. The only pipeline seam is a passive `granted_gates` input Actuation already supported. |
| **Human Interaction owns presentation only.** | The façade's approval methods delegate 1:1 to the exchange and hold no lifecycle logic. HI records **no** `approval.*` fact (single ownership). `test_facade_invokes_only_the_pipeline_no_engine` still holds (the façade imports `nexus_workflows.spine` + `nexus_approval`, no engine). |
| **Operations owns observation only.** | Every Operations method is a read-only projection of the log. `test_operations_controls_nothing` asserts the package source contains no `.run(` / `.approve(` / `.deny(` / `.expire(` / `.actuate(` / `.publish(`. It produces no Supervision `Observation` domain object — INV-11 stays with Supervision; the `operations.snapshot` is operator instrumentation. |
| **Approval Exchange owns approval coordination only.** | It never evaluates policy, executes, plans, reasons, validates, or recovers (guardrail + `test_exchange_imports_no_engine`). Its single sanctioned collaborator is the Constitutional Pipeline. |
| **No competing coordinator.** | The pipeline stays the sole execution driver. The exchange invokes `pipeline.run` to resume (same sanctioned entry point Human Interaction uses); it re-implements no stage sequencing. |
| **Single producer per event (INV-02).** | `approval.*` ⇒ producer `approval_exchange`; `operations.*` ⇒ producer `operations`. Verified: in a full run every `approval.*`/`operations.*` event carries exactly that producer and all identifiers are unique. |
| **No new frozen domain object (INV-07).** | `ApprovalSession` / `ApprovalRequest` are `ValueObject` projections of the log; all Operations views are frozen dataclasses. Guardrails assert no `DomainObject` subclass in either package. |
| **Log is truth; replay/restart (INV-13/14/18).** | All lifecycle transitions are durable `approval.*` facts with content-addressed ids and injected timestamps; the approval session is a pure projection. Restart resumes from the log, never from the Goal. |

No architectural conflict was discovered; implementation evidence is consistent with the Constitution,
ADRs, frozen contracts, and invariants.

---

## Approval Exchange Architecture

**Package `nexus_approval`** (`events`, `model`, `session`, `exchange`, `observability`, `composition`).

**The gate.** Planning already records approval gates: a `WorkItemSpec` requiring approval becomes a graph
`approval_gates` entry + a node `Constraint(kind="approval")`, and the `ExecutionStrategy` carries the
`approval_policy` taxonomy (Policy/EI's call). When Actuation reaches such a gate it leaves the node
`WAITING` and emits `execution.approval_waiting`.

**The pipeline seam (additive, passive).** Two minimal changes let the pipeline *pause* at that boundary
and *resume* through it without owning approval logic:

1. `SpineControl.granted_gates: tuple[str, ...] = ()` — the approved gate node ids, forwarded to
   Actuation's pre-existing `ActuationInputs.granted_gates` input. The pipeline decides nothing; it relays.
2. `_stage_actuation` treats an actuation that is `BLOCKED` **with nodes still `WAITING`** as a resumable
   *approval pause* (distinct from a failure-block, which still flows to Validation). This is the P15
   approval boundary; Actuation still owns the pause/resume.

**Lifecycle (deterministic, every transition durable):**

```
                 publish()            approve()  → approval.approved  → resume pipeline (granted_gates)
execution.        ┌────────┐          deny()     → approval.denied    → gate not authorized
approval_waiting → │Requested│→Pending ┤
   (Actuation)    └────────┘          expire()/  → approval.expired   → gate not authorized
                                       sweep_expired(now ≥ expires_at)
```

- **`publish(session_id, waiting)`** — for each waiting gate not yet published, emits `approval.requested`
  then `approval.pending` (idempotent; a gate already in the lifecycle is skipped). The waiting gates come
  from the paused run's `ExecutionState.waiting_nodes` (graph node ids). Human Interaction calls this after
  every submit/restart, so a pause surfaces automatically.
- **`approve(request, node)`** — records `approval.approved`, reconstructs all approved gates from the log,
  and re-drives `pipeline.run(request, control=SpineControl(granted_gates=…))`. Actuation reconstructs the
  already-completed nodes (idempotent, INV-16), grants the node, drives it, and the pipeline flows on to
  Validation → … → Knowledge.
- **`deny(session_id, node)`** — records `approval.denied`; execution does **not** resume for the gate.
- **`expire(session_id, node)` / `sweep_expired(now)`** — records `approval.expired`; ISO-8601 deadlines
  are order-preserving, so `sweep_expired` expires every pending request with `now ≥ expires_at`.
- **`session` / `pending` / `history` / `explanation`** — read-only projections of `approval.*`.

**Persistence.** No new store: the approval requests, decisions, and expirations are durable `approval.*`
events on the one shared log (ADR-007), reconstructed by `reconstruct_approval_session` (last lifecycle
fact per gate wins). Timestamps are read from the event, never embedded in the payload, so identical
decisions are idempotent (INV-16).

**Human-Interaction surface.** `pending_approvals`, `approve`, `deny`, `approval_explanation`,
`approval_history` — each delegates to the exchange. The façade never bypasses it and records no approval
fact of its own.

---

## Operations Plane Architecture

**Package `nexus_operations`** (`events`, `model`, `service`, `diagnostics`, `health`, `observability`,
`composition`). Every service is a deterministic, read-only projection of the shared log, reached only
through the pipeline's read-only inspection surface and the exchange's read-only surface — no engine import,
no execution/approval control.

- **`OperationsService`** — `active_sessions`, `session_lookup`, `pipeline_lookup`, `execution_lookup`
  (traversal completion + waiting gates), `approval_queue` (cross-session pending + depth),
  `runtime_inventory` (distinct runtimes + utilization, derived structurally from node-dispatch facts),
  `runtime_lookup` (per-session assignments by correlation), `replay_inventory`, `restart_inventory`
  (paused/resumable sessions + pending depth), and `event_lookup` (filter the log by producer/type/session).
- **`DiagnosticsService`** — `diagnostics()`: event counts by producer and by type, plus a structural
  consistency verdict (every event names a producer; identifiers are unique). Pure function of the log.
- **`HealthInspector`** — `summary()`: liveness + operational counters (pending / completed approvals,
  queue depth, active sessions, pipeline states, runtime utilization, policy-decision count) with a verdict;
  `record_snapshot()` persists it as a durable `operations.snapshot`; `snapshots()` reconstructs them.

**Non-control.** Operations produces one durable fact — the `operations.snapshot` instrumentation — and
mutates nothing else. It creates no Supervision `Observation` (INV-11) and never calls `run`/`approve`/
`actuate` (guardrail-enforced).

---

## Replay Validation

Replay is exact because every approval transition is a content-addressed `approval.*` fact with an injected
timestamp; the approval session is a pure projection.

- `test_replay_reconstructs_identical_approval_history` — a durable submit → approve is reconstructed from a
  **reopened** database: `granted_gates == ("node-review",)`, state `APPROVED`, `decided_by`/`reason`
  preserved.
- `test_approval_history_is_deterministic_and_single_producer` — the full `approval.*` stream (identifier,
  type, payload) is **byte-identical** across two independent runs on fresh infrastructure.
- `test_operations_snapshot_is_durable_and_diagnostics_survive_replay` — a fresh Operations plane over the
  reopened file reconstructs the recorded snapshot and identical diagnostics.

---

## Restart Validation

Restart resumes an in-flight approval wait correctly, never replaying completed constitutional stages
(INV-18).

- `test_restart_resumes_an_in_flight_approval_wait` — **Process 1** submits a gated request over a durable
  file; the pipeline pauses at the approval boundary (durably). **Process 2**, a fresh surface over the
  reopened file, still sees the pending wait (`pending_approvals == ["node-review"]`), approves, and the
  pipeline resumes to `completed` — reconstructing Intent/Engineering/Context/Planning/Actuation-so-far
  from the log rather than re-running them.
- `deny` leaves the session paused with the gate denied (the gated node never executes) —
  `test_deny_blocks_the_gated_work`.

---

## Diagnostics

`DiagnosticsService.diagnostics()` yields, deterministically for a given log: `total_events`, counts
`by_producer` and `by_type`, a `consistent` verdict, and any `issues`. It flags two structural breaches —
an event without a producer (INV-02) and a duplicated identifier (INV-13). `HealthInspector.summary()`
derives liveness (`healthy` while the log is consistent) plus the operational counters, and records a
durable snapshot. `test_diagnostics_are_consistent_and_count_the_log` and the health tests confirm
correctness over real runs (including a paused approval and its resolution).

---

## Operational Readiness

The platform is now operator-drivable end to end through one façade, with a governed approval loop and a
read-only operations view:

- **Approval pause / grant / deny / expire** — demonstrated (`test_pause_grant_resume_through_the_operator_surface`,
  `test_deny_blocks_the_gated_work`, `test_expiry_is_a_durable_terminal_transition`).
- **Replay / restart** — demonstrated (above).
- **Operations visibility** — `test_operations_sees_the_pause_then_the_resolution`: the queue, restart
  inventory, and health reflect a pause and then its resolution.
- **Diagnostics correctness** — consistent counts + verdict over the shared log.
- **Instrumentation** — additive `approval.*` (4 counters) and `operations.*` (2 counters) over the P1 sink;
  the durable `operations.snapshot` gives a persisted operational view.
- **CI** — `nexus_approval` and `nexus_operations` added to the mypy-strict target (consistent with P14,
  which added `nexus_human_interaction`); all three packages registered in the wheel `packages` list
  (`nexus_human_interaction` had been omitted — corrected here). Ruff lint/format clean.

---

## Remaining Gaps

1. **Deadline scheduling is caller-driven.** Expiry is deterministic (`expire` / `sweep_expired(now)` over
   an ISO-8601 `expires_at`) but there is no autonomous timer — a scheduler/operator must call the sweep.
   This is intentional (no wall-clock non-determinism in the platform); a scheduled sweep is a thin future
   add.
2. **Multi-session taxonomy label.** The exchange derives the explanation taxonomy from the first plan on
   the log (`find_plan`); with many sessions on one log the *label* is best-effort (the *gating* is always
   exact, from the graph). Single-session-per-infrastructure is the platform norm.
3. **Operations health verdict is structural.** Liveness reflects log consistency + counters; it does not
   yet consume Supervision health (INV-11/23) — deliberately, to avoid duplicating Supervision. A future
   plane could surface Supervision's Observations read-only.
4. **Approval surface scope.** The façade exposes pending/approve/deny/explanation/history (per the program);
   `expire`/`sweep` are exchange/system operations, not operator-facing, by design.

---

## Recommendation for P16

**P16 — Constitutional Autonomy & Scheduled Operations.** With the approval loop and operations plane in
place, the next seam is bounded autonomy over the same governed surfaces:

1. **Scheduled operations** — a deterministic, log-driven scheduler that drives `sweep_expired` and records
   periodic `operations.snapshot`s from an injected clock, turning today's caller-driven sweeps into a
   governed cadence (still no wall-clock in the core; the clock is injected at the edge).
2. **Bounded autonomy** — an approval *policy delegation* whereby Policy may pre-authorize classes of gates
   (auto-grant under explicit, explainable, fail-closed rules), with the Approval Exchange recording the
   delegated authorization exactly as it records a human one. This is the first safe step from
   approval-gated execution toward governed autonomous execution, and it changes no ownership — Policy still
   decides, the exchange still coordinates, Actuation still traverses.

---

### Rules honored

Preserved the Constitution, all ADRs, all invariants, and every frozen contract. No architectural redesign,
no protocol change, no hidden coupling — the two new packages are additive and one-way dependent
(`nexus_approval → {nexus_workflows.spine, nexus_core, nexus_infra}`; `nexus_operations → {…, nexus_approval}`),
and the pipeline gained only a passive `granted_gates` relay plus an approval-aware pause. **No commit was
made** — awaiting explicit instruction.
