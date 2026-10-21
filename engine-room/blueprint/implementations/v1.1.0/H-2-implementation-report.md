# H-2 — Nexus Honesty Fixes: Implementation Report (P0 / Experimental Track)

> **Release line:** v1.1.0 "Containment" · **AP:** H-2 · **Track:** H (Nexus) · **Status:** ✅ Complete
> **Target:** Nexus **Prototype → Experimental** (P0 items only). **Method:** strict TDD
> (RED → GREEN → regression). Branch `v1.1.0-planning`, on top of Track S freeze `b734c13`.
> **Authorization:** H-2 implementation, P0 scope. No commit made.

---

## 1. Scope delivered (P0 only)

| # | P0 objective | Delivered |
|---|---|---|
| 1 | Remove `AsyncMock` + all production mock execution paths | `AsyncMock` import and the `is_mocked` branch deleted from `nexus.py` |
| 2 | Remove the `is_mocked` execution branch | Loop has a single real path (model → structured tool-call → tool) |
| 3 | `SearchProvider` abstraction via DI | New `search_provider.py` port; injected via constructor (like `openrouter_client`) |
| 4 | Provider-backed search replaces canned behavior | `web_search` calls `self.search_provider.search()`; no provider → honest error (no canned text) |
| 5 | Goal-derived planning replaces decorative plans | `_generate_plan(goal)` derives the plan from the goal; the MCP literal is gone |
| 6 | Truthful execution outcomes / exit status | `execute_goal` returns `exit_code`/`status` from real outcome; failed steps persist `FAILED` |
| 7 | Structured tool-call execution flow | New `nexus_tools.py` (`ToolCall` + `parse_tool_call`); malformed → explicit error, never silent `finish` |
| 8 | Production-path test coverage | New `test_nexus_honesty.py` (16 tests) + migrated `test_nexus.py` to injection |

**Explicitly NOT implemented (out of P0 scope, as instructed):** `terminate()`, cancellation,
`resume_goal()`, auto-resume, advanced replanning, new tools, streaming, additional runtimes, schema
changes, migrations, any Pilot-track work.

## 2. Changes (minimal diff)

| File | Type | Change |
|---|---|---|
| `nexus/execution/runners/nexus_tools.py` | **new** | `ToolCall` model, `parse_tool_call`, `extract_json_block`, `ToolCallParseError`, `VALID_TOOLS` (the existing five) |
| `nexus/execution/runners/search_provider.py` | **new** | `SearchProvider` ABC (`async search(query) -> str`) |
| `nexus/execution/runners/nexus.py` | modify | remove `AsyncMock`/`is_mocked`; add `search_provider` DI param + `exit_code`/`status` fields; `_generate_plan`; structured loop; honest exit status; provider-backed `web_search`; summary artifact uses real `exit_code` |
| `tests/unit/execution/test_nexus_honesty.py` | **new** | 16 P0 tests + injected fakes (`FakeLLMClient`, `FailingLLMClient`, `FakeSearchProvider`) |
| `tests/unit/execution/test_nexus.py` | modify | migrate 2 execute tests off the removed mock path to injected fakes |

**No changes** to `base.py` (contract unchanged), `orchestrator.py`, registry, governance, scheduler,
memory schema, events, config, or the S-4 `confinement.py` seam. **No migrations.**

## 3. Architecture boundaries preserved (rules 4–10)

- **Runtime V2 / `AgentRuntimeAdapter` contract:** unchanged — `validate_goal`/`execute_goal` signatures
  intact; `search_provider` is an additive optional constructor param. No new abstract methods.
- **RuntimeRegistry:** `@runtime_registry.register("nexus")` unchanged; routing unchanged.
- **`AgentStepRecord` schema:** identical fields written every step; only the `status` *value* for a
  failed step changes from `COMPLETED` to the existing `FAILED` enum value — no column change.
- **Orchestrator:** untouched; it already maps `exit_code != 0 → ExitStatus.FAILURE`
  (`orchestrator.py:227`), so a truthful `exit_code` now finalizes failures correctly with zero
  orchestrator edits.
- **Governance:** `validate_goal` → `GovernanceManager` unchanged.
- **Sandbox confinement (Track S):** `read_file`/`write_file` still route through `resolve_in_workspace`
  (S-4) and `execute_command` through `SandboxManager` — untouched.

## 4. TDD trace

- **RED:** `test_nexus_honesty.py` → 15 failed / 1 passed (missing `nexus_tools`/`search_provider`
  modules; not-yet-honest behavior). One test (`test_execute_uses_injected_client_real_branch`) passed
  immediately because a real injected client already bypassed the mock branch.
- **GREEN:** added the two modules + the `nexus.py` honesty changes → 16/16 honesty tests pass; the 5
  migrated `test_nexus.py` tests pass.
- **Regression:** full suite **194 passed** (178 → 194, **+16**), zero regressions; ruff clean; mypy
  clean (60 files). Two trivial post-GREEN fixes (unused import via `ruff --fix` on the new test; a
  `str()` cast for a mypy `Any`-return) — no behavior change.

## 5. Verification gates (project venv `.venv/Scripts/python.exe`)

| Gate | Result |
|---|---|
| New honesty tests | **16 passed** |
| Full suite | **194 passed** (was 178), 0 regressions |
| ruff `nexus/ tests/` | All checks passed |
| mypy `nexus/` | no issues in 60 source files |

## 6. Runtime traces (recorded evidence)

Three standalone runs (in-memory SQLite, injected fakes) — see `nexus-experimental-readiness.md` §runtime traces:
- **SUCCESS:** model-derived 2-step plan; provider-backed `web_search` (`[real-provider results for
  'nexus']`); `finish` → `exit_code 0 / completed`.
- **FAILURE:** model transport error → step `status=failed`, `exit_code 1 / failed` (no masked success).
- **MALFORMED:** unparseable tool-call → `tool=error status=failed`, `exit_code 1` (no silent `finish`).

## 7. Boundary / stop

Stopped after H-2 (P0). **Not started:** `terminate()`/cancellation, `resume_goal`/auto-resume, H-3, H-4,
any Pilot work. **No commit made** (awaiting explicit instruction). HEAD `b734c13`; working tree holds the
H-2 diff above.

## 8. Verdict

All eight P0 objectives delivered with RED-first tests and runtime traces; architecture boundaries
preserved; zero regressions. Nexus meets the **Prototype → Experimental** gate
(`ADR-nexus-v1.1-foundation`). Full evidence and the reclassification determination are in
`nexus-experimental-readiness.md`.
