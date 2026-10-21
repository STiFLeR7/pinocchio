# ADR-hermes-experimental: Nexus Runtime Reclassified Prototype → Experimental

Date: 2026-06-24
Status: Accepted
Release: v1.1.0 "Containment" · Track H · H-2 closure
Supersedes (classification only): ADR-nexus-reality-audit ("Prototype")
Related: ADR-nexus-v1.1-foundation, ADR-sandbox-pilot-safe, ADR-v1.0.1-alignment-release,
`H-2-implementation-report.md`, `nexus-experimental-readiness.md`,
`nexus-experimental-closure-review.md`, `nexus-capability-upgrade.md`, `nexus-before-after.md`

---

## Context

`ADR-nexus-reality-audit` (Accepted, v1.0.1) classified Nexus a **Prototype**: real persistence,
governance, and file/command tools, but with an in-prod `AsyncMock`, a decorative hardcoded plan,
simulated `web_search`, always-`0` exit status, brittle action parsing, and absent lifecycle controls.
v1.1.0 Track H chartered an honest-first evolution (`ADR-nexus-v1.1-foundation`): **H-2 (P0)** delivers
the honesty fixes for the **Prototype → Experimental** gate; lifecycle safety (terminate/resume) is the
later **Pilot** bar.

H-2 was implemented under strict TDD and reviewed. First-hand evidence (re-verified live at this closure):

- **No production mock.** `AsyncMock`/`unittest.mock`/`is_mocked` are absent from `nexus.py` (grep +
  `test_no_unittest_mock_import_in_runtime`). Simulation lives only in injected test doubles.
- **Real search.** `SearchProvider` ABC (`search_provider.py`), constructor-injected; `web_search` calls
  it; canned text removed; no-provider → honest error (`test_web_search_uses_injected_provider`,
  `test_web_search_without_provider_is_honest_error`).
- **Goal-derived planning.** `_generate_plan(goal)` replaces the literal; plan reflects the goal
  (`test_plan_is_goal_derived_not_literal`).
- **Structured tool-calls.** `parse_tool_call` (`nexus_tools.py`); malformed → explicit FAILED, never a
  silent finish (`test_malformed_call_fails_not_silent_finish`).
- **Truthful exit status.** `exit_code = 0 if (finished and not failed) else 1`; failed steps persist
  `ExecutionStatus.FAILED`; the orchestrator (unchanged) finalizes FAILURE on non-zero
  (`test_failure_yields_nonzero_exit`).
- **Gates:** **194 passed** (178 → 194, +16), ruff clean, mypy clean (60 files), zero regressions.

## Decision

**Reclassify the Nexus runtime from Prototype to "Experimental."**

The five Prototype-defining defects are reversed in code with test + trace evidence; the sound skeleton
(governance gate, real persistence, registry/contract, Track-S-contained tools) is preserved. AP-105
ledger Caps 2, 3, 4, 8, 18 are reclassified ≥ Partially-Implemented with tests.

### Why Experimental and not Pilot

The Pilot gate additionally requires wired+tested cancellation (`terminate()`), working+tested
`resume_goal`, fail-fast init, a configurable budget, timeout lifecycle (`TIMED_OUT`), and one audited
real governed run — **none** delivered by H-2 (correctly out of P0 scope). These are the H-4 inventory.

## Conditions of the classification

1. **Experimental, not Pilot.** Nexus must not be represented as lifecycle-safe or resumable; Caps
   12/14/17/19 remain open.
2. **Effective on commit.** H-2 source is validated but **uncommitted** (HEAD `b734c13`); the
   classification is evidence-bound to that code and takes effect on commit to `v1.1.0-planning`.
3. **Production search** requires injecting a real `SearchProvider` whose egress is bound to the active
   sandbox network policy (`R-05-shared-resolution.md` §6); the default no-provider behavior is an honest
   error, never canned output.
4. The authoritative status row in `architecture-status-summary.md` (Nexus: 🔴 Mocked/Prototype → 🟡
   Experimental) is updated via a **separately authorized** documentation step — not by this ADR.

## Consequences

**Positive**
- Nexus is now *honest*: real decisions, real search, goal-derived plans, truthful outcomes — safe to
  represent as an Experimental agent runtime.
- Closes AP-105 Gaps 1, 2, 3, 6 (intelligence honesty). Orchestrator finalizes real failures with zero
  orchestrator edits.
- Minimal, additive surface: two new small modules + one adapter rewrite; no schema/migrations; Runtime
  V2 contract, registry, governance, scheduler, events, and the Track-S sandbox seam all preserved.

**Negative / accepted**
- Lifecycle safety (terminate/cancellation/resume), fail-fast init, and configurable budget remain open
  (Pilot bar / H-4); an interrupted Nexus run still restarts from zero and cannot be cancelled.
- Production `web_search` requires wiring a real provider; until then `web_search` honestly errors.
- **Pilot** and **Production Ready** are explicitly not v1.1.0-complete for Nexus.

## Follow-ups (separately authorized, not part of this ADR)

- Documentation: apply the Nexus-row upgrade in `architecture-status-summary.md` + dependent docs.
- H-4: terminate/cancellation, `resume_goal`, fail-fast init, configurable budget, `TIMED_OUT`, one
  audited real run → Pilot (inventory in `H-4-readiness-review.md` / `H-4-scope-definition.md`).
- Commit H-2 to `v1.1.0-planning`.

## Verdict

> **APPROVED.** Nexus is reclassified **Prototype → Experimental**, conditioned as above, using only
> evidence currently present in the repository.
