# H-4 — Pilot Execution Roadmap (Nexus Experimental → Pilot)

> **Planning only — no implementation, no source changes, no migrations.** The final, ordered Pilot
> implementation sequence with per-item justification, affected files, test strategy, rollback strategy,
> and risk. Derived from `H-4-readiness-review.md`, `H-4-scope-definition.md`,
> `ADR-nexus-v1.1-foundation`, and the H-1 lifecycle/recovery designs. Built on the H-2 freeze
> (`d6bd75d`, tag `hermes-experimental`). Each step is **separately authorized** before implementation.

---

## 0. Ordering principle

Lowest-risk, independent items first (build confidence + the config/init scaffolding the lifecycle
items lean on), then the lifecycle state machine (terminate → cancellation wiring → TIMED_OUT), then
recovery (resume), then the audited validation run that exercises everything end-to-end. This front-loads
safe wins and isolates the single orchestrator touch (cancellation wiring) to one reviewable step.

## 1. fail-fast initialization

- **Order justification:** smallest, independent, zero-coupling change; removes the "runs without a
  usable key" footgun and is a precondition for trusting every later lifecycle test (no silent no-key
  path). Safe first win.
- **Affected files:** `nexus/execution/runners/nexus.py` (`initialize()` raises on missing usable key).
- **Test strategy (RED-first):** `test_init_fails_without_key` (raises `ConfigurationError`/
  `ExecutionEngineError`; run does not proceed); `test_init_proceeds_with_key`. Regression: H-2 tests
  that construct the adapter inject a client/provider, so they are unaffected.
- **Rollback strategy:** single-method change; revert the `initialize()` body to the prior no-op. No data
  or schema impact; no dependents.
- **Risk:** **Low.** Only hazard is a test that relied on key-less construction reaching execution — none
  do after H-2 (they inject fakes).

## 2. configurable execution budgets

- **Order justification:** independent, additive config; needed before TIMED_OUT (step 5) so the budget
  is operator-tunable rather than the hardcoded `max_steps = 5`. Low risk, unblocks later items.
- **Affected files:** `nexus.py` (read budget from settings, default 5 preserved); `nexus/config.py`
  (**additive** field, e.g. `execution.agent_max_steps`).
- **Test strategy:** `test_step_budget_configurable` (configured value honored); `test_budget_default_preserved`
  (unset → 5). Regression: existing execute tests still finish within budget.
- **Rollback strategy:** remove the config read + field; revert to the literal. Additive field is
  backward-compatible; no migration to undo.
- **Risk:** **Low.** Additive config; no schema/migration.

## 3. `terminate()`

- **Order justification:** the cancellation mechanism must exist (set a signal; kill an in-flight sandbox
  process) before it can be wired (step 4). Splitting mechanism (step 3) from wiring (step 4) keeps the
  orchestrator-touching change isolated and independently reviewable.
- **Affected files:** `nexus.py` (`terminate()` sets a DB-observable cancel signal on `ExecutionRecord`;
  loop checks the signal at state boundaries; in-flight `execute_command` killed via
  `SandboxProcess.terminate()` / provider terminate, `provider.py:47-50` — reused, not new).
- **Test strategy:** `test_terminate_sets_cancel_signal`; `test_cancel_between_steps_cancels` (→
  `CANCELLED` terminal + `cancelled` exit); `test_inflight_command_killed`;
  `test_cancel_latency_bounded` (≤ one tool execution).
- **Rollback strategy:** revert `terminate()` to `pass` and remove the loop-boundary checks; the signal
  field (if a new column were used) is avoided by reusing an existing status/flag — so rollback is
  logic-only. No orchestrator change in this step to undo.
- **Risk:** **Medium.** Async cancellation correctness; must remain cooperative (no forced task kill).

## 4. cancellation wiring (orchestrator)

- **Order justification:** the **only** orchestrator edit in H-4; done immediately after the mechanism
  exists so it can be tested against a working `terminate()`. Isolated as its own step to bound the
  blast radius of the single architecture touch.
- **Affected files:** `nexus/scheduling/orchestrator.py` (agent branch `orchestrator.py:210-216` and the
  timeout path invoke `adapter.terminate()` on operator action / timeout — one invocation point);
  possibly `core/types.py` (**additive** `ExitStatus.CANCELLED` already exists `types.py:136`).
- **Test strategy:** `test_orchestrator_invokes_terminate_on_timeout`;
  `test_orchestrator_cancellation_finalizes_cancelled`; e2e guard that the normal success/failure paths
  are unchanged (`test_mvp_workflow`).
- **Rollback strategy:** remove the single `terminate()` invocation in the orchestrator; the adapter
  mechanism (step 3) remains dormant and harmless. Revert is one hunk.
