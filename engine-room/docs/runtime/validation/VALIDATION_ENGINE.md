# Validation Engine — implementation overview

Engineering program 2. The Validation Engine (`nexus_validation`) is the first governance
layer after execution: it **judges** whether an execution achieved its objective, using
deterministic evidence alone. It conforms to the frozen Validation architecture
(`docs/v2/14_VALIDATION.md`) and the invariants — no ADR, contract, invariant, or frozen
document was modified. These are engineering documents, not architecture.

---

## 1. Position & dependency direction

```
Execution Engine → Execution Result ─┐
Runtime event log (runtime.*) ───────┼─▶ Validation Engine → Evidence → Validation Report
Work Package (objective + criteria) ─┘         │ validation.* events
                                               ▼
                                     Event Store + Persistence  → (future) Recovery / Reflection
```

`nexus_validation → { nexus_execution, nexus_core, nexus_infra }`. It consumes the
`ExecutionResult` and the runtime event log **by value/reference**, and reuses the Phase 2
substrate (emitter, repositories, observability). Nothing upstream imports it (asserted in
`tests/integration/test_validation_pipeline.py`). It never mutates Runtime or Execution.

## 2. Modules

| Module | Responsibility |
|---|---|
| `vocabulary.py` | `ValidationDecision` (Passed/Failed/Partial/Requires Review — doc-14 canon), `ValidationStage`, `EvidenceSource`, `RuleOutcome`, target-type tags |
| `evidence.py` | `Evidence` — immutable, traceable observed fact (produced by Validation, INV-12) |
| `collector.py` | `EvidenceCollector` + `ArtifactInspector` / `OutputCollector` / `MetadataCollector` (Milestone 1) |
| `rules.py` | deterministic `ValidationRule`s + `ValidationPolicy` + `RuleContext` (Milestone 2) |
| `evaluator.py` | `DecisionEvaluator` — aggregates rule results → verdict + confidence (INV-20 policy) |
| `report.py` | `RuleResult`, `ValidationReport` — the immutable, evidence-referencing verdict (Milestone 3) |
| `events.py` | `validation.*` taxonomy + `build_event` (producer `validation`) (Milestone 4) |
| `engine.py` | `ValidationEngine.validate(...)` — orchestrates collect → evaluate → report → emit → persist (Milestone 5) |
| `observability.py`, `persistence.py`, `composition.py` | Phase-2 reuse: counters, repositories, DI wiring |

## 3. The `validate` flow (deterministic)

```
validate(execution_result, work_package, *, events, policy):
  emit validation.started
  evidence   = collector.collect(result, events)          → emit validation.evidence_collected
  for rule in DEFAULT_RULES:
      rule_result = rule.evaluate(context)                 → emit validation.rule_evaluated
  decision   = evaluator.evaluate(rule_results)            # verdict + confidence + trace
  report     = build immutable ValidationReport(...)       # references evidence, never duplicates
  emit validation.completed  (non-Failed)  |  validation.failed  (Failed)
  persist(report, evidence)
  return report
```

Every id (`vr-…`, `ev-…`, `evt-…-val-…`) is a pure function of the execution session
identity; timestamps are injected. Given identical evidence and rules, the report and event
stream are **byte-identical** (doc 14 *Deterministic*, INV-16/17) — proven in
`test_engine.py::test_two_runs_produce_identical_reports_and_events` and the E2E determinism
test.

## 4. Boundaries honored (doc 14)

Validation **judges** and nothing else: it never executes, retries, recovers, plans,
creates context, mutates artifacts, or invokes AI/LLM judges. No heuristics — every verdict
is a deterministic function of evidence with a recorded rationale (INV-31).

## 5. Test & quality results

| Gate | Result |
|---|---|
| `nexus_validation` unit suite | 67 tests |
| Coverage (`nexus_validation`) | **100.0%** (branch) |
| Full suite | **1957 passed, 1 skipped** |
| `mypy --strict` | clean (155 files) · `ruff` clean |
| Prior phases (incl. Runtime/Execution) | pass unchanged |
