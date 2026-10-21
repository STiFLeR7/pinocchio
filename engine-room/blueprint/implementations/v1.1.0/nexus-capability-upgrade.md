# Nexus Capability Upgrade — Prototype → Experimental (H-2)

> The formal capability-classification change record, with the evidence chain. Companion to
> `ADR-nexus-experimental.md`. Documentation only.

---

## 1. Classification change

| | Before | After |
|---|---|---|
| Maturity (AP-105 verdict axis) | **Prototype** (Concept Demonstration in default config) | **Experimental** |
| Authoritative ADR | `ADR-nexus-reality-audit` (Prototype) | `ADR-hermes-experimental` (supersedes the verdict) |
| Default-config behavior | Hardcoded mock decision path | Honest real path; no-provider search returns an explicit error |
| Effective | — | **On commit** of H-2 to `v1.1.0-planning` |

## 2. Per-capability upgrade ledger (AP-105 caps touched by H-2)

| Cap # | Capability | Before | After | Mechanism (H-2) |
|---|---|---|---|---|
| 4 | Prod mock branch | 🔴 Mocked | ✅ **Not present in prod** | `AsyncMock` import + `is_mocked` branch deleted; simulation → injected test doubles |
| 8 | `web_search` | 🔴 Simulated | ✅ **Implemented** | `SearchProvider` port + DI; canned text removed; honest no-provider error |
| 2 | Dynamic planning | 🔴 Simulated | 🟢 **Partially Implemented** | `_generate_plan(goal)` — model/goal-derived advisory plan; literal removed |
| 3 | Action selection | 🟠 Partially Impl | ✅ **Implemented** | `parse_tool_call` structured contract; malformed → explicit error |
| 18 | Exit-status fidelity | 🔴 Simulated | ✅ **Implemented** | outcome-derived `exit_code`/`status`; failed step persists `FAILED` |

## 3. Capabilities explicitly unchanged (preserved)

| Cap # | Capability | State |
|---|---|---|
| 1 | Goal validation (governance) | ✅ Implemented (untouched) |
| 5,6 | File tools | ✅ Implemented + workspace-confined (S-4, untouched) |
| 7 | `execute_command` | ✅ Implemented, default-secure (Track S, untouched) |
| 9,10 | Agent-step / trajectory persistence | ✅ Implemented (content now genuine) |
| 11 | Checkpoint persistence | ✅ write-only (recovery is Pilot) |
| 13 | Heartbeat | ✅ Implemented |
| 15,16 | Summarization / artifacts | ✅ Implemented (plan artifact now real) |
| 20 | Registry integration | ✅ Implemented (untouched) |

## 4. Capabilities still open (Pilot bar — NOT upgraded by H-2)

| Cap # | Capability | State after H-2 | Tier |
|---|---|---|---|
| 14 | Termination | ❌ Not Present (no-op) | Pilot / H-4 |
| 12 | Recovery / resume | ❌ Not Present | Pilot / H-4 |
| 17 | Init / key check | 🟠 Stubbed | Pilot / H-4 |
| 19 | Step bound | hardcoded 5 | Pilot / H-4 |

## 5. Evidence chain (authoritative, accepted)

```
ADR-nexus-reality-audit (v1.0.1)  ─ Prototype, ledger Caps 2/3/4/8/18 simulated/mocked
        │
H-2 implementation (TDD)  ─ mock removed · SearchProvider DI · goal-derived plan · structured calls · honest exit
        │
H-2 reports (accepted): implementation-report, honesty-validation, search-provider-report,
                        planning-validation, experimental-readiness
        │
nexus-experimental-closure-review.md  ─ verdict APPROVED (live: 194 passed, ruff+mypy clean, 4x no-X-remains)
        │
ADR-nexus-experimental.md  ─ Accepted: Prototype → Experimental
        │
THIS UPGRADE  ─ Caps 4,8,2,3,18 reclassified ≥ Partially-Implemented with tests
```

## 6. Conditions

1. **Experimental, not Pilot** — Caps 12/14/17/19 open; do not represent Nexus as lifecycle-safe or
   resumable.
2. **Effective on commit** — evidence-bound to the H-2 source (uncommitted at writing).
3. **Production search** requires a real injected `SearchProvider` bound to the sandbox network policy.
4. The `architecture-status-summary.md` row upgrade (Nexus: Mocked/Prototype → Experimental) is a
   **separately authorized** documentation step (not performed here).
