# Integration — Recovery → Reflection

Milestone 5. Reflection consumes the completed operational history and produces an analytical
report, event stream, and persisted outputs — **without modifying Recovery, Validation,
Execution, or Runtime**.

---

## 1. The wired pipeline

```
RuntimeIntake → RM.prepare → Ready RuntimeSession
   → ExecutionEngine.execute(...) → ExecutionResult          [+ runtime.* events]
   → ValidationEngine.validate(...) → ValidationReport       [+ validation.* events]
   → RecoveryEngine.recover(...) → RecoveryPlan              [+ recovery.* events]
   → ReflectionEngine.reflect(scope, execution_results, validation_reports, recovery_plans, events, metrics)
        → ReflectionReport                                   [+ reflection.* events; persisted report & patterns]
```

Wiring: `build_reflection(infrastructure, timestamps=…)` returns a `ReflectionContextBundle`
(engine + repositories) over the *same* Phase 2 infrastructure the runtime, execution,
validation, and recovery layers use — one event store, one correlation, shared observability.

## 2. Inputs consumed (by value/reference)

- **`ExecutionResult`s / `ValidationReport`s / `RecoveryPlan`s** — the immutable per-execution
  outputs, correlated by session into an `OperationalHistory`.
- **Runtime events** — carried through for provenance.
- **Operational metrics** — an optional window-level `Struct`.

Reflection reads these; it writes **only** its own outputs (Report + Patterns) and appends
`reflection.*` events. It **never modifies collected data** (doc 26 *Evidence First*).

## 3. Integration invariants (verified in code)

`tests/integration/test_reflection_pipeline.py` asserts:

| Invariant | Test |
|---|---|
| A completed operation is reflected into a report with patterns | `test_clean_operation_is_reflected` |
| A failed operation surfaces a failure/recovery pattern | `test_failed_operation_surfaces_a_failure_pattern` |
| Reflection **only appends** to the log (runtime/execution/validation/recovery events unchanged) | `test_reflection_only_appends_to_the_log` |
| Reflection shares the operation **correlation** | `test_reflection_shares_the_operation_correlation` |
| Report + Patterns **persisted** via Phase 2 repositories | `test_report_and_patterns_persisted` |
| Full pipeline is **deterministic** | `test_full_pipeline_is_deterministic` |
| **Runtime / Execution / Validation / Recovery** do not import `nexus_reflection` | 4 dependency-direction tests |

## 4. Recovery, Validation, Execution & Runtime remain unchanged

- No source file in `nexus_recovery`, `nexus_validation`, `nexus_execution`, or `nexus_runtime`
  was modified for this program. Reflection depends on them one-way; they depend on nothing here
  (dependency guardrails above). The collected outputs and pre-reflection events are immutable
  and observably untouched after `reflect`.
- Reflection does **not** import Knowledge or Planning (INV-26): Knowledge Candidates travel
  inside the Report as advisory data; a future Knowledge subsystem consumes them.

## 5. Events & persistence

- Events: `reflection.started`, `reflection.analysis_completed`, `reflection.report_created`,
  then `reflection.completed` (history reflected) or `reflection.failed` (no operational
  history) — canonical `reflection.*` namespace (doc 26 / doc 23), producer `reflection`,
  deterministic ids with a `refl-` marker (no collision with `runtime.*`, `-val-`, or `-rec-`
  ids in the shared store).
- Persistence: `ReflectionRepositories` (reports + patterns) over the Phase 2
  `InMemoryRepository`, exactly as the prior layers persist their outputs. No new persistence
  mechanism was invented; Knowledge Candidates are **not** persisted as Knowledge (INV-25).
