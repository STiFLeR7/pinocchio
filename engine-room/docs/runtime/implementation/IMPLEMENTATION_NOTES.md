# Implementation Notes — Runtime Core + Claude Vertical Slice

**Engineering program:** prove the Runtime architecture survives first contact with a real
execution runtime, using Claude Code as the single vertical slice. **Not** a full execution
platform — a validation program.

These are engineering documents, not architecture. No ADR, contract, invariant, or frozen
Runtime document (`docs/v2/runtime/00`–`24`) was modified.

---

## 1. What already existed vs. what this program built

| Milestone | Status entering the program | What this program did |
|---|---|---|
| **M1 — Runtime Core** (`nexus_runtime/`) | **Already implemented and green** (469 tests): RM prepares a `RuntimeSession` to `Ready` and stops — the frozen "RM prepares; the engine performs" boundary (`00` §1/§8). | Left the preparation pipeline untouched. **Realized the deferred execution-lifecycle canon** (see M1′). |
| **M1′ — Deferred lifecycle canon** | States `Running/Completed/Cancelled/Destroyed` and events `runtime.started…destroyed` were **frozen canon in `07`/`15`** but explicitly *deferred in code* ("deferred to the Execution Engine phase"). | Implemented them in `nexus_runtime/{vocabulary,events,lifecycle}.py` — generic, zero provider code. See [RUNTIME_DECISIONS](RUNTIME_DECISIONS.md) §1. |
| **M2 — Claude Adapter** (`nexus_runtime_claude/`) | Did not exist. | Built. All Claude-specific behavior lives here and nowhere else. See [CLAUDE_RUNTIME](CLAUDE_RUNTIME.md). |
| **M3 — Execution Engine** (`nexus_execution/`) | Did not exist (Execution Engine is "Phase 8, downstream"). | Built the *minimal* generic engine + the concrete `RuntimeAdapter` protocol (materializing conceptual doc `03`). See [EXECUTION_FLOW](EXECUTION_FLOW.md). |
| **M4 — E2E validation** | — | One deterministic integration scenario + an opt-in real-`claude` smoke. `tests/integration/test_runtime_vertical_slice.py`. |

## 2. Package layout & dependency direction

```
nexus_runtime         (RM core — provider-blind; realizes the lifecycle canon)
    ▲
nexus_execution       → { nexus_runtime, nexus_core, nexus_infra }
    │   generic Engine + the concrete RuntimeAdapter protocol (materialized doc 03)
    ▲
nexus_runtime_claude  → { nexus_execution, nexus_core }
        the ONLY place "Claude" drives behavior
```

- `nexus_execution` consumes RM's `RuntimeSession` (downstream of RM, `00` §4) and reuses
  the Phase 2 substrate (event emitter = the infrastructure context; metrics = its sink).
- `nexus_runtime_claude` implements the engine's protocol; nothing generic imports it
  (asserted in code — see §4).
- Both registered in `pyproject.toml` (`[tool.hatch.build.targets.wheel]`) and the Makefile
  (`PACKAGES`, `TESTS`, `test-cov` cov targets).

## 3. Test & quality results

| Gate | Result |
|---|---|
| Full suite | **1881 passed, 1 skipped** (opt-in real-`claude` smoke) |
| Coverage (`nexus_runtime`, `nexus_execution`, `nexus_runtime_claude`) | **100.0%** (branch) |
| `mypy --strict` | clean (25 source files) |
| `ruff check` / `ruff format --check` | clean |
| Prior phases | pass unchanged (see §4 for the 4 test-assertion updates M1′ required) |

## 4. The four M1′ test updates (the only edits to existing tests)

Realizing the deferred canon opened three closed sets that Phase-8A tests pinned; each was
updated to the realized canon (not a behavior change to the preparation path):

1. `legal_transitions(READY)` — added `RUNNING`.
2. `legal_transitions(FAILED)` — added `DESTROYED` (execution-path teardown).
3. `TERMINAL_STATES` — added `DESTROYED`.
4. `RuntimeLifecycleState` member count — `7 → 11`.

The determinism suite (preparation path only) is untouched. New tests cover every execution
transition and the whole-lifecycle projection.

Structural guardrails enforce the program's validation checklist in code
(`tests/integration/…`):
- RM core (`nexus_runtime`) contains **zero** "claude" mentions;
- the generic engine (`nexus_execution`) never imports `nexus_runtime_claude`;
- the Claude package holds the provider behavior.

## 5. What was deliberately NOT built (Milestone-3 constraints)

No scheduling, retries, recovery, validation, reflection, or knowledge. No Gemini/Docker/
Browser/Shell/Python runtimes. Suspend/resume (`Paused`/`Waiting`) and their events stay
deferred — the minimal engine drives none of them. Allocation *capacity release* for an
executed session is a documented future affordance, not part of this slice
([RUNTIME_DECISIONS](RUNTIME_DECISIONS.md) §5).
