# H-2 — Test Strategy (Track H, v1.1.0)

> **Design only.** The test design that will *prove* Nexus honesty when H-2 is implemented. Defines
> what to test, the RED→GREEN→regression discipline, the injection seams that replace the in-module
> mock, and the explicit evidence each P0 gap requires. No tests are written here (no implementation).
> Run target (at implementation time): project venv `.venv/Scripts/python.exe`.

---

## 1. Principles

- **TDD-first** (project standard): each P0 change lands RED (failing test asserting the honest behavior)
  → GREEN (minimal code) → full regression. No code without a failing test first.
- **Inject, don't embed.** The test double replaces the runtime's in-module `AsyncMock` via the **existing
  constructor seam** (`openrouter_client`) plus the new `search_provider` seam. Tests mock the
  *transport/provider*, never the *decision logic* — so green tests evidence real reasoning paths
  (closes Gap 9).
- **Honesty assertions are negative too:** assert simulation is *absent* (no `unittest.mock` import in
  `nexus.py`; no canned search string in the runtime).
- **Preserve the sound skeleton:** existing persistence/governance/artifact assertions must stay green.

## 2. Current baseline (what exists today)

`tests/unit/execution/test_nexus.py` — 4 tests, **all through the mock path**: they assert governance,
`agent_steps`/checkpoint persistence, artifact shape. They do **not** cover real reasoning, real search,
failure, termination, or resume (Gap 9). These tests must be **migrated** to the injection seam, not
deleted — their persistence/governance assertions remain valuable.

## 3. Test fakes (design)

| Fake | Replaces | Shape |
|---|---|---|
| `FakeLLMClient` | in-module `AsyncMock` for `openrouter_client` | `async complete(prompt) -> str` returning scripted **structured** JSON tool-calls (per test) |
| `FakeSearchProvider` | canned `web_search` text (`nexus.py:84-94`) | `async search(query) -> results` returning deterministic fixtures |
| `FailingLLMClient` / `FailingSearchProvider` | — | raise/return `ok=false` to drive FAILED paths |

All injected via constructor (Rule 2). Located in `tests/` (or a `conftest.py` fixture), **never** in
`nexus/`.

## 4. P0 test matrix (required evidence for Experimental)

| Gap | RED test(s) | Asserts (honest behavior) |
|---|---|---|
| **P0-1 mock removal** | `test_no_mock_import_in_runtime`; `test_real_branch_drives_loop` | `unittest.mock` not imported by `nexus.py`; loop runs via injected `FakeLLMClient` (no `is_mocked`) |
| **P0-2 structured calls** | `test_structured_toolcall_parsed`; `test_malformed_toolcall_is_error_not_finish`; `test_unknown_tool_errors` | valid `ToolCall` parsed; malformed → explicit error state (not silent `finish`); unknown tool → error `ToolResult` |
| **P0-3 goal-derived plan** | `test_plan_derived_from_goal`; `test_no_hardcoded_plan_literal` | plan varies with goal; persisted as real `agent_plan`; the 3-step literal is gone |
| **P0-4 exit status** | `test_failure_yields_nonzero_exit`; `test_failed_step_status_truthful`; `test_success_yields_zero` | tool/loop failure → non-zero exit + FAILURE finalization; failed step persisted non-COMPLETED; genuine finish → 0 |
| **P0-5 search port** | `test_web_search_calls_provider`; `test_no_canned_search_in_runtime`; `test_search_egress_respects_policy` | `FakeSearchProvider` invoked; canned MCP text absent from `nexus/`; egress disabled/host-governed under `network=none` |
| **P0-6 real-branch coverage** | (umbrella — satisfied by the above) | real decision + real search + honest failure all covered without the mock path |

## 5. P1 test design (Pilot — implemented in H-4, designed now)

| Gap | Test(s) | Asserts |
|---|---|---|
| **P1-1 terminate** | `test_cancel_between_steps_cancels`; `test_inflight_command_killed`; `test_cancel_latency_bounded` | cancel signal → `CANCELLED` terminal + `cancelled` exit; sandbox process terminated; ≤ one tool-exec latency |
| **P1-2 resume** | `test_resume_rebuilds_trajectory`; `test_resume_continues_from_cursor`; `test_resume_no_duplicate_step`; `test_resume_fails_closed_on_missing_data`; `test_resume_revalidates_governance` | trajectory rebuilt from `agent_steps`; continues at max+1; idempotent; fail-closed; governance re-checked |
| **P1-3 fail-fast init** | `test_init_fails_without_key`; `test_init_proceeds_with_key` | missing key raises; present key proceeds |
| **P1-4 budget/TIMED_OUT** | `test_budget_exhaustion_times_out`; `test_step_budget_configurable` | budget exhaustion → `TIMED_OUT` (≠ COMPLETED); configurable value honored |

## 6. Regression & non-regression guards

- **Full suite must stay green** (current **178 passed**) after each H-2 step; CLI runtimes
  (`test_gemini.py`, `test_claude.py`), sandbox suites (S-2/S-3/S-4), governance, scheduler, and e2e
  (`test_mvp_workflow.py`) are unaffected by Nexus-internal honesty changes.
- **e2e finalization guard:** `test_mvp_workflow` exercises the orchestrator finalize path; verify a
  Nexus failure now finalizes FAILURE (not masked SUCCESS) without breaking the success path.
- **Gates:** `ruff check nexus/ tests/` clean; `mypy nexus/` clean — every step.

## 7. Coverage definition of done (Experimental)

Nexus is test-qualified for Experimental when: the mock path is gone and proven absent; the real
decision/search/plan/exit-status behaviors are each covered by a passing test using injected fakes;
failure is observably non-zero; and the full suite + ruff + mypy are green with zero regressions. Pilot
adds the P1-1/P1-2/P1-4 suites plus one audited real governed run.

## 8. Status

Design only — no tests authored, no source changed. Test authoring happens inside the gated H-2 (P0) and
H-4 (P1) implementation APs under RED-first discipline.
