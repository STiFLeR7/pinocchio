# AP-102 — Critical Safety Fixes — Implementation Report

> **Release:** Nexus v1.0.1 "Alignment"
> **Action Point:** AP-102 — Critical Safety Fixes (A-001, A-002 only)
> **Type:** Root-cause implementation under strict TDD (systematic-debugging Phase 4).
> **Status:** ✅ Complete · **Result:** 126 tests pass, ruff + mypy clean, diff scoped to 6 files.

---

## 1. Objective

Implement only the two Priority-0 safety findings validated in AP-101:
- **A-001** — Fail-open owner authentication → fail closed (startup gate + service defense-in-depth).
- **A-002** — Execution timeout mismatch → honor ADR-010 per-runtime timeouts + enforce hard limit.

No other work. Strict TDD: failing tests first, minimal root-cause fix, then full regression.

## 2. Method (systematic-debugging Phase 4)

1. Read existing test patterns and all `ApprovalService` construction sites to guarantee
   regression-safety and tight scope.
2. Wrote failing tests first; **confirmed red** (defect reproduced live).
3. Implemented minimal root-cause fixes.
4. **Confirmed green**; ran full suite + ruff + mypy; verified diff scope.

## 3. Changes (6 source files, +76 / −18)

### A-001 — fail closed
- `nexus/api.py`: new `_validate_startup_configuration(settings)` raising `ConfigurationError` on
  empty `discord.owner_ids`; invoked at the top of the `lifespan` startup (logged `critical` then
  re-raised → app cannot serve).
- `nexus/approvals/service.py`: `evaluate_approval` now denies when `owner_ids` is empty
  (defense-in-depth), before any decision logic. Targeted at the authorization chokepoint only, so
  `sweep_expired_approvals` is unaffected.
- Detail: [`owner-auth-hardening.md`](./owner-auth-hardening.md).

### A-002 — honor configured timeouts + hard limit
- `nexus/execution/runners/base.py`: new `resolve_execution_timeout(settings, field, default=300)`
  helper; reads the per-runtime field, clamps to `hard_limit`.
- `claude.py` → `claude_timeout`; `gemini.py` → `gemini_timeout`; `nexus.py` (`execute_command`) →
  `research_timeout`. Removed the broken `research_timeout_seconds` lookups and the hardcoded 300.
- Detail: [`runtime-timeout-validation.md`](./runtime-timeout-validation.md).

## 4. Tests added (16) — all green

- `tests/unit/approvals/test_owner_auth_hardening.py` (4) — A-001 service.
- `tests/unit/test_startup_validation.py` (2) — A-001 startup gate.
- `tests/unit/execution/test_timeout_resolution.py` (10) — A-002 resolver + per-runtime behavior.

## 5. Verification (evidence)

| Gate | Result |
|---|---|
| New AP-102 tests | 16 passed |
| Full suite | **126 passed** (110 prior + 16), 0 regressions |
| ruff `nexus/ tests/` | All checks passed |
| mypy `nexus/ --ignore-missing-imports` | Success: no issues in 53 files |
| Diff scope | 6 files, +76/−18, all traced to A-001/A-002 |

Full evidence: [`safety-regression-report.md`](./safety-regression-report.md).

## 6. Constraint compliance

- ✅ Only A-001 and A-002 touched; no scope expansion.
- ✅ No scheduler work, no Nexus redesign, no sandbox changes, no documentation
  (README/STATUS/ROADMAP) updates, no runtime features, no governance/architecture changes.
- ✅ Only root-cause fixes; no opportunistic refactoring.
- ✅ Every change traces to an accepted finding (constraint 6).
- ✅ Validation present (constraint 8); reports/this document present (constraint 9).
- ✅ Blueprint synchronized for AP-102 scope (this folder). *(Project-state docs README/STATUS/
  ROADMAP are intentionally untouched — that is AP-104's job, and AP-102 forbids doc updates.)*

## 7. Issues discovered → documented & deferred

Per instruction (additional issues documented, not fixed):
1. `bot.py` inline owner check retains fail-open *shape* for its UX message only (authoritative
   `evaluate_approval` is now fail-closed) — cosmetic alignment **deferred**.
2. No dedicated `nexus_timeout` config field; Nexus uses `research_timeout` — **deferred**.
3. Timed-out CLI steps still recorded `COMPLETED`/`exit_code=-1` (TD-21) — **deferred**.

## 8. Success criteria — met

- [x] Startup fails with empty `owner_ids`.
- [x] Approvals fail with empty `owner_ids`.
- [x] Runtime timeouts match configuration.
- [x] Hard limit enforced (impossible to exceed).
- [x] All tests pass; no regressions.
- [x] Git diff tightly scoped.

## 9. Deliverables produced

- `blueprint/implementations/v1.0.1/AP-102-report.md` (this)
- `blueprint/implementations/v1.0.1/owner-auth-hardening.md`
- `blueprint/implementations/v1.0.1/runtime-timeout-validation.md`
- `blueprint/implementations/v1.0.1/safety-regression-report.md`

## 10. Recommendation

AP-102 complete. Recommend proceeding to **AP-103 (Scheduler Foundation — DESIGN FIRST)**: produce
`scheduler-design.md` + `scheduler-event-map.md` for approval before any scheduler implementation,
explicitly scoping the two new monitor jobs (outbox/checkpoint health) as read-only observation to
stay within "no new features" (flagged in AP-101). Awaiting authorization.
