# P13 — Constitutional Spine Fusion & Durable Pipeline Report

Status: Complete (implementation; not committed — awaiting explicit release instruction)
Scope: **one additive subsystem** — `nexus_workflows/spine/` — that fuses P0–P11 into a single durable
Goal→Knowledge pipeline. Closes P12 findings F-1, F-2, F-3. **No constitutional owner, ADR, contract,
or invariant changed.** The one incumbent edit is the sanctioned additive durable seam on
`PipelineBuilder` (F-2), default-preserving.

---

## Executive Summary

P12 found the platform was a set of proven segments, not a single driver: the grounded producers
(Intent→Engineering→Context→grounded Planning→Execution Actuation) formed the front-to-execution chain,
while the incumbent `WorkflowCoordinator` reached Validate→Learn — two composable chains, no unified
Goal→Knowledge run, and no full-pipeline durable restart. P13 builds that unified driver, additively.

The deliverable is `nexus_workflows.spine.ConstitutionalPipeline` — **one deterministic coordinator that
invokes each constitutional owner exactly once**, in dependency order, over one shared (durable) log:

```
Intent → Engineering → Context → Planning → Execution Actuation
      → [Execution→Validation seam] → Validation → Recovery → Reflection → Knowledge
```

It owns the *orchestration of the constitutional stages only* — the additive `pipeline.*` events — and
owns none of their behavior. It reuses the incumbent `Pipeline` wiring (for Context + the Validate→Learn
back chain), the grounded producers (P8/P9/P10), and the P11 Execution Actuator unchanged. The three
findings close as follows:

- **F-1 (one driver):** the coordinator runs the whole spine, feeding the Intent-produced Goal + the
  Engineering Strategy into grounded Planning and driving execution through the **P11 actuator** — no
  competing coordinator, no engine duplicated.
- **F-2 (durable restart):** one durable pipeline session restarts from the **last completed
  constitutional boundary**, reconstructing each completed owner's artifact from the shared log without
  re-invoking it. Restart nests: a mid-execution interruption resumes at Actuation and the actuator then
  resumes node-level from its own log.
- **F-3 (Execution→Validation seam):** a pure `ExecutionState + log → ExecutionResult` projection so the
  actuator hands off to Validation using the frozen contract — reaching **PASSED** (evidence-corroborated,
  INV-20), not a degraded PARTIAL.

**Validation:** 21 new tests (14 unit + 7 integration), all green; **full v2 sweep 2 831 passed, 1
opt-in skip, 0 regressions** (1 pre-existing `test_state_machines` `db_session` error from the
`--noconftest` fixture strip, unrelated); **91 architecture guardrail tests pass**; **17 event producers,
each unique** (`pipeline` is the 17th); mypy-strict + ruff clean. The unified pipeline is deterministic,
durably replayable, and restartable end-to-end.

---

## Constitutional Compliance

Audited against the 39 invariants and the decision-ownership table. **No violation introduced.** The
coordinator reasons/estimates/plans/traverses/validates/recovers/reflects/learns/evaluates-policy through
**nobody's internals** — every stage is a call to an existing owner's public entry point.

