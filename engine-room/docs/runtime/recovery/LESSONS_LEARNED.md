# Lessons Learned — Recovery Engine

The objective: make Nexus deterministically determine the correct governed response to every
Validation outcome **without executing work itself** — establishing the second governance
layer of the control plane. **Achieved, with no architectural change.** No
`ARCHITECTURAL_CONFLICT_<N>.md` was produced.

---

## 1. Assumptions confirmed

- **The frozen Recovery architecture (doc 19) is implementable as-is.** Its failure
  categories, strategies, retry policies, and boundaries mapped directly to code.
- **INV-21 is the right spine.** "Execution exposes outputs/failures; Validation decides
  completion; Recovery decides continuation" gave the layer a crisp remit: Recovery reaches a
  *decision stage* and stops. It never restores, retries, or plans — those belong to the actor
  that performs the action.
- **INV-22 falls out naturally.** Recovery references (never discards) validated evidence, and
  the Approval rule means governance is never bypassed. Abort preserves evidence rather than
  restarting from the Goal.
- **The layer-output pattern generalises a fourth time.** The Recovery Plan is a
  Recovery-owned value object (no frozen core contract), exactly like the Runtime Session,
  Execution Result, and Validation Report. The pattern held without friction.
- **Reserved event namespaces + id markers scale.** `recovery.*` needed no new architectural
  event; the `-rec-` id marker keeps recovery events collision-free alongside `runtime.*` and
  the validation `-val-` marker in the shared, correlated store.
- **Determinism is achievable for a decision layer.** With injected timestamps and
  pure-function rules/ids, identical inputs yield byte-identical plans and event streams — the
  program's headline requirement.

## 2. Implementation refinements (engineering, not architecture)

- **Decision scope: prompt subset of doc-19 strategies.** The program fixes six decisions
  (Complete / Retry / Resume / Escalate / Await Approval / Abort); doc 19 lists more (Rollback,
  Switch Runtime, Request Context) plus Replan. We implemented the subset and documented the
  1:1 mapping and the deferrals in `RECOVERY_DECISIONS.md`. Deferred strategies route honestly
  to `Escalate` today rather than being silently synthesised.
- **"Continuation" needed concrete inputs.** Recovery decides from the *Validation Report*
  (verdict, confidence, evidence refs) plus the *Execution Result* (typed doc-11 error) — the
  report is primary; the result supplies the failure classification. This keeps Recovery
  cleanly downstream of Validation.
- **Failure classification is a total, deterministic map.** doc-11 `error_class` / `owner` →
  doc-19 `FailureCategory`, with a Validation-failure fallback when there is no typed execution
  error. `CONTEXT` / `DEPENDENCY` exist in the vocabulary but are not synthesised from the
  current signals — a clean extension point, not a gap in the decision surface.
- **Resume outranks Retry.** doc-19 *Progress Preservation* ("never repeat completed work")
  made the precedence choice: a Partial verdict with a valid checkpoint resumes rather than
  re-runs. Retry is the fallback when no checkpoint exists.
- **`recovery.completed` vs `recovery.failed`.** Mirrored Validation's convention: `failed`
  means the *decision* is Abort (no governed continuation exists), not that the recovery
  *process* errored. Rules stayed total (never raise), so the process itself cannot fail —
  a future rule that can fault internally would need a separate error path.
- **Attempt history is an input.** The engine takes `attempt` as a parameter (the orchestrator
  owns execution history) — consistent with Recovery being a pure decision function, not a
  stateful counter.

## 3. Future integration points

1. **Replan** — a seventh decision + rule, wired to Planning (the reserved slot). Recovery
   would propose a replan; Planning performs it. No engine change beyond a new rule + precedence
   entry.
2. **Rollback / Switch Runtime / Request Context** — the remaining doc-19 strategies as new
   rules over richer signals (domain support, runtime health, context validity).
3. **Checkpoint discovery** — today `checkpoint_ref` is supplied; when Execution emits
   `runtime.checkpoint_captured` (deferred in the runtime slice), Recovery can discover the
   latest valid checkpoint from the log itself.
4. **Reflection / Knowledge** — successful and failed recovery patterns feed operational
   knowledge (doc 19 *Relationship with Knowledge*), influencing future Execution Strategies.
   Recovery already emits the events and plan those layers would consume.

## 4. Success criteria — status

| Criterion | Result |
|---|---|
| Determine the correct governed response to every Validation outcome | ✓ |
| Recovery consumes Validation only; never executes | ✓ (decides continuation; INV-21) |
| Validation / Runtime / Execution unchanged | ✓ (append-only + dependency guardrails) |
| Recovery Plans immutable; reference (not duplicate) artifacts | ✓ (INV-12) |
| Decisions deterministic; identical reports → identical plans | ✓ (determinism tests) |
| Rules explainable | ✓ (`reasoning_trace`, INV-31) |
| ADRs / contracts / invariants unchanged | ✓ |
| Second governance layer established between Validation and future actions | ✓ |
