# Lessons Learned — Validation Engine

The objective: make Nexus able to decide, from **deterministic evidence alone**, whether an
execution achieved its outcome — so execution is no longer the terminal stage. **Achieved,
with no architectural change.** No `ARCHITECTURAL_CONFLICT_<N>.md` was produced.

---

## 1. Assumptions validated

- **The frozen Validation architecture (doc 14) is implementable as-is.** Its decision
  vocabulary, evidence properties, report contents, and boundaries mapped directly to code.
- **INV-12/INV-20 are the right spine.** Treating Execution's outputs as *Evidence
  Candidates* and demanding independent corroboration before "Passed" produced a governance
  model that never rubber-stamps a runtime self-report — the AP-502 evidence-insufficiency
  case falls out naturally (a clean run with zero artifacts is Partial, not Passed).
- **The layer-output pattern generalizes.** Evidence and the Validation Report are
  Validation-owned value objects (no frozen core contract), exactly like the Runtime Session
  and Execution Result. The pattern held a third time without friction.
- **Reserved event namespaces were sufficient.** `validation.*` (doc 15 §4 / doc 23) needed
  no new architectural event; the `-val-` id marker keeps them collision-free in the shared,
  correlated store.
- **Determinism is achievable for judgement, not just execution.** With injected timestamps
  and pure-function rules/ids, identical evidence yields byte-identical reports and event
  streams — the program's headline requirement.
- **Phase-2 reuse held.** Emitter, `InMemoryRepository`, and observability were reused
  unchanged; Validation invented no substrate.

## 2. Assumptions refined (engineering, not architecture)

- **Vocabulary: canon over prompt.** The program prompt's labels (Success / Failure /
  Partial Success / Inconclusive) differ from doc-14's (Passed / Failed / Partial / Requires
  Review). We used **canon** and documented the 1:1 mapping — the right call, ratified before
  building.
- **"Independent" evidence needed a concrete source.** Doc 14's "never rely solely on
  execution output" became a concrete decision: artifact Evidence is read from the
  `runtime.artifact_emitted` **event log**, not from `ExecutionResult.artifact_refs`, so the
  corroboration rule rests on the append-only record rather than a self-populated field.
- **Confidence is deliberately simple.** Doc 14 lists confidence scoring as *future
  evolution*, so we shipped a deterministic, explainable "fraction of applicable rules
  satisfied" rather than inventing a richer model now.
- **Human/hybrid validation deferred.** Doc 14's `Waiting Human Review` / `Cancelled`
  lifecycle states and human validators are out of the deterministic automated scope; the
  automated engine reaches `Requires Review` (the decision) and stops. The human *workflow*
  is a later phase.

## 3. Implementation observations

- The engine's `events` parameter shadowed the `events` module — resolved by importing the
  module as `vevents`. A small naming clash worth noting for the next layer.
- `ExecutionResult` has no `identity`; the runtime **session identity** is the natural
  stable scope for all validation ids (one attempt → one session → one report).
- Rules stayed *total* (never raise) — so `validation.failed` cleanly means "the **verdict**
  is Failed," not "the validation process errored." If a future rule can fail internally,
  that distinction may need a separate error path.

## 4. Success criteria — status

| Criterion | Result |
|---|---|
| Determine outcome from deterministic evidence alone | ✓ |
| Identical execution results → identical reports | ✓ (`test_two_runs…`, E2E determinism) |
| Validation never mutates artifacts / execution / runtime | ✓ (append-only + dependency guardrails) |
| Evidence is traceable; reports reference (not duplicate) evidence | ✓ |
| All decisions explainable | ✓ (`reasoning_trace`, INV-31) |
| Runtime / Execution / ADRs / contracts / invariants unchanged | ✓ |
| Execution is no longer the terminal stage | ✓ — Validation is the first post-execution governance layer, and the foundation for Recovery / Reflection / Knowledge |

## 5. Recommended next steps (engineering)

1. Add domain/quality rules that read richer `completion_criteria` shapes (tests, builds,
   review gates) — new `ValidationRule`s, no engine change.
2. Realize the human-review workflow (`Waiting Human Review` / `Cancelled`) when an approval
   phase needs it.
3. Wire Recovery to react to `validation.failed` / `Partial` (a later program) — Validation
   already emits the events and verdict it needs.
