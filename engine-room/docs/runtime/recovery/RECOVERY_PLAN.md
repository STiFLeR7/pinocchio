# Recovery Plan — structure & traceability

Milestone 3. A `RecoveryPlan` is the Recovery Engine's immutable output — the governed
decision plus the deterministic derivation that produced it. It **references existing objects
by id and never duplicates them** (INV-12, ADR-003): the triggering Validation Report, the
Execution Result, the Evidence, and any checkpoint are all carried as `Reference` values,
never embedded. It is a Recovery-layer value object (the pattern of the Runtime Session /
Execution Result / Validation Report), not a frozen core contract.

---

## 1. Structure

| Field | Purpose |
|---|---|
| `identity` | `rp-{session}` — deterministic |
| `decision` | `RecoveryDecision` (Complete / Retry / Resume / Escalate / Await Approval / Abort) |
| `stage` | `RecoveryStage` projection of the decision |
| `failure_category` | the classified `FailureCategory` (doc 19) |
| `session_ref` / `work_package_ref` | the recovered work, **by id** |
| `validation_report_ref` / `execution_result_ref` / `runtime_ref` | the inputs, **by id** |
| `correlation_identifier` | shared operation lineage (INV-39) |
| `triggering_evidence_refs` | the Validation Report's Evidence, **by reference** — never embedded |
| `checkpoint_ref` | the checkpoint a Resume restores from (set only when resumable) |
| `escalation_target` | the target for Escalate / Await Approval |
| `rule_results` | each `RecoveryRuleResult` (id, outcome, proposed decision, rationale) |
| `required_actions` | the governed next steps for the decision |
| `recommendations` | deterministic operator guidance |
| `reasoning_trace` | one line per rule — the explainability record (INV-31) |
| `retry_eligible` / `retry_policy` / `attempts_used` / `attempts_remaining` | the retry basis |
| `resumable` | whether progress-preserving resume was available |
| `planner` / `timestamp` | provenance (`nexus_recovery`) + recorded time (INV-17) |

`recovered` (decision is Complete) and `aborted` (decision is Abort) are convenience
properties.

## 2. Traceability (references, not copies)

```
RecoveryPlan ──validation_report_ref──▶ ValidationReport ──evidence_refs──▶ Evidence ──▶ runtime.* events
      │  triggering_evidence_refs (same Evidence, by id)                                      │
      │  execution_result_ref ──▶ ExecutionResult                                             │
      │  checkpoint_ref ──▶ Checkpoint (Execution creates; Recovery restores — doc 25)        │
      └────────────────────────── same correlation_identifier ─────────────────────────────┘
```

The plan never contains a Validation Report, an Evidence object, artifact bytes, or checkpoint
state — only `Reference`s. To inspect any of them, a consumer resolves the reference against
the repositories / event store. This keeps plans small, immutable, and auditable, and
satisfies "Recovery Plans reference existing artifacts; never duplicate them." Validated
evidence is preserved, never discarded (INV-22).

## 3. Policy integration

The retry basis on the plan (`retry_eligible`, `retry_policy`, `attempts_used`,
`attempts_remaining`) and the escalation target are read directly from the `RecoveryPolicy`
bundle the decision ran under — Recovery is *strategy driven* (doc 19), so the plan records the
policy inputs its decision rests on, making the decision reproducible and auditable.

## 4. Determinism

Every field is a pure function of `(validation_report, execution_result, policy, attempt,
checkpoint)` and the injected timestamp. Two recoveries of identical inputs produce an
**equal** plan object (`test_engine.py::test_two_runs_produce_identical_plans_and_events`).
