# Validation Report — structure & traceability

Milestone 3. A `ValidationReport` is the Validation Engine's immutable output — the doc-14
report contents plus a reasoning trace and the evaluated rule results. It **references
Evidence by id and never duplicates artifacts** (INV-12, ADR-003). It is a Validation-layer
value object (the pattern of the Runtime Session / Execution Result), not a frozen core
contract.

> Naming note: distinct from `nexus_core.validation.ValidationReport`, which is the
> *contract-validation* framework's report. Different namespace, different concern.

---

## 1. Structure

| Field | Purpose |
|---|---|
| `identity` | `vr-{session}` — deterministic |
| `decision` | `ValidationDecision` (Passed/Failed/Partial/Requires Review) |
| `stage` | `ValidationStage` projection of the decision |
| `confidence` | deterministic evidence-corroboration strength `[0,1]` |
| `session_ref` / `work_package_ref` / `execution_result_ref` / `runtime_ref` | the judged execution, **by id** |
| `correlation_identifier` | shared operation lineage (INV-39) |
| `evidence_refs` | Evidence **by reference** — never embedded |
| `rule_results` | each `RuleResult` (id, outcome, rationale, evidence refs) |
| `satisfied_requirements` / `failed_requirements` / `missing_evidence` | doc-14 satisfied/failed requirements + missing evidence |
| `recommendations` | deterministic next steps for non-Passed verdicts |
| `reasoning_trace` | one line per rule — the explainability record (INV-31) |
| `observations` | evidence-by-source counts |
| `validator` / `timestamp` | provenance (`nexus_validation`) + recorded time (INV-17) |

## 2. Decision model

The decision, confidence, and requirement lists come entirely from the deterministic
`DecisionEvaluator` (see `VALIDATION_RULES.md` §4–5). `decision → stage` is a fixed map.
`passed` is a convenience property (`decision is Passed`) — a *validated* outcome (INV-20),
never a runtime self-report.

## 3. Traceability (references, not copies)

```
ValidationReport ──evidence_refs──▶ Evidence ──derived_from──▶ runtime.* events / ExecutionResult
       │  rule_results[].evidence_refs                                    │
       └──────────────────────── same correlation_identifier ────────────┘
```

The report never contains artifact bytes or Evidence objects — only `Reference`s. To inspect
an artifact or the source events, a consumer resolves the reference against the repositories
/ event store. This keeps reports small, immutable, and auditable, and satisfies "reports
reference evidence; they do not duplicate artifacts."

## 4. Determinism

Every field is a pure function of `(execution_result, work_package, events, policy)` and the
injected timestamp. Two validations of identical inputs produce an **equal** report object
(`test_engine.py::test_two_runs_produce_identical_reports_and_events`).