| Concern | Evidence | Verdict |
|---|---|---|
| **INV-01** one-way deps | `nexus_workflows` is the integration boundary (imported by nothing); it may import every engine. No new inverted dependency; guardrails green. | ✅ Intact |
| **INV-02 / one owner per decision** | The coordinator makes **no** constitutional decision — it only sequences owners. Its own facts are the single-producer `pipeline.*` stream (`producer="pipeline"`, the 17th unique producer). | ✅ One owner each |
| **INV-07** one schema per object | The pipeline adds **no** frozen domain object. `PipelineSession` is a `ValueObject` projection of the `pipeline.*` log; `SpineRun`/`SpineRequest`/`SpineControl` are plain dataclasses (integration I/O). Guardrail-proven (no `DomainObject` base). | ✅ No competing model |
| **INV-11** Observation owned by Supervision | `PipelineObservability` only increments counters over the P1 sink — instrumentation, never authoritative state. | ✅ Holds |
| **INV-13/14/15** log is truth; state derived; one event per transition | The pipeline session, and every owner artifact, reconstruct from the shared log; each `pipeline.*` fact is content-hash-addressed (idempotent re-append — INV-16). | ✅ Holds |
| **INV-16** idempotent consumers | Restart re-emits the deterministic back-chain/started facts idempotently (identical id+content = no-op); reconstructed owners are never re-invoked. | ✅ Holds |
| **INV-17** capture, don't recompute | On restart the Goal, Strategy, ExecutionPlan, and ExecutionState are reconstructed from their owners' **embedded** facts — no re-understanding, re-inference, re-planning, or re-execution. | ✅ Holds |
| **INV-18** resume from checkpoint, never from Goal | Restart resumes at the first constitutional boundary not on the log; the Actuator resumes node-level. Never restarts from the raw request. | ✅ Holds |
| **INV-20/21** evidence-based completion; execution never self-completes | The F-3 projection preserves the runtime session scope so Validation's independent artifact corroboration resolves — PASSED requires an independent artifact, not the runtime's self-report. | ✅ Holds |
| **INV-22** recovery never restarts from Goal | Recovery consumes the projected `ExecutionResult` + log; the failure path yields bounded `retry`. | ✅ Holds |
| **INV-24/26** evidence-backed Knowledge; learning via the record | Knowledge ingests only validated-provenance candidates. (The fused driver does not yet *read* Knowledge pre-planning — see Remaining Gaps; that is a capability gap, not a violation.) | ✅ Holds |
| **INV-28/30/31** Policy sole evaluator | Engineering consults Policy (simulate) unchanged; no policy logic added. | ✅ Holds |
| **INV-37** Orchestration selects runtime | Execution runs through the P11 actuator → Orchestration coordinators → Runtime Manager, unchanged. | ✅ Holds |
| **INV-39** correlated events | Every `pipeline.*` fact carries the run correlation identifier. | ✅ Holds |

---

## Pipeline Architecture

The subsystem is seven small modules under `nexus_workflows/spine/`, additive to the incumbent
`nexus_workflows` integration package (which already imports every engine and is imported by nothing):

| Module | Responsibility |
|---|---|
| `model.py` | `SpineStage` (the 9 stages), `SpineStatus`, `PipelineSession` (ValueObject projection), `SpineRequest` (text-first input), `SpineControl` (graceful-stop bound), `SpineRun` (immutable outcome). |
| `events.py` | The additive `pipeline.*` facts + `build_event` (`producer="pipeline"`, `source="nexus_workflows.spine"`). |
| `bridge.py` | **F-3** — `execution_results(state, log)`: the Execution Actuation → Validation seam. |
| `coordinator.py` | **F-1/F-2** — `ConstitutionalPipeline` (the driver, stage coordination, restart) + the replay reconstructors (`find_goal/strategy/plan/execution_state`, `reconstruct_pipeline_session`) + `PipelineObservability`. |
| `composition.py` | `build_constitutional_pipeline(infra, …)` — DI wiring over one (durable-capable) infrastructure. |
| `reference.py` | The canonical text-first `spine_reference_request` for tests. |
| `__init__.py` | Public exports. |

**Reuse, not reimplementation.** `build_constitutional_pipeline` reuses the incumbent `Pipeline` (via the
F-2 durable seam) for Context Engineering and the Validate→Learn back chain; the grounded producers
(P8/P9/P10) and the P11 Execution Actuator for the front-to-execution chain. There is **no competing
orchestration framework** — the guardrail asserts the composition drives owners through the public roots
(`PipelineBuilder`, `build_intent`, `build_engineering`, `build_grounded_planning`).

The **one incumbent edit** is the F-2 durable seam: `PipelineBuilder.__init__` gains an optional
`infrastructure: InfrastructureContext | None = None` (default `None` → unchanged in-memory behavior);
`build()` wires over the injected infra when present. This is what lets the *whole* Goal→Knowledge run —
not just the P11 execution slice — ride a durable (ADR-007) log. All incumbent workflow/briefing/research
tests pass unchanged.

---

