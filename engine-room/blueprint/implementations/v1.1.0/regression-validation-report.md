# Regression Validation Report (S-2)

> Full-suite, lint, and type validation for S-2, plus the one expected regression and its
> in-scope reconciliation. Run with the project venv (`.venv/Scripts/python.exe`).

---

## 1. Gate results

| Gate | Command | Result |
|---|---|---|
| Full test suite | `pytest -q` | **152 passed** in ~37s |
| New S-2 tests | `pytest tests/unit/execution/test_sandbox_resolution.py -v` | **9 passed** |
| Lint | `ruff check nexus/ tests/` | **All checks passed!** |
| Types | `mypy nexus/ --ignore-missing-imports` | **Success: no issues found in 57 source files** |

Baseline before S-2: 143 passing (v1.0.1). After S-2: **152** (= 143 + 9 new). No net loss.

## 2. The one expected regression (caused by the intended R-01 change)

| Test | Symptom | Root cause | Reconciliation |
|---|---|---|---|
| `test_timeout_resolution.py::test_nexus_execute_command_uses_research_timeout` | `KeyError: 'timeout'` | The test passed real `test_settings` (`sandbox.enabled=False`) into Nexus `execute_command`; the new fail-closed default makes `SandboxManager(...)` raise **before** the monkeypatched `execute` is reached (Nexus catches it), so `captured["timeout"]` is never set. | Test now sets `test_settings.sandbox = SandboxConfig(enabled=True, provider="mock")` so resolution succeeds and the monkeypatched `execute` is reached. **No Nexus source change.** |

This is the **intended** behavior change surfacing correctly: under the new contract, executing a command
requires explicit sandbox configuration. The test encoded the old default-host assumption and was
updated to configure the sandbox it needs — exactly what an operator must now do.

### Why the CLI runner timeout tests did NOT regress
`test_claude_execute_uses_claude_timeout` / `test_gemini_execute_uses_gemini_timeout` use the same
`test_settings` (`enabled=False`) but still pass: the CLI runners **write the timeout step record
before** constructing `SandboxManager`, so the asserted `timeout_threshold` is persisted even though the
subsequent `SandboxManager(...)` raises and is caught by the runner. Only the Nexus test asserted on the
monkeypatched `execute` being reached, hence it alone needed reconciliation.

## 3. Suites confirmed unaffected (spot list)

- `test_sandbox.py` — existing resolution fallback (`settings=None → Local`), mock/docker construction,
  mock execution audit (`created/started/terminated/failure/timeout`), lifecycle orphan cleanup,
  artifact collector — **all green** (audit logging preserved, abstraction preserved).
- `test_gemini.py` / `test_claude.py` — adapter construction + `execute("echo …")` (settings=None →
  Local path retained) — **green**.
- `test_nexus.py` — mock-path execute/checkpoint/persist (does not invoke `execute_command`) — **green**.
- `test_governance.py`, `test_policy_externalization.py`, `test_p0_hardening.py`,
  `test_scheduler_foundation.py`, `test_research.py`, `test_briefing.py`, e2e `test_mvp_workflow.py`
  (MagicMock settings → Local path) — **green**.

## 4. Diff scope (minimal)

| File | Type |
|---|---|
| `nexus/core/exceptions.py` | source (+1 exception class) |
| `nexus/execution/sandbox/manager.py` | source (`_resolve_provider` fail-closed + import) |
| `tests/unit/execution/test_sandbox_resolution.py` | new test (9) |
| `tests/unit/execution/test_timeout_resolution.py` | test reconciliation (1 settings line + import) |

No changes to Nexus/Gemini/Claude source, scheduler, governance, memory, schema, migrations, or config
defaults.

## 5. Verdict

**PASS, no unresolved regressions.** The single expected failure was an intended-behavior consequence
reconciled within scope (test settings only, no Nexus source change). All gates green.
