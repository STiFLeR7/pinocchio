# Reflection Report — structure & traceability

Milestone 3. A `ReflectionReport` is the Reflection Engine's immutable output — the
deterministic analytical summary of one operational window. It is a Reflection-layer value
object (the pattern of the Runtime Session / Execution Result / Validation Report / Recovery
Plan), not a frozen core contract. It **references existing objects by id and never duplicates
them** (INV-12, ADR-003).

---

## 1. Structure

| Field | Purpose |
|---|---|
| `identity` | `rr-{scope}` — deterministic |
| `scope` | the operational window analysed |
| `stage` | `ReflectionStage` — `COMPLETED` (history reflected) or `FAILED` (no history) |
| `confidence` | overall `ConfidenceLevel`, derived from the number of operations |
| `correlation_identifier` | shared operation lineage (INV-39) |
| `episode_count` | how many operations were reflected on |
| `execution_summary` | totals: `total` / `succeeded` / `failed` / `by_runtime` (+ window metrics) |
| `validation_summary` | `validated` + `by_decision` counts |
| `recovery_summary` | `recovered` + `by_decision` + `retry_eligible` counts |
| `patterns` | the detected `OperationalPattern`s (each references its episodes) |
| `confirmed_observations` | descriptions of patterns corroborated ≥ twice |
| `knowledge_candidates` | advisory `KnowledgeCandidate`s (INV-25 — candidates, not Knowledge) |
| `recommendations` | the candidate summaries (advisory) |
| `evidence_refs` | the de-duplicated references to every reflected operation |
| `reasoning_trace` | one line per pattern — the explainability record (INV-31) |
| `reflector` / `timestamp` | provenance (`nexus_reflection`) + recorded time (INV-17) |

`is_empty` (episode_count is 0) is a convenience property.

## 2. Traceability (references, not copies)

```
ReflectionReport ──patterns[].evidence_refs──▶ RecoveryPlan / ValidationReport / ExecutionResult ──▶ Evidence / runtime.* events
       │  evidence_refs (deduped union of the above)                                                          │
       │  knowledge_candidates[].source_pattern_ref ──▶ OperationalPattern                                    │
       └────────────────────────────────── same correlation_identifier ───────────────────────────────────┘
```

The report never contains an Execution Result, a Validation Report, a Recovery Plan, Evidence,
or artifact bytes — only `Reference`s. To inspect any of them, a consumer resolves the
reference against the repositories / event store. This keeps reports small, immutable, and
auditable, and satisfies "reports reference existing artifacts; never duplicate them."

## 3. Operational insights

The report answers doc-26's reflection questions deterministically, from evidence alone:

- **What happened?** — the execution / validation / recovery summaries.
- **What worked / failed?** — `repeated_success` / `repeated_failure` patterns.
- **Where is the friction?** — the `bottleneck` and `retry_frequency` patterns.
- **What should change?** — the advisory `knowledge_candidates` (only from *confirmed,
  actionable* patterns — doc 26 *Actionable*; INV-25), each carrying a confidence so Knowledge
  can prioritise.

Knowledge Candidates are **advisory until accepted** (INV-25): Reflection produces them; a
future Knowledge subsystem decides what becomes persistent. Reflection persists the Report and
Patterns, never the Candidates as Knowledge.

## 4. Determinism

Every field is a pure function of the collected history and the injected timestamp. Two
reflections of identical history produce an **equal** report object (`test_engine.py::
test_two_runs_produce_identical_reports_and_events`).
