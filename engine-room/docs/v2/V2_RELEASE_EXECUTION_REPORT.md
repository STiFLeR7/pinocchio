# Release Execution Report — Nexus v2.0.0

**Status: Released.** `v2.0.0` is tagged on `master` at the merge commit of PR #9. This report documents
what was actually executed against `docs/v2/V1_RELEASE_READINESS_REPORT.md`'s seven-commit plan, including
one deviation the plan did not anticipate and the two blockers found and resolved during merge.

---

## 1. Commit Execution

Phase 1 (Verify Clean State) confirmed the working tree matched Release Readiness exactly: 41 modified
files, 3 untracked (`LICENSE`, `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md`,
`tests/unit/nexus_execution/actuation/test_dispatch.py`), plus `docs/v2/V1_RELEASE_READINESS_REPORT.md`
written moments before this session began. Full suite (3215 passed, 1 unrelated skip), mypy --strict (388
files), ruff check, and a wheel build all re-verified green before any commit was made.

The seven-commit plan from `docs/v2/V1_RELEASE_READINESS_REPORT.md` §7 was executed exactly as written, in
order, with no regrouping and no squashing:

| # | Commit | Hash | Files |
|---|---|---|---|
| 1 | `fix(execution,workflows): scope Runtime Session identity to the goal, not the work-item key alone` | `cbd3177` | 5 |
| 2 | `fix(workflows): match restart-seeding to the goal actually being run` | `4af2ffb` | 3 |
| 3 | `docs(rc2): execution identity & session isolation report` | `a1137bf` | 1 |
| 4 | `chore(release): graduate v2 packages from 2.0.0a1 to 2.0.0` | `f4c3b58` | 33 |
| 5 | `docs(release): add LICENSE; changelog entry for v2.0.0` | `f921995` | 2 |
| 6 | `docs(v2): reconcile operator guide and ADR ratification report with RC2 and current ADR status` | `cebce51` | 2 |
| 7 | `docs(release): v2.0.0 release readiness report` | `d07dc14` | 1 |

