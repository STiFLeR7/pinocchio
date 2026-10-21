# H-4 — Pilot Risk Plan (Nexus Experimental → Pilot)

> **Planning only — no implementation.** Consolidated risk register, mitigations, rollback triggers, and
> sequencing guards for the H-4 Pilot work. Companion to `H-4-execution-roadmap.md`. Built on H-2 freeze
> `d6bd75d` (tag `hermes-experimental`).

---

## 1. Risk register (by step)

| Step | Item | Risk | Primary hazard | Mitigation |
|---|---|---|---|---|
| 1 | fail-fast init | 🟢 Low | a test relied on key-less execution | H-2 tests inject fakes → unaffected; verify before changing |
| 2 | configurable budget | 🟢 Low | default drift | additive field, default 5 preserved + asserted |
| 3 | `terminate()` | 🟠 Medium | async cancellation deadlock / forced kill | cooperative only; checks at state boundaries; reuse sandbox terminate |
| 4 | cancellation wiring | 🔴 Med–High | orchestrator regression | **only orchestrator touch**; single invocation point; e2e guard; isolated step |
| 5 | `TIMED_OUT` lifecycle | 🟠 Low–Med | finalization-mapping mismatch | additive `ExitStatus`; fall back to FAILURE mapping; tests assert distinct terminal |
| 6 | `resume_goal()` | 🟠 Low–Med | duplicate/incorrect resume cursor | `step_index = max+1`; idempotency test; fail-closed on inconsistency |
| 7 | audited real run | 🟢 Low | provider/env availability | gate on a real `SearchProvider`/LLM; document if unavailable |

## 2. Cross-cutting risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Schema creep (new column/table for cancel signal or status) | Medium | High (violates "no migrations") | Use **existing** `ExecutionRecord` status/flag + existing `ExecutionStatus.TIMED_OUT`/`CANCELLED`; any `ExitStatus` value is additive, impl-AP-decided |
| Hidden coupling orchestrator↔adapter | Medium | Medium | DB-observable cancel signal (Rule 5/9), not an in-memory back-channel |
| Regressing H-2 honesty guarantees | Low | High | H-2 guard tests (`test_no_unittest_mock_import_in_runtime`, exit-status tests) run every step |
| Regressing Track-S sandbox containment | Low | High | no changes to `confinement.py`/`manager.py`/`provider.py`; `execute_command`/file tools untouched |
| Cancellation latency unbounded | Low | Medium | observe signal at state boundaries → ≤ one tool execution; test asserts bound |
| Resume masks data loss by restarting fresh | Low | High | resume **fails closed** on missing/inconsistent data; never silent restart |

## 3. Rollback strategy (per step) & triggers

| Step | Rollback | Trigger to roll back |
|---|---|---|
| 1 | revert `initialize()` to no-op (1 hunk) | unexpected construction-time failures in unrelated suites |
| 2 | remove config read + additive field | budget default regression |
| 3 | `terminate()` → `pass`; remove boundary checks (logic-only) | loop deadlock / flaky cancellation tests |
| 4 | remove the single orchestrator `terminate()` invocation | any e2e/orchestrator regression (`test_mvp_workflow`) |
| 5 | revert timeout branch → H-2 honest `exit_code 1/failed` | finalization-mapping breakage |
| 6 | remove `resume_goal` + optional contract method (pure addition) | resume idempotency failure |
| 7 | n/a (evidence artifact) | — |

**General rollback property:** every H-4 step is **additive or logic-only** with no migration, so each
step reverts to the previous green state by reverting its own hunk(s). Steps 3 and 4 are split precisely
so the orchestrator change can be reverted independently of the cancellation mechanism.

## 4. Sequencing guards (do-not-proceed conditions)

- Do not start **step 4** (orchestrator wiring) until **step 3** (`terminate()` mechanism) is green and
  tested in isolation.
- Do not start **step 5** (`TIMED_OUT`) until **step 2** (budget) is in place.
- Do not start **step 7** (audited run) until steps 1–6 are green and a real provider is available.
- Abort the step and roll back if the full suite, ruff, or mypy is not green, or if any H-2 guard test or
  Track-S sandbox test regresses.

## 5. Quality gates per step (every step)

`pytest` full suite green (≥ 194 + new) · `ruff check nexus/ tests/` clean · `mypy nexus/` clean · zero
regressions in CLI runtimes, sandbox (S-2/S-3/S-4), governance, scheduler, e2e · H-2 honesty guards green.

## 6. Residual / accepted risk for Pilot

- Cancellation latency is bounded to one tool execution (cooperative model) — accepted; forced kill is
  out of scope.
- Auto-resume (orphan-triggered) is **P2** — Pilot ships resume as *invocable* only; an un-monitored
  orphaned run still requires operator/orchestrator-initiated resume.
- In-container file I/O ceiling (R-05) is **P2** — the host-side workspace floor (S-4) already prevents
  escape.

## 7. Status

Risk plan only. No code, no migration, no commit of implementation. H-4 is **gated**; nothing here
authorizes implementation.
