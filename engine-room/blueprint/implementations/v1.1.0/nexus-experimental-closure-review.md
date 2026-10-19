# H-2 — Nexus Experimental Closure Review

> Final evidence-based closure review for H-2 (Prototype → **Experimental**). Review only — no
> implementation, no source/test changes. Claims re-verified against current source + a live
> test/lint/type run at the post-H-2 working tree (HEAD `b734c13` + uncommitted H-2 diff).
> Basis: accepted `H-2-implementation-report.md`, `nexus-honesty-validation.md`,
> `nexus-search-provider-report.md`, `nexus-planning-validation.md`, `nexus-experimental-readiness.md`.

---

## 1. Live verification (this review)

| Gate | Command | Result |
|---|---|---|
| Full suite | `pytest -q` | **194 passed** (~34s) |
| Lint | `ruff check nexus/ tests/` | **All checks passed!** |
| Types | `mypy nexus/ --ignore-missing-imports` | **no issues in 60 source files** |
| HEAD | `git rev-parse --short HEAD` | `b734c13` (H-2 staged, **uncommitted**) |

Test-count delta: 178 (Track S freeze) → **194 (+16)**. Zero regressions.

## 2. "No X remains" verification (source-level, required)

| Condition | Method | Result |
|---|---|---|
| No production `AsyncMock` | `grep -E "AsyncMock\|unittest\.mock\|is_mocked" nexus.py` | **NONE** ✅ |
| No canned search implementation | `grep` canned MCP strings in `nexus.py` | **NONE** ✅ |
| No decorative plan generation | `grep` the literal plan strings in `nexus.py` | **NONE** ✅ |
| No always-success execution path | inspect `execute_goal` | `exit_code = 0 if (finished and not failed) else 1` (`nexus.py:303`); no hardcoded `return 0` ✅ |

Guard tests enforce these going forward: `test_no_unittest_mock_import_in_runtime`,
`test_no_canned_search_literal_in_runtime`, `test_failure_yields_nonzero_exit`.

## 3. Exact files changed by H-2

| File | Type | Size / diff |
|---|---|---|
| `nexus/execution/runners/nexus.py` | modify | 176 lines changed (115 ins / 87 del net region) |
| `nexus/execution/runners/nexus_tools.py` | **new** | 67 lines — `ToolCall`, `parse_tool_call`, `extract_json_block`, `ToolCallParseError`, `VALID_TOOLS` |
| `nexus/execution/runners/search_provider.py` | **new** | 24 lines — `SearchProvider` ABC |
| `tests/unit/execution/test_nexus.py` | modify | +26 lines — migrated 2 execute tests to injection |
| `tests/unit/execution/test_nexus_honesty.py` | **new** | 258 lines — 16 P0 tests + injected fakes |

Plus documentation deliverables (design package + H-2 reports + this closure set). **No** changes to
`base.py`, `orchestrator.py`, registry, governance, scheduler, memory schema, events, config, or the
Track-S `confinement.py`/`manager.py`/`provider.py`. **No migrations.**

## 4. Capability matrix — before vs after (Experimental gate)

| Cap (AP-105 #) | Before | After | Verified by |
|---|---|---|---|
| Prod mock (4) | 🔴 Mocked | ✅ Not-present-in-prod | grep + `test_no_unittest_mock_import_in_runtime` |
| Search (8) | 🔴 Simulated | ✅ Provider-backed (DI) | `test_web_search_uses_injected_provider` |
| Planning (2) | 🔴 Simulated | 🟢 Partially Impl (goal-derived) | `test_plan_is_goal_derived_not_literal` |
| Action selection (3) | 🟠 Brittle | ✅ Structured/validated | `test_parse_*`, `test_malformed_call_fails_not_silent_finish` |
| Exit-status (18) | 🔴 Always 0 | ✅ Outcome-derived | `test_failure_yields_nonzero_exit`, `test_success_yields_zero_exit` |

(Full table incl. preserved/deferred caps in `nexus-before-after.md`.)

## 5. Remaining Pilot blockers (out of H-2 scope)

| Item | AP-105 cap | Tier | Owner |
|---|---|---|---|
| `terminate()` functional + wired | 14 | Pilot | H-4 |
| Cooperative cancellation | 14 | Pilot | H-4 |
| `resume_goal()` (resumable recovery) | 12 | Pilot | H-4 |
| Fail-fast initialization | 17 | Pilot | H-4 |
| Configurable execution budget | 19 | Pilot | H-4 |
| Timeout lifecycle (`TIMED_OUT`) | — | Pilot | H-4 |
| In-container file I/O ceiling (R-05) | 5/6 | P2 | H-5 / Track S |
| One audited real governed run | — | Pilot | H-4 |

None of these are required for **Experimental**; they are the Pilot bar (`ADR-nexus-v1.1-foundation`).
Full inventory in `H-4-readiness-review.md` / `H-4-scope-definition.md`.

## 6. Experimental classification justification

Per the `ADR-nexus-v1.1-foundation` Prototype → Experimental gate, **all** clauses are met with code +
test + trace evidence:
1. No simulation in prod (mock removed, guard-tested).
2. Real exit status (outcome-derived; orchestrator finalizes FAILURE on non-zero).
3. Real search (`SearchProvider` DI; canned demoted to a test double; honest no-provider default).
4. Structured tool-calls (schema-validated; malformed → explicit failure, not silent finish).
5. Goal-derived plan (model/goal-derived; literal removed).
6. Real-LLM-branch tests (16 honesty tests; 194 total green).

The sound skeleton (governance gate, real persistence, registry/contract, Track-S-contained tools) is
preserved. Lifecycle safety (terminate/resume) is deliberately deferred to Pilot.

## 7. Verdict

> **APPROVED** — Nexus reclassified **Prototype → Experimental**, conditioned: (a) Experimental, not
> Pilot (Pilot blockers in §5 open); (b) effective on commit (H-2 currently uncommitted); (c) production
> search requires injecting a real `SearchProvider` bound to the sandbox network policy; (d) the
> `architecture-status-summary.md` Nexus-row upgrade is a separately authorized doc step.

Formal decision: `ADR-nexus-experimental.md`. Supporting matrices: `nexus-capability-upgrade.md`,
`nexus-before-after.md`.

## 8. Review constraints honored

No code/test modified ✅ · no new implementation ✅ · no migrations ✅ · no commit ✅ · claims
re-verified against live source + gates ✅.
