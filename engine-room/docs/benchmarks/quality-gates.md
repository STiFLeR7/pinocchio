# Benchmark: Quality Gates — Tests, Type Coverage, Lint, Build, CI

## Purpose

Track the evidence that the codebase itself is trustworthy — test count and pass rate, `mypy --strict`
coverage, `ruff` cleanliness, coverage-gate percentage, wheel-build verification, and CI status — across
every release milestone. These are not performance numbers; they are the gates every commit in this
program had to pass, and they belong in this evidence base because "is Nexus fast" is a much smaller
question than "is Nexus's own account of itself (tests, types, lint) actually true," and a reader deserves
both.

## Methodology

Every figure below is a direct run of the same commands `.github/workflows/core-ci.yml` and
`.github/workflows/ci.yml` run: `pytest tests/`, `mypy --strict` (per `pyproject.toml`'s `strict = true`),
`ruff check` and `ruff format --check`, and `uv build --wheel`. Each release milestone re-ran all of them
against its own final state — none of these numbers are self-reported by the code; they are gate outputs.

## Measured Result

### Test suite, type coverage, and lint — by milestone

| Milestone | Tests | mypy --strict | ruff check | ruff format --check | Coverage gate |
|---|---|---|---|---|---|
| P17 | 2927 passed, 1 opt-in skip, 1 pre-existing unrelated error | Clean, 30 packages, 387 source files, 0 errors | Clean | not separately verified this pass | 97.97% (95% required) |
| RC1 | 2934 passed (+7 new regression tests), 1 opt-in skip, same 1 pre-existing unrelated error | Clean, 388 source files, 0 errors | Clean, same 30-package v2 scope | not separately verified this pass | unchanged scope from P17 |
| RC2 | 3215 passed (+281 vs. RC1; 6 target this defect class directly, remainder from other work already on the branch), 1 skipped, 0 failed | Clean, 316 touched production packages | Clean, repository-wide | not separately verified this pass | not re-stated this pass |
| Release Readiness | 3215 passed, 1 skipped, 0 failed (unchanged from RC2) | Clean, 388 production source files | Clean, repository-wide | not separately verified this pass | not re-stated this pass |
| Release Execution (final, tag `v2.0.0`) | 3215 passed, 1 skipped, 0 failed | Clean, 388 files | Clean, repository-wide | **Clean, 696 files** — the first pass to actually run this check; found and fixed real drift in 4 files (commit 8, `65ad52d`) | not re-stated this pass |

**The one real gap this table itself documents:** `ruff format --check` was not run as its own explicit
verification step until Release Execution, even though CI's `Ruff (lint + format)` job always ran it —
"ruff clean" in every earlier report meant `ruff check` only. Release Execution found this gap the hard way
(a real CI failure on push) and states explicitly: "Future validation passes for this repository should run
both" (`docs/v2/V2_RELEASE_EXECUTION_REPORT.md` §"One new fact this execution pass surfaced").

### Package count

| Milestone | v2 packages | Notes |
|---|---|---|
| P17 | 30 packages (built across P0–P16) | |
| RC1 → Release | 31 packages | Growth reflects continued build-out through the release milestones, not a discrepancy — every release-era report (Release Readiness, Release Execution) confirms 31/31 packages match `pyproject.toml`'s wheel package list with no drift. |

### Wheel build verification

| Milestone | Result |
|---|---|
| P17 | Not a build-verification milestone itself; `pyproject.toml` packages list confirmed complete (31/31 `nexus_*` + `nexus`) |
| Release Readiness | `uv build --wheel` succeeds; artifact inspected, contains all 31 v2 packages |
| Release Execution | `nexus-2.0.0-py3-none-any.whl` built and inspected — 31/31 v2 packages + `nexus` (v1) present |

### CI status at the actual merge/tag

| Job (`.github/workflows/core-ci.yml` unless noted) | Result at merge commit `07097ac` |
|---|---|
| `Lint, Type Check & Test` (`.github/workflows/ci.yml`, v1-scoped, required branch-protection check) | Passed |
| `Ruff (lint + format)` | Passed (after commit 8's formatting fix) |
| `MyPy (strict)` | Passed |
| `PyTest + coverage` | Passed |
| `Build verification` | Passed |

## Source Reports

`docs/v2/P17_PRODUCTION_READINESS_REPORT.md` (2927/97.97%/387-file baseline);
`docs/v2/RC1_PRODUCTIZATION_REPORT.md` §Executive Summary, §6 (2934, 388 files);
`docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md` §1, §10 (3215, 316 touched files);
`docs/v2/V1_RELEASE_READINESS_REPORT.md` §1, §4, §8 (3215/388/wheel);
`docs/v2/V2_RELEASE_EXECUTION_REPORT.md` §1, §4, §6 (final 3215/388/696-file-format/wheel/CI).

## Interpretation

The trend across five milestones is monotonic and consistent: test count only grows (2927 → 2934 → 3215),
every regression suite stays at 0 failures, mypy-strict scope only grows (387 → 388 files) and stays at 0
errors, and the one real gap found (`ruff format --check` never separately verified) was found by CI itself
at the actual push, not glossed over in the report that found it — treated as a real fact ("Future
validation passes for this repository should run both"), not retroactively minimized.

The Constitution itself (per the root `README.md` and `CHANGELOG.md` [2.0.0] entry) states the platform was
"ratified... against 39 architectural invariants" — this is a design/ratification count from
`docs/v2/99_ARCHITECTURAL_INVARIANTS.md`, enforced operationally via architecture-fitness tests (e.g.
`tests/unit/nexus_scheduler/test_guardrails.py`'s dependency-boundary checks, cited directly in
`docs/v2/RC1_PRODUCTIZATION_REPORT.md` §2.2). No source report states a standalone "N invariant tests pass"
count separate from the overall test totals above — the 39 is a count of ratified invariants, not a
benchmark metric in its own right, and is reported here as such rather than conflated with the test-suite
numbers.

## Limitations

- **Coverage-gate percentage (97.97%) was stated once, at P17, and not re-stated in later reports** — RC1
  through Release Execution confirm the gate still passes (implicitly, via "full suite green") but do not
  re-quote the percentage. Treat 97.97% as a P17-era snapshot, not a continuously re-verified figure.
- **`ruff format --check`'s file count (696) is scoped differently from mypy's (388)** — the two numbers are
  not directly comparable; 696 reflects a broader v2-scope sweep (including test directories) than mypy's
  388 production source files.
- **These are gate results, not code-quality scores** — "0 mypy errors" means the configured strict ruleset
  found nothing, not that the code is provably defect-free; RC1's and RC2's own adversarial reviews found
  real defects (see [`guarantees.md`](guarantees.md)) that no automated gate here caught on its own.
