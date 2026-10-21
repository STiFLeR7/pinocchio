# Validation Rules & Decision Model — implementation

Milestone 2. Rules are deterministic, evidence-driven, and explainable — **no AI, no
heuristics** (doc 14 *Deterministic* / *Evidence Driven*). Each rule is a pure function of
the collected Evidence and the Work Package's completion criteria, returning a `RuleResult`
with a canonical `RuleOutcome` and a rationale (INV-31).

---

## 1. Decision vocabulary (doc-14 canon)

The frozen architecture fixes four outcomes. The program prompt's informal labels map 1:1:

| Doc-14 canon (used) | Prompt label |
|---|---|
| **Passed** | Success |
| **Failed** | Failure |
| **Partial** | Partial Success |
| **Requires Review** | Inconclusive |

`RuleOutcome` (per rule): `SATISFIED`, `VIOLATED`, `INSUFFICIENT_EVIDENCE`, `NOT_APPLICABLE`.

## 2. The default rules

| Rule id | Satisfied when | Violated when | Insufficient when |
|---|---|---|---|
| `process_outcome` | outcome COMPLETED | outcome FAILED | outcome CANCELLED (undetermined) |
| `exit_status` | exit `0` or absent | non-zero exit | — |
| `error_absence` | no `error_class` | a typed error present | — |
| `completion_criteria` | explicit criteria met | required artifact / min-count unmet | criteria present but not deterministically evaluable |
| `artifact_corroboration` | ≥1 independent artifact | — | **no independent artifact corroborates a clean run (INV-20)** |

`completion_criteria` is `NOT_APPLICABLE` when the Work Package specifies none;
`artifact_corroboration` is `NOT_APPLICABLE` when policy disables it (`ValidationPolicy`).

## 3. The INV-20 policy (ratified decision)

A runtime "Completed" self-report is **never sufficient**. The corroboration rule requires
an *independent* artifact (read from the event log) before a clean run can pass. With no
explicit completion criteria:

- Completed + exit 0 + no error + **≥1 artifact** → **Passed**;
- Completed + exit 0 + no error + **0 artifacts** → **Partial** (not Passed).

## 4. Aggregation precedence (`DecisionEvaluator`)

Deterministic, top-to-bottom:

1. any **hard-rule** (`process_outcome` / `exit_status` / `error_absence`) `VIOLATED` → **Failed**
2. `process_outcome` `INSUFFICIENT` (cancelled) → **Requires Review**
3. `completion_criteria` `VIOLATED` → **Partial**
4. `completion_criteria` `INSUFFICIENT` → **Requires Review**
5. `artifact_corroboration` `INSUFFICIENT` → **Partial**
6. otherwise → **Passed**

## 5. Confidence (deterministic)

`confidence = satisfied / applicable`, where *applicable* excludes `NOT_APPLICABLE` rules
(rounded to 4 dp). It is an explainable "evidence-corroboration strength": a fully-satisfied
clean run is `1.0`; a run with violations is proportionally lower. Doc 14 lists richer
confidence scoring as *future evolution*; this deterministic measure is the current form.

## 6. Explainability (INV-31)

Every verdict carries a `reasoning_trace` (one line per rule: `id: outcome — rationale`),
plus `satisfied_requirements`, `failed_requirements`, `missing_evidence`, and
`recommendations`. The four "why" questions of doc 14 (what was evaluated / which satisfied
/ which failed / why the verdict) are all answerable from the Report alone.

## 7. Extensibility

New rules are new `ValidationRule` implementations added to `DEFAULT_RULES` (or a custom
tuple passed to `ValidationEngine`); `ValidationPolicy` toggles requirements. No engine or
evaluator change is needed for a new rule that returns the canonical `RuleOutcome`.