## Stage Coordination

`ConstitutionalPipeline.run(request, *, control)` drives `ORDERED_STAGES` once each:

1. **Intent** — `resolve(request_from_text(...))` → Goal (from raw operator text; the pipeline starts
   *before* the Goal).
2. **Engineering** — `strategize_for_goal(goal, estimation, policy)` → EngineeringStrategy.
3. **Context** — `engineer(goal, ContextRequest)` → ContextPackage.
4. **Planning** — grounded `plan(PlanningInputs(goal, strategy, context, work_items))` → ExecutionPlan.
5. **Actuation** — `build_execution_actuation(infra, adapter).actuate(ActuationInputs)` → ExecutionState
   (drives Orchestration + Runtime + Execution).
6. **Validation** — over the F-3-projected `ExecutionResult`s → ValidationReports.
7. **Recovery** — `recover(report, result)` → RecoveryPlans.
8. **Reflection** — `reflect(scope, results, reports, plans)` → ReflectionReport + candidates.
9. **Knowledge** — `ingest(candidate)` → recorded Knowledge.

Each stage emits `pipeline.stage_started` then `pipeline.stage_completed` (carrying the produced
artifact's reference). The run emits `pipeline.started` (first run) or `pipeline.resumed` (restart), and
`pipeline.completed` on reaching Knowledge. A graceful stop (`SpineControl.stop_after_stage`, or an
actuation left `PAUSED`) emits `pipeline.paused` and returns a resumable `SpineRun`. Actuation that ends
`BLOCKED` (a failure halted a branch) is **terminal, not paused** — the outcome is handed to Validation to
judge, so a failed run still reaches Knowledge (the lesson is recorded), exactly matching the incumbent.

Observed on the reference run: all nine stages execute once, `validation_decisions == (passed, passed)`,
Knowledge recorded; the shared log carries **12 producers** (intent, estimation, engineering, policy,
context_engineering, planning, runtime, validation, recovery, reflection, knowledge, pipeline —
Orchestration and the Execution engine participate *through* Actuation's `runtime` lineage, per P12/F-6).

---

## Durable Restart (F-2)

A durable pipeline session is the projection of the `pipeline.*` stream (`reconstruct_pipeline_session`).
Restart resumes from the **last completed constitutional boundary**, reconstructing each completed owner's
artifact from that owner's **embedded** fact on the shared durable log — never re-invoking it:

| Boundary | Reconstructed from | Owner re-invoked? |
|---|---|---|
| Goal | `intent.resolved` → `IntentAnalysis` | No |
| EngineeringStrategy | `engineering.strategized` → `EngineeringStrategy` | No |
| ExecutionPlan | `planning.execution_plan_assembled` → `ExecutionPlan` | No |
| ExecutionState | `execution.completed` → `ExecutionState` | No |

The resume point is the first stage whose artifact is not yet on the log. **Context Engineering is
checkpointed jointly with Planning** — its ContextPackage is a transient, deterministic input consumed
only by Planning and superseded by the log-embedded ExecutionPlan, so it is never persisted as a second
copy of another owner's artifact in the pipeline log (avoiding an INV-07/ownership smell).

**Restart nests.** A mid-execution interruption (`ActuationControl.stop_after`) leaves Actuation `PAUSED`
with no `execution.completed`; restart resumes *at* Actuation, and the actuator itself seeds its completed
nodes from the durable `execution.*` log and continues node-level — never replanning (INV-18).

Demonstrated (`test_pipeline_restarts_*`):
- **Post-actuation boundary:** interrupt after Actuation → restart reconstructs Intent/Engineering/
  Context/Planning/Actuation (owners not re-invoked) and executes only Validation→Recovery→Reflection→
  Knowledge; the resumed `ExecutionState`, validation decisions, and Knowledge ids equal an uninterrupted
  run's.
- **Mid-execution boundary:** interrupt after one node → restart reconstructs the front, re-enters
  Actuation (resumes node-level), and reaches Knowledge.

---

## Replay Validation

Replay reconstructs the complete pipeline from the durable log alone (`test_pipeline_replays_*`): a
reopened file yields `reconstruct_pipeline_session(...).stages_completed == all nine stages` with status
`COMPLETED`, and `find_execution_state(events)` equals the original `ExecutionState`. No stage
re-executes during replay — reconstruction reads embedded facts (INV-13/14/17). Determinism is
byte-exact: two independent runs over fresh infrastructure yield identical `(identifier, type, payload)`
event streams (`test_pipeline_is_the_only_driver_and_is_deterministic`).

---

## Execution → Validation Integration (F-3)

The actuator yields one `ExecutionState` (a projection of the `execution.*` log); Validation consumes the
frozen `ExecutionResult` — one per executed node. `bridge.execution_results(state, events)` reconstructs
each `ExecutionResult` additively, without touching the actuator's contract.

The one subtlety it closes: Validation's INV-20 artifact-corroboration rule reads the **independent**
`runtime.artifact_emitted` events keyed by the node's *execution-session* scope — an identity the actuator
does not surface. The bridge recovers it from the runtime's frozen `runtime.session_created` fact (which
carries `node`), so the projected `session_ref` matches the log and corroboration resolves exactly as it
does for the incumbent per-session loop. Because the engine's teardown always reaches `Destroyed`,
`final_state` is deterministically `DESTROYED`. The proof is behavioral: validation returns **PASSED**
(not PARTIAL) for a clean run and **FAILED** for the failure path (`test_bridge.py`,
`test_recovered_scope_lets_validation_corroborate_to_passed`). Execution never touches Knowledge —
Validation remains the independent judge in between.

---

## Operational Readiness

| Concern | Status | Evidence |
|---|---|---|
| **Startup** | ✅ | `build_constitutional_pipeline(infra)` wires the whole spine over one infra; `build_durable_infrastructure` opens SQLite/WAL (ADR-007). |
| **Shutdown / graceful stop** | ✅ | `SpineControl.stop_after_stage` / `ActuationControl` stop the run gracefully and return a resumable `SpineRun`. |
| **Restart** | ✅ | Full-pipeline restart from the last completed constitutional boundary (post-actuation **and** mid-execution), proven identical to an uninterrupted run. |
| **Replay** | ✅ | Full-pipeline durable replay reconstructs the pipeline session + owner artifacts; no re-execution. |
| **Failure handling** | ✅ | `fail=True` → outcomes `failed`, validation `failed`, recovery `retry` (bounded), Knowledge still recorded. |
| **Checkpoint / approval** | ✅ | Handled by the P11 actuator inside the Actuation stage (checkpoint/approval events, gated pauses) — unchanged. |
| **Governance / fail-closed** | ✅ | Policy governs via Engineering (simulate); the fail-closed default is proven independently (P12). |
| **Determinism** | ✅ | Byte-identical event streams across runs (FixedTimestampSource; content-addressed ids). |

---

## Remaining Architectural Gaps

Documented honestly (none is a violation; none blocked the milestone):

1. **Cross-run learning is not exercised by the unified driver (INV-26 read loop).** The incumbent
   `WorkflowCoordinator` reads Knowledge before planning and folds it into the `PlanningRequest` as
   assumptions. The grounded planner (P10) does not accept a prior-knowledge input, so the fused pipeline
   does not *read* Knowledge pre-planning. Learning still flows *out* (Knowledge is written each run), and
   the incumbent read-loop path is untouched — but the unified driver does not yet demonstrate run-2
   grounded by run-1's Knowledge. Closing it needs grounded Planning to accept a prior-knowledge input (a
   P10 enhancement), out of P13 scope. **Recommended for P14.**
