# Lessons Learned — did the architecture survive first contact?

The objective was not feature completeness; it was to prove that Nexus' Runtime
architecture survives first contact with a real execution runtime. **It did — with no
architectural change.** Below: assumptions that held, assumptions that needed engineering
refinement, and the (zero) architectural conflicts.

---

## 1. Assumptions that proved correct

- **The nine-concern adapter contract (`03`) is sufficient and closed.** Claude Code mapped
  onto all nine concerns with no tenth concern and no special case. A real runtime did not
  need a bespoke RM or engine path.
- **The conceptual contract materializes cleanly into code.** Turning doc `03`'s prose into a
  `typing.Protocol` required only engineering decisions; the engine stayed provider-blind
  (`isinstance(adapter, RuntimeAdapter)` and nothing more).
- **"RM prepares; the engine performs" is a real, clean seam.** The `Ready` `RuntimeSession`
  was a complete, sufficient handoff. The engine needed only the session + the (by-value)
  Work Package + an adapter — no reach-back into RM internals.
- **The lifecycle (`07`) and event taxonomy (`15`) already covered execution.** The states and
  events the engine needed were *canon*, merely deferred in code. Realizing them added no new
  state or event — the strongest possible evidence the architecture anticipated execution.
- **ADR-001 holds across the whole lifecycle.** Folding the full preparation+execution event
  stream reproduces `Destroyed` deterministically. Session state genuinely is a projection.
- **Determinism is achievable with a real runtime shape.** A deterministic invoker behind the
  real adapter seam produced byte-identical event streams across runs — the program's
  determinism requirement met without pretending the model is deterministic.
- **The transport/semantic split (`22` §3, `23`) is the right factoring.** Separating the
  Claude *wire* (invoker) from the adapter's *semantic normalization* made the CLI vs. stub
  swap trivial and kept the mapping honest.
- **Evidence-by-reference (INV-12/ADR-003) is practical.** Emitting artifacts and captured
  output by reference (not content) was natural, not a burden.

## 2. Assumptions that required engineering refinement

- **The adapter contract was conceptual — the *seam* had to be invented.** Doc `03` left the
  method list open by design; we had to choose a concrete Protocol, a signal model, and the
  cancel/timeout mechanism. Correct, but it is engineering the architecture deliberately
  deferred, not something the docs handed us.
- **Teardown terminal state for executed sessions.** Phase-8A modelled `Released` as a
  preparation-abandon *state*, while doc `07` treats `runtime.released` as an *event* within
  teardown and `Destroyed` as the terminal *state*. We resolved by keeping `Released` for the
  never-ran path and using `Destroyed` for the executed path — and surfaced that returning an
  executed session's *capacity* needs a small RM affordance (emit `runtime.released` without
  forcing the `Released` state). A documented follow-up, not a blocker.
- **Timeout needed a deterministic model.** Wall-clock timeouts break reproducibility, so the
  minimal engine models the `10` bound as a per-signal `deadline_steps`. Production keeps the
  same semantics with a real clock; the test path stays deterministic.
- **Suspend/resume deferred, honestly.** `Paused`/`Waiting` are canon but out of the minimal
  engine's scope; we kept them unimplemented rather than adding unexercised vocabulary.

## 3. Architectural conflicts encountered

**None.** No implementation step required modifying Planning, Orchestration, Harness, the
Runtime architecture, an ADR, a contract, or an invariant. No `ARCHITECTURAL_CONFLICT_<N>.md`
was produced. The one seam friction (capacity release for executed sessions) is a future
engineering affordance the architecture already accommodates (`07` §6 separates the
`runtime.released` event from the teardown state), not a redesign.

## 4. Validation checklist — status

| Requirement | Result |
|---|---|
| Runtime architecture unchanged | ✓ (docs `00`–`24` untouched) |
| No contracts / ADRs / invariants change | ✓ |
| RM Manager contains zero Claude-specific code | ✓ (asserted in code) |
| Claude adapter contains all provider-specific behavior | ✓ (asserted in code) |
| Runtime lifecycle follows the frozen specification | ✓ (realizes deferred `07`/`15` canon) |
| Event stream is deterministic | ✓ (identical across runs under a fixed clock) |
| Execution artifacts conform to Runtime contracts | ✓ (Evidence Candidates by reference) |
| Existing phases pass unchanged | ✓ (1881 passed; only the 4 M1′ canon assertions updated) |

## 5. Recommended next steps (engineering, not architecture)

1. Add the RM capacity-release affordance for executed sessions (§2) so `runtime.released`
   can accompany `Destroyed`.
2. Realize `Paused`/`Waiting` + their events when a scheduling/approval phase needs them.
3. Add a second adapter (Shell or Gemini) to re-confirm the engine stays generic — expected
   to be a new package + a registration, with zero engine change.
4. Broaden M4 into a full Goal→Harness→Runtime integration once the upstream pipeline is
   wired end-to-end.
