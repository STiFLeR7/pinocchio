# Nexus Maturity Upgrade — Prototype → Experimental

> Formal maturity-classification change record with the evidence chain. Companion to
> `ADR-nexus-experimental.md`. Documentation only.

---

## 1. Classification change

| | Before | After |
|---|---|---|
| Maturity (architecture-status-summary) | 🔴 Mocked (partial) | 🟠 **Experimental** |
| AP-105 verdict axis | **Prototype** | **Experimental** |
| Authoritative ADR | `ADR-nexus-reality-audit` | `ADR-hermes-experimental` (supersedes verdict) |
| Default-config behavior | Hardcoded mock decision path | Honest path; no-provider search → explicit error |
| Effective | — | **On commit** of H-2 to `v1.1.0-planning` |

## 2. The five reversed defects (why the upgrade is earned)

| # | Prototype defect | Reversal (H-2) | Cap | Evidence |
|---|---|---|---|---|
| 1 | `AsyncMock`/`is_mocked` in prod | removed; simulation → injected test doubles | 4 | `test_no_unittest_mock_import_in_runtime`; grep NONE |
| 2 | Simulated `web_search` | `SearchProvider` DI; provider-backed; honest no-provider error | 8 | `test_web_search_uses_injected_provider` |
| 3 | Decorative hardcoded plan | `_generate_plan(goal)` goal-derived | 2 | `test_plan_is_goal_derived_not_literal` |
| 4 | Brittle parse → silent finish | `parse_tool_call` structured; malformed → FAILED | 3 | `test_malformed_call_fails_not_silent_finish` |
| 5 | Always-`0` exit | outcome-derived `exit_code`/`status` | 18 | `test_failure_yields_nonzero_exit` |

## 3. Evidence chain (authoritative, accepted)

```
ADR-nexus-reality-audit (v1.0.1)  ─ Prototype; Caps 2/3/4/8/18 simulated/mocked
        │
H-2 implementation (TDD, P0)       ─ mock removed · SearchProvider DI · goal-derived plan · structured calls · honest exit
        │
H-2 reports (accepted)             ─ implementation/honesty/search/planning/readiness
        │
nexus-experimental-closure-review.md  ─ APPROVED (live: 194 passed, ruff+mypy clean, 4× no-X-remains)
        │
ADR-nexus-experimental.md         ─ Accepted: Prototype → Experimental
        │
THIS UPGRADE  ─ propagated to architecture-status-summary.md, STATUS.md, ROADMAP.md, README.md
```

## 4. Why Experimental and not Pilot

The Pilot gate additionally requires wired+tested cancellation, working+tested resume, fail-fast init,
configurable budget, `TIMED_OUT` lifecycle, and one audited real governed run — none delivered by H-2
(out of P0 scope by design). Those are the H-4 inventory (`H-4-scope-definition.md`).

## 5. Conditions on the new classification

1. **Experimental, not Pilot** — do not represent Nexus as lifecycle-safe or resumable.
2. **Effective on commit** — evidence-bound to the H-2 source (uncommitted at writing).
3. **Production search** requires a real injected `SearchProvider` bound to the sandbox network policy;
   default no-provider behavior is an honest error, never canned.
4. The authoritative `architecture-status-summary.md` Nexus row is updated by this closure (the
   separately-authorized documentation step).

## 6. Cross-subsystem note

With this upgrade, v1.1.0 "Containment" has moved **two** subsystems: **Sandbox** Experimental → Pilot
Safe (Track S) and **Nexus** Prototype → Experimental (Track H / H-2). The remaining Track H work (H-4)
takes Nexus to Pilot.
