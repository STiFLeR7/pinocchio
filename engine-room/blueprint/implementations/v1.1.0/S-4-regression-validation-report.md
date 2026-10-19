# Regression Validation Report (S-4)

> Full-suite, lint, and type validation for S-4. (Named `S-4-regression-validation-report.md` to
> preserve the S-2 and S-3 records — blueprint memory is never overwritten.) Run with the project venv
> (`.venv/Scripts/python.exe`).

---

## 1. Gate results

| Gate | Command | Result |
|---|---|---|
| Full test suite | `pytest -q` | **178 passed** in ~44s |
| New S-4 tests | `pytest tests/unit/execution/test_workspace_confinement.py -v` | **12 passed** |
| Lint | `ruff check nexus/ tests/` | **All checks passed!** |
| Types | `mypy nexus/ --ignore-missing-imports` | **Success: no issues found in 58 source files** |

Progression: 143 (v1.0.1) → 152 (S-2) → 166 (S-3) → **178 (S-4, +12)**. **Zero regressions.**

## 2. No regressions (key point)

S-4 added a new confinement seam and routed Nexus file tools through it without altering any
behavior the suite already relied on:

- **Nexus existing tests** (`test_nexus.py`) green: the mock-path `write_file` writes
  `mcp_report.md` to the workspace (`repository="."`), which resolves **inside** the workspace and is
  allowed — unchanged behavior.
- **CLI runtimes** (`test_gemini.py`, `test_claude.py`, 12 tests) green: Gemini/Claude have **no
  file-tool path**, so workspace confinement does not apply to or alter them.
- **Sandbox / resolution / enforcement** (`test_sandbox.py`, `test_sandbox_resolution.py`,
  `test_sandbox_enforcement.py`) green: S-2/S-3 behavior unchanged (the confinement seam is additive
  and independent of provider resolution).
- **Timeout, governance, scheduler, e2e** suites green.

## 3. Explicit proofs (required)

| Proof | Test(s) |
|---|---|
| Path traversal fails | `test_parent_traversal_denied`, `test_deep_traversal_denied` |
| Workspace escape fails | `test_absolute_escape_denied`, `test_nexus_read_escape_denied`, `test_nexus_write_escape_denied` |
| Approved workspace access succeeds | `test_valid_relative_path_allowed`, `test_nexus_read_within_workspace_succeeds`, `test_nexus_write_within_workspace_succeeds` |
| Existing CLI runtimes unaffected | `test_gemini.py` + `test_claude.py` (12) green; no file-tool path in CLI runtimes |

## 4. Diff scope (minimal)

| File | Type |
|---|---|
| `nexus/core/exceptions.py` | source (+1 exception) |
| `nexus/execution/sandbox/confinement.py` | source (new seam) |
| `nexus/execution/sandbox/__init__.py` | source (export) |
| `nexus/execution/runners/nexus.py` | source (file-tool confinement + `_workspace_cwd` helper; **no new tools, no feature expansion**) |
| `tests/unit/execution/test_workspace_confinement.py` | new test (12) |

No changes to Gemini/Claude source, scheduler, governance, memory, events, schema, migrations, or
config defaults. No Track-H Nexus work (search/planning/cancellation/resume).

## 5. Verdict

**PASS, zero regressions.** All gates green; R-05 closed; S-2/S-3 guarantees and CLI runtimes
unaffected.
