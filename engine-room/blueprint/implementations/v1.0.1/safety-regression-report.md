# AP-102 — Safety Regression Report

> **Release:** Nexus v1.0.1 "Alignment" · **AP:** AP-102 · **Scope:** A-001, A-002 only
> **Method:** strict TDD (red → green) + full-suite regression + lint/type gates.

---

## 1. TDD evidence (red → green)

### Red (before implementation)
- New A-001/A-002 modules failed at import/runtime:
  ```
  ImportError: cannot import name '_validate_startup_configuration' from 'nexus.api'
  ImportError: cannot import name 'resolve_execution_timeout' from 'nexus.execution.runners.base'
  ```
- Owner-auth fail-closed tests (importable) failed with the live defect:
  ```
  FAILED tests/unit/approvals/test_owner_auth_hardening.py::test_evaluate_approval_denied_when_owner_ids_empty
  FAILED tests/unit/approvals/test_owner_auth_hardening.py::test_evaluate_approval_denied_when_owner_ids_none
  Failed: DID NOT RAISE ApprovalEngineError
  2 failed, 2 passed
  ```
  (The 2 passing were the regression tests encoding existing correct behavior.)

### Green (after implementation)
```
tests/unit/approvals/test_owner_auth_hardening.py
tests/unit/test_startup_validation.py
tests/unit/execution/test_timeout_resolution.py
................                                    [100%]
16 passed in 2.12s
```

## 2. Full-suite regression

```
.venv/Scripts/python.exe -m pytest -q
126 passed in 32.01s
```

- **Before AP-102:** 110 tests (per AP-101 baseline).
- **After AP-102:** 126 tests = 110 prior + 16 new. **0 failures, 0 regressions.**
- Every pre-existing test still passes — including the runner execute/heartbeat/persist tests
  (settings-less path → 300s default, behavior unchanged) and the approval tests
  (`sweep_expired_approvals` with empty owner_ids unaffected, owner/non-owner paths unchanged).

## 3. Quality gates (CI parity)

```
ruff check nexus/ tests/   →  All checks passed!
mypy nexus/ --ignore-missing-imports  →  Success: no issues found in 53 source files
```

## 4. Diff scope (tightly scoped — success criterion)

Source changes (`git diff --stat`): **6 files, +76 / −18**.

| File | Change | Finding |
|---|---|---|
| `nexus/api.py` | +`_validate_startup_configuration` + lifespan gate + import | A-001 |
| `nexus/approvals/service.py` | fail-closed branch in `evaluate_approval` | A-001 |
| `nexus/execution/runners/base.py` | +`resolve_execution_timeout` helper | A-002 |
| `nexus/execution/runners/claude.py` | use `claude_timeout` resolver | A-002 |
| `nexus/execution/runners/gemini.py` | use `gemini_timeout` resolver | A-002 |
| `nexus/execution/runners/nexus.py` | use `research_timeout` resolver | A-002 |

New test files (untracked): `tests/unit/approvals/test_owner_auth_hardening.py`,
`tests/unit/test_startup_validation.py`, `tests/unit/execution/test_timeout_resolution.py`.

**No** changes to: scheduler, sandbox, governance, Nexus loop/plan/simulation, documentation
(README/STATUS/ROADMAP), or any architecture. No opportunistic refactoring.

## 5. Success-criteria matrix (AP-102)

| Criterion | Status | Evidence |
|---|---|---|
| Startup fails with empty `owner_ids` | ✅ | `test_startup_fails_with_empty_owner_ids`; `api.py` gate |
| Approvals fail with empty `owner_ids` | ✅ | `test_evaluate_approval_denied_when_owner_ids_{empty,none}` |
| Valid owners unchanged | ✅ | `test_valid_owner_behaves_unchanged`, existing approval tests pass |
| Runtime timeouts match configuration | ✅ | Claude/Gemini behavioral tests (2700/1800) |
| Hard limit enforced | ✅ | `test_hard_limit_is_impossible_to_exceed`, `test_claude_execute_clamps_to_hard_limit` |
| Claude/Gemini/Nexus verified | ✅ | per-runtime behavioral tests |
| All tests pass | ✅ | 126 passed |
| No regressions | ✅ | full suite + ruff + mypy clean |
| Git diff tightly scoped | ✅ | 6 files, +76/−18, all traced to A-001/A-002 |

## 6. Issues discovered during AP-102 — documented & deferred

Per the "any additional issue must be documented and deferred" instruction:

1. **`bot.py:52-58` inline owner check** retains the `if self.owner_ids and …` shape for its
   ephemeral UX reply. Not an authorization bypass (the authoritative `evaluate_approval` now fails
   closed). Cosmetic alignment **deferred**.
2. **No dedicated `nexus_timeout` config field.** Nexus maps to `research_timeout` (rationale in
   `runtime-timeout-validation.md`). Introducing a dedicated tier **deferred** (config addition).
3. **Timed-out CLI steps still recorded `COMPLETED`/`exit_code=-1`** (audit TD-21). Separate accepted
   item, not in AP-102 scope — **deferred**.

No additional safety defects were found within A-001/A-002 scope.
