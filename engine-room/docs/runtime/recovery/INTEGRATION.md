# Integration — Validation → Recovery

Milestone 5. Recovery consumes the validated outcome and produces a decision, event stream,
and persisted plan — **without modifying Validation, Execution, or Runtime**.

---

## 1. The wired pipeline

```
RuntimeIntake → RM.prepare → Ready RuntimeSession
   → ExecutionEngine.execute(...) → ExecutionResult          [+ runtime.* events]
   → ValidationEngine.validate(...) → ValidationReport       [+ validation.* events]
   → RecoveryEngine.recover(report, result, events, policy, attempt, checkpoint_ref)
        → RecoveryPlan                                        [+ recovery.* events; persisted plan]
```

Wiring: `build_recovery(infrastructure, timestamps=…)` returns a `RecoveryContextBundle`
(engine + repositories) over the *same* Phase 2 infrastructure the runtime, execution, and
validation layers use — one event store, one correlation, shared observability.

## 2. Inputs consumed (by value/reference)

- **`ValidationReport`** (from `nexus_validation`) — the verdict, confidence, evidence refs,
  correlation.
- **`ExecutionResult`** (from `nexus_execution`) — the typed execution error for classification.
- **Recovery Policy** — the strategy bundle (doc 19); **attempt** — the retry history;
  **checkpoint_ref** — the latest valid checkpoint (doc 25).

Recovery reads these; it writes **only** its own output (the Plan) and appends `recovery.*`
events.

## 3. Integration invariants (verified in code)

`tests/integration/test_recovery_pipeline.py` asserts:

| Invariant | Test |
|---|---|
| Clean run → **Complete** | `test_clean_run_is_recovered_complete` |
| Claude error → **Retry** (retryable, budget) | `test_claude_failure_is_recovered_retry` |
| Partial + checkpoint → **Resume** from that checkpoint | `test_partial_validation_is_recovered_resume_from_checkpoint` |
| Policy-fatal category → **Abort** + `recovery.failed` | `test_abort_emits_recovery_failed` |
| Recovery **only appends** to the log (runtime/execution/validation events unchanged) | `test_recovery_only_appends_to_the_log` |
| Recovery shares the operation **correlation** | `test_recovery_shares_the_operation_correlation` |
| Plan **persisted** via Phase 2 repositories | `test_plan_is_persisted` |
| Full pipeline is **deterministic** | `test_full_pipeline_is_deterministic` |
| **Runtime / Execution / Validation** do not import `nexus_recovery` | 3 dependency-direction tests |

## 4. Validation, Execution & Runtime remain unchanged

- No source file in `nexus_validation`, `nexus_execution`, or `nexus_runtime` was modified for
  this program. Recovery depends on them one-way; they depend on nothing here (dependency
  guardrails above). The Validation Report and the pre-recovery events are immutable and
  observably untouched after `recover`.
- Recovery does **not** import Orchestration or Planning: the `Recovery → Orchestration`
  relationship (doc 19) is a feedback *data flow* (the orchestrator consumes the Plan), not a
  build dependency — Recovery is a pure decision function.

## 5. Events & persistence

- Events: `recovery.started`, `recovery.rule_evaluated` (one per rule), `recovery.decision_created`,
  then `recovery.completed` (a governed continuation was determined) or `recovery.failed`
  (Abort — no continuation exists) — canonical `recovery.*` namespace (doc 19 / doc 23),
  producer `recovery`, deterministic ids with a `-rec-` marker (no collision with `runtime.*`
  or `-val-` ids in the shared store).
- Persistence: `RecoveryRepositories` (plans) over the Phase 2 `InMemoryRepository`, exactly
  as Validation persists its reports. No new persistence mechanism was invented.
