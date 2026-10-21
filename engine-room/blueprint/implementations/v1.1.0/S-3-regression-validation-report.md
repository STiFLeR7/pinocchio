# Regression Validation Report (S-3)

> Full-suite, lint, and type validation for S-3. (Named `S-3-regression-validation-report.md` to
> preserve the S-2 record at `regression-validation-report.md` — blueprint memory is never overwritten.)
> Run with the project venv (`.venv/Scripts/python.exe`).

---

## 1. Gate results

| Gate | Command | Result |
|---|---|---|
| Full test suite | `pytest -q` | **166 passed** in ~42s |
| New S-3 tests | `pytest tests/unit/execution/test_sandbox_enforcement.py -v` | **14 passed** |
| Lint | `ruff check nexus/ tests/` | **All checks passed!** |
| Types | `mypy nexus/ --ignore-missing-imports` | **Success: no issues found in 57 source files** |

Progression: 143 (v1.0.1) → 152 (S-2, +9) → **166 (S-3, +14)**. No net loss; **zero regressions**.

## 2. No regressions (key point)

Unlike S-2, **no existing test required reconciliation**. S-3 added a startup gate and provider
metadata/availability without changing resolution outcomes for any configuration already exercised by
the suite:

- The startup gate (`validate_sandbox_startup`) is **new** and only invoked in the lifespan; the
  existing lifespan/startup tests (`test_startup_validation.py`, A-001) use `enabled=False`, which the
  gate **allows** (warns) — they pass unchanged.
- The `policy_enforced` field is **additive** to `sandbox.created.data`; existing audit tests
  (`test_sandbox.py`) assert on `event_type`, not on this field — unaffected.
- `_resolve_provider` now reads the shared `RECOGNIZED_PROVIDERS` registry but its **outcomes are
  identical** to S-2 (docker/mock/local resolve; disabled/unknown fail closed) — confirmed by the S-2
  suite (9) and `test_s2_failclosed_preserved`.
- `ensure_available()` is only called by the new startup gate and provider-level tests; the existing
  Docker command-construction test (`test_docker_sandbox_command_construction`) does not invoke it and
  is unaffected.

## 3. Suites confirmed green (spot list)

- S-2 resolution suite (`test_sandbox_resolution.py`, 9) — **all green** (S-2 preserved).
- `test_sandbox.py` (policy defaults, fallback, mock/docker construction, mock execution audit,
  lifecycle, collector) — **green**.
- `test_timeout_resolution.py` (incl. the S-2-reconciled Nexus test) — **green**.
- `test_gemini.py`, `test_claude.py`, `test_nexus.py`, `test_governance.py`,
  `test_p0_hardening.py`, `test_scheduler_foundation.py`, `test_startup_validation.py`,
  e2e `test_mvp_workflow.py` — **green**.

## 4. Diff scope (minimal)

| File | Type |
|---|---|
| `nexus/core/exceptions.py` | source (+1 exception) |
| `nexus/execution/sandbox/provider.py` | source (enforces_policy, ensure_available, RECOGNIZED_PROVIDERS) |
| `nexus/execution/sandbox/manager.py` | source (shared registry, audit field, startup gate) |
| `nexus/execution/sandbox/__init__.py` | source (exports) |
| `nexus/api.py` | source (lifespan gate call) |
| `tests/unit/execution/test_sandbox_enforcement.py` | new test (14) |

No changes to Nexus/Gemini/Claude source, scheduler, governance, memory, schema, migrations, or config
defaults.

## 5. Explicit proofs (required)

| Proof | Test(s) |
|---|---|
| Docker-unavailable paths fail closed | `test_startup_docker_unavailable_aborts`, `test_docker_ensure_available_raises_when_missing`, `test_docker_ensure_available_raises_on_nonzero` |
| Policy-enforcement failures fail closed | docker-unavailable abort (above) + `test_execute_audit_declares_policy_enforcement` (honest declaration) |
| Startup validation prevents unsafe runtime states | `test_startup_unknown_provider_aborts`, `test_startup_docker_unavailable_aborts` (abort before any execution) |
| S-2 behavior unchanged | `test_s2_failclosed_preserved` + full S-2 suite (9) green |

## 6. Verdict

**PASS, zero regressions.** All gates green; S-2 guarantees preserved; S-3 objectives (R-03, R-06, R-07)
validated.
