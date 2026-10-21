# Recovery Engine — implementation

Milestones 1-5. The Recovery Engine is the deterministic **decision layer between Validation
and future execution** (doc 19). It consumes a validated outcome and produces an immutable
**Recovery Plan** that names the governed next action. It **decides continuation** (INV-21)
and never acts: it never executes, retries, restores, fails over, plans, mutates Validation,
or invokes AI (doc 19 boundaries; INV-22). No architectural conflict was found; no
`ARCHITECTURAL_CONFLICT_<N>.md` was produced.

---

## 1. Position & inputs

```
Execution Result ─┐
                  ├─▶ Recovery Engine.recover(report, result, *, events, policy, attempt, checkpoint_ref) ─▶ Recovery Plan
Validation Report ┘
```

- **`ValidationReport`** (from `nexus_validation`) — the primary input: the verdict
  (Passed / Failed / Partial / Requires Review), confidence, evidence refs, correlation.
- **`ExecutionResult`** (from `nexus_execution`) — the typed execution error (doc-11
  `error_class` / `owner`) used for failure classification.
- **Recovery Policy** — the declarative bundle (retry budget, fatal categories, approval
  categories, resume permission, escalation target). Recovery is *strategy driven* (doc 19):
  it never invents behaviour, it applies the policy.
- **`attempt`** — the 1-based attempt count (the orchestrator supplies the history; Recovery
  is a pure decision function of it).
- **`checkpoint_ref`** — the latest valid checkpoint to resume from, if any (doc 25:
  Execution *creates* checkpoints, Recovery *restores* them — it never defines their shape).

Recovery reads these and writes **only** its own output (the Recovery Plan) plus `recovery.*`
events. It never mutates the Validation Report, the Execution Result, or the event log.

## 2. What `recover` does (deterministic pipeline)

1. emit `recovery.started`;
2. **classify** the failure into a doc-19 `FailureCategory` (`classification.py`);
3. evaluate each deterministic **rule** (`rules.py`), emitting `recovery.rule_evaluated`;
4. **aggregate** one decision by fixed precedence (`evaluator.py`);
5. build the immutable **Recovery Plan** (`plan.py`) — references, never copies;
6. emit `recovery.decision_created`, then `recovery.completed` (a governed continuation was
   determined) or `recovery.failed` (Abort — no continuation exists);
7. **persist** the Plan and return it.

## 3. Modules

| Module | Responsibility |
|---|---|
| `vocabulary.py` | closed enums (`RecoveryDecision`, `RecoveryStage`, `FailureCategory`, `RetryPolicyKind`, `RecoveryRuleOutcome`) + `Reference` target-type strings |
| `ids.py` | deterministic `plan_id` / `event_id` (pure functions of session + kind + ordinal; `-rec-` marker) |
| `policy.py` | `RetryPolicy` / `RecoveryPolicy` bundle + `DEFAULT_RECOVERY_POLICY` |
| `classification.py` | `FailureClassifier` → `FailureSignal` (doc-11 error → doc-19 category) |
| `rules.py` | `RecoveryContext` + six deterministic rules + `DEFAULT_RULES` + `DECISION_PRECEDENCE` |
| `evaluator.py` | `RecoveryEvaluator` → `RecoveryDetermination` (precedence + derivation) |
| `plan.py` | `RecoveryRuleResult`, `RecoveryPlan` (immutable, reference-only output) |
| `events.py` | `recovery.*` taxonomy + `build_event` |
| `observability.py` | derived counters over the Phase 2 sink |
| `persistence.py` | `RecoveryRepositories` over the Phase 2 `InMemoryRepository` |
| `engine.py` | `RecoveryEngine.recover(...)` orchestration |
| `composition.py` | `build_recovery(infrastructure, ...)` DI wiring |

Dependency direction: `nexus_recovery → {nexus_validation, nexus_execution, nexus_runtime,
nexus_core, nexus_infra}` — strictly downstream. Recovery does **not** depend on Orchestration
or Planning (the `Recovery → Orchestration` feedback is a data flow, not a build dependency —
doc 99 §layering).

## 4. Determinism

Every field of the plan and every event id is a pure function of `(report, result, policy,
attempt, checkpoint)` and the injected timestamp — no clock, no randomness. Identical inputs
yield a byte-identical plan and event stream (`test_engine.py::
test_two_runs_produce_identical_plans_and_events`; the E2E determinism test). Timestamps are
the one captured-as-data value (INV-17); their source is injected.

## 5. Tests & coverage

`tests/unit/nexus_recovery/` (classification, rules, evaluator, engine, units) +
`tests/integration/test_recovery_pipeline.py` — **66 tests, 100% branch coverage** on the
package. The full suite (2240 passed / 1 skipped) is green with all prior phases unchanged.