2. **Back-chain restart granularity.** Validation→Knowledge form the deterministic learning tail
   downstream of the ExecutionState checkpoint. A restart interrupted *within* the tail re-derives it
   idempotently from the reconstructed ExecutionState (identical event re-append is a no-op — INV-16;
   identical Knowledge items re-ingest idempotently) rather than skipping the completed tail owners
   individually. Per-owner back-chain checkpoints are a possible refinement; the current design is correct
   (no duplicate effect) and simpler.
3. **The incumbent `WorkflowCoordinator` is retained.** P13 *adds* the unified `ConstitutionalPipeline`
   rather than deleting the incumbent, which is still consumed by the briefings/research workflows (goal-
   first, back-chain-only). The P12 "split" — a grounded front with no back half, and a back chain with no
   grounded front — is eliminated: one driver now spans the whole spine. The incumbent remains an
   independent, narrower workflow, not a competing half; removing it would break its existing consumers
   (out of scope).
4. **P12 cosmetic findings persist, not worsened.** F-4 (two clock conventions) is *narrowed* inside the
   spine — the coordinator unifies `now = timestamps.now` so one clock drives every stage. F-5 (two
   `PolicyContext` classes) and F-6 (`execution.*` events carry `producer="runtime"`) are unchanged; the
   spine takes no dependency that worsens them.

