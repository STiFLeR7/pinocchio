# Validation & Recovery Flow — Implementation

Milestones 4 & 5: research outputs are never trusted automatically — every stage passes through the
existing Validation engine, and injected failures drive the existing Recovery engine to its
governed continuations.

## Milestone 4 — no output is trusted automatically

The research workflow reuses the pipeline's Validation stage unchanged: for each research Work
Package, the existing Validation engine judges the `ExecutionResult` against the package and emits a
`ValidationReport` with independently collected Evidence (INV-20 — completion derives from Evidence,
never runtime self-report). The `ResearchBrief` surfaces this:

* `validation_decisions` — the verdict per research stage;
* `evidence_refs` — the Validation evidence collected (drawn from the Validation stages of the
  timeline, kept distinct from the produced deliverables);
* `is_validated` — true only when **every** stage passed.

On the happy path all four research stages pass and the brief is `is_actionable`
(`test_research_produces_an_actionable_validated_brief`).

## Milestone 5 — failure injection and governed recovery

### Live retry (end-to-end)

Running the research workflow with the failing runtime path (`fail=True`) exercises the real
Recovery engine end to end: each stage's execution fails, Validation returns `failed`, and Recovery
decides `retry` — surfaced as `recovery_decisions == ("retry", …)` and `brief.recovered is True`
(`test_failed_research_run_recovers_via_retry`). This is the autonomous failure path, not a
simulation.

### Retry / escalation / resume via the existing engine

`recovery_outlook(report, result)` drives the existing `RecoveryEngine` over the three
research-relevant failure conditions and reports which governed continuation it reaches:

| Injected condition | Existing engine's decision |
|---|---|
| fresh failure, budget remaining | **retry** |
| same failure, retry budget exhausted (`attempt == max_attempts`) | **escalate** (the safe floor) |
| partial progress with a valid checkpoint | **resume** (progress preservation, doc 19) |

Only the *conditions* are injected (attempt count, checkpoint, a partial verdict via a copied
report) — every decision is produced by the unmodified Recovery engine. Each hypothetical
evaluation runs on its own isolated event log (a throwaway `build_recovery` over fresh
infrastructure), so the probes neither collide with one another nor pollute the research run's real
log. `RecoveryOutlook.covers_all_governed_continuations` asserts all three are reached
(`test_recovery_offers_retry_escalation_and_resume`).

## Why this stays a consumer

Research decides no recovery and grades no output. Validation and Recovery are the existing engines'
responsibility; `nexus_research` only *invokes* them and *reports* their decisions. The failure
injection changes inputs (a failing adapter, an attempt count, a checkpoint), never engine code.
