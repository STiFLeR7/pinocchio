# Nexus Experimental Readiness Assessment (H-2)

> The reclassification determination: **can Nexus move Prototype → Experimental on repository evidence
> after H-2?** Consolidates the before/after capability matrix, code evidence, test evidence, runtime
> traces, test-count delta, and regression summary. Verified at the post-H-2 working tree (HEAD
> `b734c13` + uncommitted H-2 diff).

---

## 1. Promotion gate (`ADR-nexus-v1.1-foundation`)

**Prototype → Experimental requires:** no simulation in the prod path · real exit status · real search ·
structured tool-calls · goal-derived plan · real-LLM-branch tests. (Lifecycle safety — terminate/resume —
is the **Pilot** bar and is *not* required here.)

## 2. Before vs after capability matrix

| Cap (AP-105 #) | Before (Prototype) | After (H-2) | Evidence |
|---|---|---|---|
| Prod mock branch (4) | 🔴 Mocked (`AsyncMock` in prod) | ✅ **Not present in prod** | `test_no_unittest_mock_import_in_runtime` |
| `web_search` (8) | 🔴 Simulated (canned) | ✅ **Implemented** (provider-backed) | `test_web_search_uses_injected_provider`; `nexus-search-provider-report.md` |
| Dynamic planning (2) | 🔴 Simulated (literal) | 🟢 **Partially Implemented** (goal-derived, advisory) | `test_plan_is_goal_derived_not_literal`; `nexus-planning-validation.md` |
| Action selection (3) | 🟠 Partial (brittle parse) | ✅ **Implemented** (structured, validated) | `test_parse_*`, `test_malformed_call_fails_not_silent_finish` |
| Exit-status fidelity (18) | 🔴 Simulated (always 0) | ✅ **Implemented** (outcome-derived) | `test_failure_yields_nonzero_exit`, `test_success_yields_zero_exit` |
| Goal validation (1) | ✅ Implemented | ✅ Implemented (unchanged) | governance untouched |
| File tools (5,6) | ✅ + confined (S-4) | ✅ + confined (unchanged) | S-4 seam intact |
| `execute_command` (7) | ✅ sandbox (default-secure, S-2/S-3) | ✅ unchanged | Track S intact |
| Agent-step persistence (9,10) | ✅ Implemented | ✅ Implemented (now genuine content) | persistence tests green |
| Checkpoint persistence (11) | ✅ write-only | ✅ write-only (resume is Pilot) | unchanged |
| **Termination (14)** | ❌ Not Present | ❌ **Not Present (deferred — Pilot/H-4)** | out of P0 scope |
| **Recovery/resume (12)** | ❌ Not Present | ❌ **Not Present (deferred — Pilot/H-4)** | out of P0 scope |
| Init (17) | 🟠 Stubbed | 🟠 Stubbed (fail-fast is Pilot/H-4) | out of P0 scope |
| Step bound (19) | hardcoded 5 | hardcoded 5 (configurable is Pilot/H-4) | out of P0 scope |

**All five Experimental-gating capabilities are now met.** The still-open items (14, 12, 17, 19) are the
**Pilot** bar — correctly deferred.

## 3. Code evidence (current source)

- Mock removed: `nexus.py` no longer imports `unittest.mock`; no `is_mocked` branch.
- Structured calls: `nexus.py` decision uses `parse_tool_call` (`nexus_tools.py`); malformed →
  `ToolCallParseError` → `FAILED`.
- Search port: `search_provider.py::SearchProvider`; injected via `__init__`; `web_search` calls it.
- Goal-derived plan: `nexus.py::_generate_plan` (model or goal-derived fallback); literal gone.
- Exit status: `execute_goal` computes `exit_code`/`status` from `finished`/`failed`; failed steps persist
  `ExecutionStatus.FAILED`; summary artifact uses real `exit_code`.

## 4. Test evidence

| Suite | Count | Purpose |
|---|---|---|
| `test_nexus_honesty.py` | **16** | mock-absence guards, structured parse, search DI, goal-planning, exit status |
| `test_nexus.py` | 5 | migrated to injection; persistence/governance/artifacts (real path now) |

**Test-count delta:** 178 (Track S freeze) → **194** (+16). **Zero regressions.**

## 5. Runtime traces (recorded, in-memory SQLite + injected fakes)

```
=== SUCCESS (provider-backed search -> finish) ===
goal: Research nexus developments
plan: [{'step': 1, 'description': 'Research the topic'}, {'step': 2, 'description': 'Report findings'}]
  step 0: tool=web_search status=completed result="[real-provider results for 'nexus']"
  step 1: tool=finish     status=completed result='Agent completed execution.'
RETURN: {'exit_code': 0, 'status': 'completed', 'steps_executed': 2, 'trajectory_len': 2}

=== FAILURE (model transport error -> truthful non-zero exit) ===
goal: This will fail
plan: [{'step': 1, 'description': 'Work toward goal: This will fail'}]
  step 0: tool=error status=failed result='Error: model transport failure'
RETURN: {'exit_code': 1, 'status': 'failed', 'steps_executed': 1, 'trajectory_len': 1}

=== MALFORMED (bad tool-call -> FAILED, not silent finish) ===
goal: Malformed path
plan: [{'step': 1, 'description': 'plan'}]
  step 0: tool=error status=failed result='Tool-call parse error: Completion is not valid JSON: ...'
RETURN: {'exit_code': 1, 'status': 'failed', 'steps_executed': 1, 'trajectory_len': 1}
```

These demonstrate: goal-derived planning, provider-backed search observation, structured-call failure as
a real failure (not silent finish), and truthful exit status across success/failure.

## 6. Regression & gate summary

| Gate | Result |
|---|---|
| Full suite | **194 passed** (178 → 194), 0 regressions |
| ruff `nexus/ tests/` | All checks passed |
| mypy `nexus/` | no issues, 60 source files |
| CLI runtimes (gemini/claude), sandbox S-2/S-3/S-4, governance, scheduler, e2e | green (unaffected) |

## 7. Success-criteria check (from the H-2 authorization)

| Criterion | Met? | Evidence |
|---|---|---|
| Execute without production `AsyncMock` paths | ✅ | guard tests; source |
| Use provider-driven search | ✅ | `SearchProvider` DI; trace |
| Generate goal-derived plans | ✅ | planning tests; trace |
| Produce truthful execution outcomes | ✅ | exit-status tests; traces |
| Preserve governance and sandbox controls | ✅ | governance + S-4/Track-S untouched |
| Pass all tests | ✅ | 194 passed, ruff+mypy clean |

## 8. Final determination

**Question:** Based solely on repository evidence after H-2, can Nexus be reclassified
**Prototype → Experimental**?

**Code evidence** (mock removed, structured calls, search port, goal-derived plan, honest exit status) +
**test evidence** (16 new honesty tests, 194 passing, ruff/mypy clean) + **runtime traces** (success,
failure, malformed all behaving truthfully) jointly satisfy **every** clause of the
`ADR-nexus-v1.1-foundation` Prototype → Experimental gate. The five Experimental-gating capabilities are
met; the remaining open items are the **Pilot** bar and are correctly deferred.

> ### Verdict: **YES — reclassify Nexus Prototype → Experimental.**

**Conditions:**
1. **Experimental, not Pilot** — `terminate()`/cancellation, `resume_goal`/recovery, fail-fast init, and
   configurable budget remain open (Pilot bar / H-4). Nexus must not be represented as lifecycle-safe or
   resumable.
2. **Effective on commit** — the H-2 source is validated but **uncommitted** (HEAD `b734c13`); the
   classification is evidence-bound to that code and takes effect when H-2 is committed.
3. **Production search** requires injecting a real `SearchProvider` and binding its egress to the sandbox
   network policy; the default no-provider behavior is an honest error, not canned output.
4. The `architecture-status-summary.md` row (Nexus: Mocked/Prototype → Experimental) is a **separately
   authorized** documentation step — not performed here.

**Stopped after H-2 implementation + validation. No Pilot-track work, no H-3/H-4, no commit.**
