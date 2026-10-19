# Integration — Execution → Validation

Milestone 5. Validation consumes Runtime/Execution output and produces a verdict, event
stream, and persisted report — **without modifying Runtime or Execution**.

---

## 1. The wired pipeline

```
RuntimeIntake → RM.prepare → Ready RuntimeSession
   → ExecutionEngine.execute(...) → ExecutionResult          [+ runtime.* events in the store]
   → ValidationEngine.validate(result, work_package, events) [reads the log; appends validation.*]
   → ValidationReport                                        [+ persisted report & evidence]
```

Wiring: `build_validation(infrastructure, timestamps=…)` returns a `ValidationContext`
(engine + repositories) over the *same* Phase-2 infrastructure the runtime and execution
layers use — one event store, one correlation, shared observability.

## 2. Inputs consumed (by value/reference)

- **`ExecutionResult`** (from `nexus_execution`) — outcome, exit status, error, captured
  output, metrics, artifact refs.
- **Runtime event log** — the `runtime.artifact_emitted` events (the *independent* Evidence
  Candidates), read from `infrastructure.event_store.read_all()`.
- **`WorkPackage`** — the objective and `completion_criteria` (what was requested).

Validation reads these; it writes **only** its own outputs (Evidence, Report) and appends
`validation.*` events.

## 3. Integration invariants (verified in code)

`tests/integration/test_validation_pipeline.py` asserts:

| Invariant | Test |
|---|---|
| Clean run → **Passed**, corroborated by an independent artifact (INV-20) | `test_clean_run_is_validated_passed`, `test_verdict_is_evidence_backed_not_self_report` |
| Claude error → **Failed** | `test_claude_failure_is_validated_failed` |
| Validation **only appends** to the log (runtime/execution events unchanged) | `test_validation_only_appends_to_the_log` |
| Validation shares the operation **correlation** | `test_validation_shares_the_operation_correlation` |
| Report + Evidence **persisted** via Phase-2 repositories | `test_report_and_evidence_persisted` |
| Full pipeline is **deterministic** | `test_full_pipeline_is_deterministic` |
| **Runtime** does not import `nexus_validation` | `test_runtime_does_not_depend_on_validation` |
| **Execution** does not import `nexus_validation` | `test_execution_does_not_depend_on_validation` |

## 4. Runtime & Execution remain unchanged

- No source file in `nexus_runtime` or `nexus_execution` was modified for this program (the
  execution states/events realized in program 1 already exist).
- Validation depends on them one-way; they depend on nothing here (dependency-direction
  guardrails above). The `ExecutionResult` and the pre-validation events are immutable and
  observably untouched after `validate`.

## 5. Events & persistence

- Events: `validation.started`, `validation.evidence_collected`,
  `validation.rule_evaluated` (one per rule), then `validation.completed` (non-Failed) or
  `validation.failed` (Failed) — canonical `validation.*` namespace (doc 15 §4, doc 23),
  producer `validation`, deterministic ids with a `-val-` marker (no collision with
  `runtime.*` ids).
- Persistence: `ValidationRepositories` (reports + evidence) over the Phase-2
  `InMemoryRepository`, exactly as RM persists its sessions/allocations. No new persistence
  mechanism was invented.