Each commit's staged files were verified against the plan's file list before committing (`git status
--short`), and the full suite was re-run after commit 4 (the only commit touching behavior-adjacent
metadata — `pyproject.toml`'s `pydantic<3` ceiling) to confirm no drift: still 3215 passed, 1 skipped.

**One deviation, found during Phase 4 (Merge), not anticipated by the plan:**

| # | Commit | Hash | Files | Reason |
|---|---|---|---|---|
| 8 | `style(release): apply ruff format to RC2's changed files` | `65ad52d` | 4 | `core-ci.yml`'s Ruff job runs both `ruff check` and `ruff format --check`; this release's own Phase 1/3 validation had only run the former. Pushing the branch surfaced a real CI failure: 4 of RC2's own files (`coordinator.py`, `test_constitutional_spine.py`, `test_scheduler.py`, `test_bridge.py`) needed reformatting. Whitespace/line-wrap only — confirmed via diff inspection, and via a full re-run of the test suite, ruff check, and `ruff format --check` after applying it, all green. Presented to the user as an explicit decision before committing (this was not authorized by the original plan); the user chose to add it as commit 8 rather than merge with a failing check or halt the release. |

## 2. Merge Summary

- **PR:** #9, "RC1 — v2 Productization & GA Preparation" (`release/rc1-v2-productization` → `master`), opened during RC1, already existed at the start of this session.
- **Pre-existing blockers found at merge time, not before:**
  1. CI's `Ruff (lint + format)` job failing (resolved by commit 8 above).
  2. Branch protection's required-conversation-resolution rule blocked the merge on two unresolved automated-review threads (`chatgpt-codex-connector`), filed before this session against `nexus_workflows/spine/coordinator.py` and `nexus_execution/actuation/dispatch.py`. Both described — independently and in detail — the exact two defects RC2 fixed in commits 1–2 above (node-only `package_identity` scoping; unfiltered `_seed` reconstruction). Marked outdated by GitHub (code had since changed) but still required manual resolution. Presented to the user; resolved on explicit instruction, since both described already-fixed defects.
- **Merge strategy:** regular merge commit (`gh pr merge 9 --merge`), matching every prior merge to `master` in this repository's history (`Merge pull request #N from ...` — no prior squash or rebase merges exist).
- **Merge commit:** `07097ac0292b9a2d9a05dd336793350fe5a9f6fd`.
- **Required status check** (`Lint, Type Check & Test`, from `.github/workflows/ci.yml`, v1-scoped): passed. All other CI jobs (`Ruff (lint + format)`, `MyPy (strict)`, `PyTest + coverage`, `Build verification`, from `core-ci.yml`): passed at merge time.

## 3. Tag Verification

- **Tag:** `v2.0.0` (annotated).
- **Points to:** `07097ac0292b9a2d9a05dd336793350fe5a9f6fd` — confirmed identical to the merge commit via `git rev-parse v2.0.0^{commit}`.
- **On `master`:** confirmed via `git merge-base --is-ancestor v2.0.0 origin/master`.
- **No collision:** confirmed `v2.0.0` did not previously exist (only `v1.0.0`/`v1.0.1`/`v1.1.0` existed, all for the unrelated v1 lineage); `git push origin v2.0.0` reported `[new tag]`.
- **Pushed to `origin`.**

## 4. Validation Results

Re-run against the final merged state (`master` tip / tag `v2.0.0`):

| Check | Result |
|---|---|
| Full test suite | 3215 passed, 1 skipped (opt-in `NEXUS_CLAUDE_SMOKE`, unrelated), 0 failed — unchanged from Release Readiness |
| mypy --strict (30-package v2 scope, matching `core-ci.yml`) | Clean, 388 source files |
| ruff check | Clean, repository-wide |
| ruff format --check (v2 scope) | Clean, 696 files — closed the gap commit 8 fixed |
| Wheel build | `nexus-2.0.0-py3-none-any.whl`, 31/31 v2 packages + `nexus` present |
| CI (GitHub Actions, on the actual merge commit) | All 5 jobs green: `Lint, Type Check & Test`, `Ruff (lint + format)`, `MyPy (strict)`, `PyTest + coverage`, `Build verification` |

No regression against the numbers `V1_RELEASE_READINESS_REPORT.md` §4 recorded.

## 5. Repository State

- `pyproject.toml`: `version = "2.0.0"`.
- All 31 `nexus_*/__init__.py`: `__version__ = "2.0.0"` (verified individually, all consistent).
- `CHANGELOG.md`: `## [2.0.0] — 2026-07-23 — "Constitutional Spine"` entry present.
- `LICENSE`: present (MIT, matching `pyproject.toml`'s declaration).
- Working tree: clean (`git status --short` empty) on both the local branch and `origin/master`.
- Local branch `release/rc1-v2-productization` and `origin/master` now share the same tip (`07097ac`) as ancestors; the branch itself was left in place (not deleted — deleting it was outside this milestone's scope and not requested).

## 6. Final Release Status

**Nexus v2.0.0 is released.** Tag `v2.0.0` on `master`, commit `07097ac0292b9a2d9a05dd336793350fe5a9f6fd`,
pushed to `origin`. Every architectural correctness issue Production Readiness (P17), RC1, and RC2
identified as a GA blocker is committed, merged, and tagged — including RC2's fix for the specific defect
(cross-goal execution-identity corruption) that caused RC1 to downgrade its own GA recommendation. The
four-way version disagreement is resolved consistently across the tagged commit. CI is green on the merge
commit across all five jobs, including the required branch-protection check.

**Known limitations carried into this release, unchanged from `V1_RELEASE_READINESS_REPORT.md` §5 and
`RC2_EXECUTION_IDENTITY_REPORT.md` §9** — none block this release, all are pre-existing and already
disclosed: no v1→v2 data migration tool; unversioned durable schema; ADR-009 (runtime-selection ownership)
filed but unratified; `WorkflowCoordinator`'s duplicate-driver blast radius; `build_human_interaction()`'s
dormant duplicate composition root; the Constitution's undisclosed ADR-009 dispute; root `README.md`'s
silence on v2's existence (§6 of Release Readiness — still an open decision for the user, not resolved by
this release).

**One new fact this execution pass surfaced:** Release Readiness's claim of "ruff clean repository-wide"
was based on `ruff check` alone; `ruff format --check` (also run by CI) was not verified until this pass,
and did find real drift (resolved in commit 8). Future validation passes for this repository should run
both.
