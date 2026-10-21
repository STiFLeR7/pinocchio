# Phase 5 — Outcome-Linked Cross-Run Learning: Preregistered Gate

**Status:** frozen before Phase 5 implementation. [`cases.json`](cases.json) is the machine-readable contract. Do not relabel cases or lower thresholds to fit results.

## Product boundary

Reflection proposes, Knowledge accepts and serves, and Policy authorizes grounding. A `validation_report` reference counts as outcome support only when it resolves to a durable `PASSED` verdict for the source run and its referenced evidence can be traced. Failed, partial, and requires-review outcomes cannot be promoted as proven guidance. An absent report or a type-correct reference alone is insufficient. Accepted items retain source goal/run, validation report, evidence references, and attributable operator feedback where supplied. Knowledge remains read-only to later consumers; retrieval grants no action authority.

The fixture uses isolated, labeled source and second-run goals. For each case it records the source candidate→acceptance decision→item/version chain, lifecycle facts, Policy grounding decision, selected Knowledge IDs, Engineering and Context references, second-run plan fingerprint, validation verdict, and evidence references. Relevant cases compare an otherwise equivalent second run with and without the Knowledge item. The comparison reports observed plan and outcome differences without attributing causation to retrieval.

## Frozen 12-case retrieval set

Logical labels in `cases.json` resolve to actual Knowledge Subject Keys in the evidence manifest before assertion. Each case has its own controlled state, so exact-subject serving is not inflated by sharing an item across cases.

| ID | Registered condition | Expected surface |
| --- | --- | --- |
| R1 | Current accepted item, exact subject and kind, passed source verdict with evidence. | Relevant item |
| R2 | Current accepted item in the second goal's declared domain and applicability. | Relevant item |
| R3 | Latest evolved item retains two passing source verdicts and their evidence. | Relevant latest item |
| R4 | Accepted replacement explicitly supersedes an older item; query the replacement subject. | Replacement only |
| R5 | Passed source item has attributable positive operator feedback. | Relevant item with feedback provenance |
| R6 | Current in-scope item at the policy serving floor with a passed source verdict. | Relevant item |
| X1 | Matching candidate rejected because its source verdict failed or is unknown. | Nothing |
| X2 | Matching accepted item expired by recorded deterministic TTL maintenance. | Nothing |
| X3 | Matching item deprecated after attributable contradictory feedback. | Nothing |
| X4 | Old item explicitly superseded by an accepted replacement; query the old subject. | Nothing |
| X5 | Current accepted item has an unrelated subject, kind, domain, or applicability scope. | Nothing |
| X6 | Matching current accepted item but Knowledge-grounding Policy returns DENY. | Nothing |

## Pass thresholds and evidence

At least five of six R cases surface the labeled relevant item; none of X1–X6 surface an excluded item. No failed, partial, unknown, unresolved, or contradicted source outcome is promoted to `PROVEN` or served as validated guidance. All accepted relevant items carry source goal/run, report and evidence references; feedback used in a decision carries actor, event ID, and source-run attribution. Supersession, deprecation, expiry, and scope decisions are explicit and explainable.

The first and second run must use the operator-facing spine path for the comparison, with Planning/Validation facts and source references retained. For every relevant case record baseline and seeded second-run selected IDs, Engineering/Context influences, plan fingerprints, validation verdicts, and an observed-improved/same/worse/unknown comparison; make no causal claim. Fresh-process replay must reconstruct the same Knowledge item/version, selection and Context references from durable facts without a new retrieval/acceptance decision, model call, or lifecycle side effect. Retain the labeled cases, actual ID map, candidate-to-acceptance event chain, lifecycle and feedback events, per-case results, second-run comparison, replay trace, failure list, and evidence-class limitations. The strict full suite must pass with warnings as errors, live Claude smoke enabled, zero skips/warnings, followed by Ruff, mypy, build, and staged diff checks before commit.
