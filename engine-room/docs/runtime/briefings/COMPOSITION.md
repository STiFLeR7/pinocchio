# Composition (Milestone 3)

The `BriefComposer` reads a `WorkflowRun` and reorganizes it into a `Brief`. Its single rule:

> Compose briefings from **validated artifacts, recovery outcomes, reflection reports, and
> knowledge items**. **Never consume raw runtime output directly.**

## What a composed section carries

For each declared section the composer produces a `BriefSectionView`:

| Field | Source | Governance |
|---|---|---|
| `decision` | the section's Validation verdict | the existing Validation engine (INV-20) |
| `validated_artifacts` | the produced deliverable, **gated on `decision == "passed"`** | withheld unless validated |
| `evidence_refs` | the Validation stage's independently collected evidence | proof, not self-report |
| `recovery_decision` | the section's governed Recovery decision | the existing Recovery engine |

The `Brief` then adds the Reflection findings (`reflection_candidates`), the persisted Knowledge
(`knowledge_item_ids`), and the Knowledge consumed this generation.

## Never raw runtime output

Two mechanisms enforce the rule, both in `composer.py`:

1. **The runtime's captured-output stream is excluded.** Every execution stage emits a
   `…-captured-output` artifact — the raw stdout capture. `_is_raw_output` filters it out, so it
   can never reach a brief. The end-to-end test asserts no composed artifact contains
   `captured-output`.
2. **Deliverables are gated on the Validation verdict.** A section surfaces its deliverable
   artifact only when its Validation decision is `passed`. On a failed generation every section is
   withheld (`validated_artifacts == ()`) even though the runtime "produced" a file — nothing
   unvalidated is ever composed (`test_failed_generation_withholds_the_brief_and_recovers`).

The composer holds **no** validation, recovery, reflection, or knowledge logic — it only *projects*
what those engines already decided.

## Correlation is by node, not by index

For one run the execution, validation, and recovery stages appear in **session order**
(e.g. `compare-findings` before `gather-sources`), which is *not* the declared section order, and
`validation_decisions` / `recovery_decisions` are index-aligned to that same session order. The
composer therefore keys everything on the node id (`validation:node-survey-signals` → the
`survey-signals` section), pairs each validation stage with its execution stage by node, and reads
the decision at the matching index. Sections are then emitted in the `BriefType`'s declared order
for a stable document. A declared section with no matching node (e.g. composing an operational
digest over a research run) is reported `absent` and withheld, never fabricated
(`test_absent_sections_are_withheld_when_the_run_lacks_them`).

## Brief-level verdicts

* `is_validated` — every section passed Validation.
* `recovered` — any section needed a governed continuation other than `complete`.
* `is_publishable` — validated **and** every section carries a validated deliverable. This is the
  gate a delivery surface checks before sending a brief.