- **Risk:** **Medium–High.** Touches shared orchestration; mitigated by isolation, a single invocation
  point, and the e2e guard.

## 5. `TIMED_OUT` lifecycle

- **Order justification:** depends on the configurable budget (step 2) and the lifecycle plumbing
  (steps 3–4); converts "budget/wall-clock exhausted" from H-2's honest binary failure into a distinct
  terminal so timeouts are observably different from errors and completions.
- **Affected files:** `nexus.py` (enforce ADR-010 wall-clock via the already-imported
  `resolve_execution_timeout`; budget/time exhaustion → `TIMED_OUT`); `core/types.py` only if an
  `ExitStatus.TIMED_OUT` is added (**additive**; `ExecutionStatus.TIMED_OUT` already exists
  `types.py:41`); `orchestrator.py` only if a distinct finalization is wanted (else maps to FAILURE).
- **Test strategy:** `test_budget_exhaustion_times_out`; `test_wallclock_timeout_times_out`;
  `test_timed_out_distinct_from_completed_and_failed`.
- **Rollback strategy:** revert the timeout branch so exhaustion falls back to H-2's `exit_code 1/failed`
  (still honest). Additive enum value (if added) is backward-compatible.
- **Risk:** **Low–Medium.** Interaction with orchestrator finalization mapping; kept additive.

## 6. `resume_goal()`

- **Order justification:** independent of cancellation (a read-reconstruction), but sequenced after the
  lifecycle terminal states exist so "resumable boundary" (`CHECKPOINTED`) and terminal semantics are
  well-defined. Last code item before the audited run.
- **Affected files:** `nexus.py` (`resume_goal(execution_id)`: rebuild trajectory from `AgentStepRecord`
  ordered by `step_index`; restore plan + cursor from latest `WorkflowCheckpointRecord`; `step_index =
  max+1`; re-enter loop; re-validate goal via governance); `base.py` (`AgentRuntimeAdapter` — **additive
  optional** method; CLI adapters untouched).
- **Test strategy:** `test_resume_rebuilds_trajectory`; `test_resume_continues_from_cursor`;
  `test_resume_no_duplicate_step`; `test_resume_fails_closed_on_missing_data`;
  `test_resume_revalidates_governance`.
- **Rollback strategy:** remove `resume_goal` + the optional contract method; pure addition, nothing else
  depends on it; no schema to undo (read-only over existing tables).
- **Risk:** **Low–Medium.** Idempotency/cursor correctness; bounded by fail-closed on inconsistent data.

## 7. audited real-world validation run

- **Order justification:** the Pilot gate's evidence requirement — exercises honesty + lifecycle +
  recovery together with a **real** provider, proving genuine governed output. Must be last (needs all
  prior items).
- **Affected files:** none (a test/fixture or a documented run with a real `SearchProvider`/LLM);
  evidence captured in a deliverable, not source.
- **Test strategy:** one end-to-end governed run producing genuine output, fully audited
  (`agent_steps` + `sandbox.*` + artifacts); assert truthful terminal status; optionally a cancellation
  and a resume exercised within the run.
- **Rollback strategy:** n/a (evidence artifact; no code).
- **Risk:** **Low.** Environment/provider availability dependency.

## 8. Sequence summary

```
1 fail-fast init        (Low)        ─ independent
2 configurable budget   (Low)        ─ independent; precedes 5
3 terminate()           (Medium)     ─ mechanism; precedes 4
4 cancellation wiring   (Med–High)   ─ only orchestrator touch; after 3
5 TIMED_OUT lifecycle   (Low–Med)    ─ after 2 + 3/4
6 resume_goal()         (Low–Med)    ─ after terminal states defined
7 audited real run      (Low)        ─ after all; Pilot evidence
```

## 9. Pilot promotion gate (recap)

Experimental **plus** wired+tested cancellation (3,4) · working+tested resume (6) · fail-fast init (1) ·
configurable budget (2) · timeout lifecycle (5) · R-05 file confinement (**done, S-4**) · one audited
real run (7). AP-105 Caps 12 & 14 = Implemented; 17 & 19 ≥ Implemented.

## 10. Boundaries (reaffirmed)

No schema redesign / no migrations (additive enums only; resume is read-only) · one orchestrator touch
(step 4) · Runtime V2 contract additive-only · governance/registry/scheduler/events/Track-S seam
preserved · cooperative cancellation only. **H-4 is gated** — implementation begins only on explicit
authorization; this roadmap authorizes nothing.

## 11. Risk detail

See `H-4-risk-plan.md` for the consolidated risk register, mitigations, and per-step rollback triggers.