---

## Recommendation for P14

**P14 — Grounded Learning Loop & Human-Interaction Surface.** Two threads, in order:

1. **Close the learning loop additively (Gap 1):** give grounded Planning a read-only prior-knowledge
   input so the unified pipeline grounds run-2 planning in run-1's Knowledge (INV-26 via the record),
   completing the cognition→learning→cognition cycle on the single driver.
2. **Build the Human-Interaction channel (P5):** the approval boundary is *enforced* (Actuation pauses at
   an ungranted gate) but there is no surface to present the decision and collect a response. With the
   spine now unified, durable, and restartable, the approval pause + `pipeline.resumed` gives a clean seam
   for a human-in-the-loop surface — the prerequisite for approval-gated autonomy.

Then Scheduler and Operations, on the now-coherent, durable pipeline base — the sequence the P12 objective
prescribed (unify and harden the pipeline first).

---

## Success Criteria

| Criterion | Result |
|---|---|
| One constitutional Goal→Knowledge pipeline exists | ✅ `ConstitutionalPipeline` drives all nine stages once. |
| Split execution paths eliminated without changing ownership | ✅ One driver spans the whole spine; no owner modified (see Gap 3 for the retained legacy path). |
| Restart resumes from the last completed constitutional stage | ✅ Post-actuation + mid-execution, proven identical to an uninterrupted run. |
| Replay reconstructs the complete pipeline | ✅ Pipeline session + owner artifacts reconstruct from the durable log; no re-execution. |
| Execution hands off cleanly to Validation | ✅ F-3 projection → PASSED (evidence-corroborated). |
| No constitutional owner changes | ✅ Only additive code + the sanctioned `PipelineBuilder` durable seam (F-2). |
| No ADR/contract/invariant changes | ✅ None touched. |
| All tests pass, zero regressions | ✅ 2 831 passed, 1 opt-in skip, 0 regressions; 91 guardrails green; mypy/ruff clean. |

---

## Validation Summary

- **21 new tests:** unit — `test_coordinator.py` (5: drives-every-stage-once, evidence-backed Knowledge,
  determinism, single-producer, failure propagation), `test_bridge.py` (3: F-3 projection, scope-recovery
  → PASSED, failed-node projection), `test_reconstruct.py` (2: owner-artifact + pipeline-session replay),
  `test_guardrails.py` (4: single producer, no new domain object, ValueObject session, no competing
  framework); integration — `test_constitutional_spine.py` (7: whole-spine-to-Knowledge, determinism,
  durable replay, restart-from-last-stage, mid-execution restart, failure→Knowledge, event-lineage).
- **Full v2 sweep: 2 831 passed, 1 skipped (opt-in), 0 regressions** (1 pre-existing `test_state_machines`
  `db_session` error from `--noconftest`, unrelated).
- **91 architecture guardrail tests pass** (P12's 87 + 4 new). **17 event producers, each unique**
  (`pipeline` is the 17th). **mypy-strict + ruff** clean on the new package + the seam.
- **Incumbent surface:** `git status` shows exactly one tracked-file modification — the additive
  `PipelineBuilder` durable seam — plus the new `nexus_workflows/spine/` package, its tests, and this
  report. No owner/contract/ADR/invariant changed.

Per the rules, **no commit was made**.
