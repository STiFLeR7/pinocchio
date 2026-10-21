# Release Readiness Report — Nexus v2.0.0

**Status:** Preparation complete. **Nothing has been committed, merged, or tagged** — every action below
was applied to the working tree only, per this milestone's explicit instruction. This report is the
single artifact a subsequent, explicit "commit and release" instruction should act on.

**Scope note (a decision made mid-milestone):** the governing prompt titled this milestone "v1.0.0."
That version collides with real repository history — `v1.0.0` is an existing git tag (commit `4566020`)
for the original v1 monolith's first release, and every v2 package already self-declared
`__version__ = "2.0.0a1"` throughout its P0–P17 build-out. `docs/v2/P17_PRODUCTION_READINESS_REPORT.md`
§7.2 had already flagged this exact conflict and explicitly deferred the choice to "a
product/release-management call." Asked directly, the user confirmed **`v2.0.0`** as the correct
version identifier. Every deliverable below (CHANGELOG entry, version bumps, this report's filename)
reflects that decision; "V1" in this report's filename is this document's own round-number in the
P#/RC#/V# reporting sequence, not a product version claim.

---

## 1. Executive Summary

RC1 and RC2 closed every architectural correctness issue Production Readiness identified. This
milestone's job was narrower and purely operational: make the repository internally consistent, prepare
real release artifacts, and produce evidence for a GA decision — no redesign, no new capability, no
speculative cleanup.

Two parallel audits (Phase 1: repository audit; Phase 2: release consistency) ran against the full
working tree, cross-checking documentation, packaging, CI, ADRs, and exports against actual code. Both
converged on the same short list of genuine gaps, all fixed in this pass:

- **A four-way version disagreement**, flagged since P17 and never resolved by RC1: `pyproject.toml`
  read `0.1.0`, 24 of 31 v2 packages read `2.0.0a1`, 7 v2 packages declared no version at all, and
  `CHANGELOG.md` had no v2 entry whatsoever. **Resolved**: all 31 v2 packages and `pyproject.toml` now
  read `2.0.0`; the missing 7 now declare it too.
- **A missing `LICENSE` file** — declared in `pyproject.toml` and linked from a `README.md` badge, but
  the file itself never existed. **Resolved.**
- **An unbounded `pydantic` dependency**, a one-line hardening `docs/v2/P17_PRODUCTION_READINESS_REPORT.md`
  §7.5 recommended and RC1 left outstanding. **Resolved** (`>=2.0,<3`).
- **A stale `ADR_RATIFICATION_REPORT.md` line** claiming ADR-009 "remains to be written" — it was filed
  during RC1, three weeks before this milestone. **Resolved.**
- **An undocumented orphan package** (`nexus_human_interaction`) with the exact "built, unwired" shape
  the Operator Guide already annotates for four sibling packages, but missing that annotation.
  **Resolved.**
- Everything else the audits found is either a false alarm (verified and closed, no action needed) or a
  genuine but non-blocking gap, documented rather than fixed because fixing it would exceed this
  milestone's additive, no-redesign charter (§5).

**The one finding that matters most for a release decision:** as of this report, **RC2's fixes, RC1's
prior commits' consistency, and every change this milestone made exist only in the working tree.** Git
HEAD is still `b4b1ef3` (RC1's last commit). A release cut from HEAD today would ship RC1's code —
including the exact defect (silent cross-goal execution-identity corruption) RC2 exists to fix. This is
not a discovered problem; it is the expected, correct state for a milestone that was explicitly told not
to commit. §7 gives the full commit plan needed to close this gap.

Full validation: **3215 passed, 1 skipped (opt-in, unrelated), 0 failed.** mypy --strict clean across all
388 v2 source files. ruff clean repository-wide. Wheel build verified (`nexus-2.0.0-py3-none-any.whl`,
all 31 v2 packages present in the artifact).

---

## 2. Repository Audit (Phase 1)

Full findings preserved in the dispatched audit's transcript; summarized by category:

| Category | Finding | Verdict |
|---|---|---|
| Foreign directory | `pi_eval/` (74 MB, an unrelated external coding-agent tool, "Pi Agent Harness") sits at the repo root with its own nested `.git` | **Not a repository concern** — `.gitignore:92` explicitly excludes it (`/pi_eval/`), it has zero commits in Nexus's history, and zero references from any Nexus file, doc, or CI workflow. Local clutter, not release risk. |
| Orphan packages | `nexus_operator`, `nexus_briefings`, `nexus_research`, `nexus_integration` — zero production importers | **Unwired but intentional/documented** — matches P17 finding R6/R1 exactly, unchanged, already annotated in `OPERATOR_GUIDE.md` |
| Orphan package (newly found) | `nexus_human_interaction` — same "zero production importer" signature as the above, but **not** annotated as such anywhere | **Fixed this pass** — `OPERATOR_GUIDE.md` now carries a `‡` footnote matching the existing annotation pattern |
| Composition-root seam unused | `nexus_history.build_history()` has zero external callers, though the package itself is used | Noted, not fixed — the seam being unused doesn't affect the package's real (used) surface |
| Duplicate composition root | `WorkflowCoordinator` (`nexus_workflows/coordinator.py`) bypasses Execution Actuation — P17 finding R4, "low exposure" | **Blast radius has grown**: now directly instantiated by `nexus_briefings`, `nexus_operator`, `nexus_research`, and `nexus_runtime_adapters/crossruntime.py` — all four themselves unwired, so no live INV-02 violation exists today, but this should be re-scored rather than silently carried forward again (§5) |
| Duplicate composition root (newly found) | `build_human_interaction()` constructs its own independent `ConstitutionalPipeline`/`ApprovalExchange`, disconnected from `nexus_scheduler.bootstrap()`'s | Dormant (never called in production), same shape as a previously-fixed real defect (P17's two-`HarnessRegistry` finding) — documented, not fixed (§5) |
| TODO/FIXME/XXX | Grepped all of `nexus/`, all 31 `nexus_*` packages, `tests/`, `scripts/` | **Zero genuine hits in v2.** Three hits total, all in v1, all domain vocabulary ("reminders & TODOs"), not code TODOs |
| Stale/abandoned files | Searched for `*_old.py`, `*_backup.py`, `*.bak`, `scratch_*.py`, `*_wip.py`, etc. | **None found** |
| Third/abandoned v2 entrypoint | Checked for any `__main__.py` beyond the two known entrypoints, and deleted-entrypoint git history | **None — exactly two entrypoints ever existed** (`nexus/__main__.py`, `nexus_scheduler/__main__.py`) |
| pyproject packages list vs. disk | Cross-checked `[tool.hatch.build.targets.wheel].packages` against every `nexus_*` directory | **Perfect match, 31/31, no drift** |

---

## 3. Release Consistency (Phase 2)

| Area | Finding | Verdict |
|---|---|---|
| ADR statuses | ADR-001–004, 007, 008: Accepted. ADR-009: Proposed (unratified, correctly described as such everywhere it's cited) | Consistent |
| `ADR_RATIFICATION_REPORT.md` | Claimed ADR-009 "remains to be written"; it was filed 2026-07-21 (RC1), under a narrower topic than originally anticipated | **Fixed** — annotated in place with an update note, original text preserved |
| `99_ARCHITECTURAL_INVARIANTS.md` / `ARCHITECTURE_CONSTITUTION.md` vs. ADR-009 | INV-37 and 5 restatements of "Orchestration selects the runtime" in the Constitution do not disclose that ADR-009 has filed a wording correction against exactly this invariant | **Not fixed** — the invariants file and Constitution are explicitly "Preserve" documents this milestone must not alter; a disclosure note is a defensible fast-follow but was judged higher-risk than this pass's mandate justifies. Documented here and in §5. |
| Package exports (`__all__` vs. cross-package imports) | Sampled 6 central packages; every cross-package import resolves against the target's `__all__`; no dead exports found | Consistent |
| CI (`ci.yml`, `core-ci.yml`) | Both enumerate all 31 v2 packages correctly; Python 3.12 everywhere; `mypy --strict` (via `pyproject.toml`'s `strict = true`) and `ruff check` both run; coverage-gate package exclusions match P17's own documented history | Consistent |
| `pyproject.toml` scripts | Both `nexus` and `nexus-v2` console scripts resolve to real, importable, callable `main` functions (verified by direct import) | Consistent |
| Dependency inventory | Re-ran P17's AST-style import scan: zero v2 packages import any v1-only dependency (fastapi, sqlalchemy, discord.py, etc.) — v2's entire third-party footprint is still `pydantic` alone | Consistent, confirmed unchanged |
| `pydantic` upper bound | P17 recommended `<3`; outstanding at RC1's HEAD | **Fixed this pass** |
| 7 packages with no `__version__` | `nexus_policy`, `nexus_integration`, `nexus_estimation`, `nexus_engineering`, `nexus_intent`, `nexus_repository`, `nexus_history` | **Fixed this pass** — `__version__ = "2.0.0"` added, matching the existing pattern in the other 24 packages |
| `pyproject.toml [project].version` vs. `nexus/__init__.py` | Now `2.0.0` vs. v1's own `0.1.0` — a real, but pre-existing and already-documented, tension (`CHANGELOG.md`'s own "Known Issues" for 1.0.1/1.1.0 defer this v1-side fix explicitly) | Accepted as-is — there is exactly one `pyproject.toml` for the whole repository; its `[project].version` must describe the one distributable artifact, and `2.0.0` is what this milestone's release is. Fixing v1's internal string is out of this milestone's scope. |
| `OPERATOR_GUIDE.md` vs. RC1/RC2 | Entrypoint and scheduler-complexity descriptions accurate; RC2 was not mentioned anywhere, and its two disclosed-but-unfixed risks were not carried into the troubleshooting table | **Fixed this pass** — added an RC2 pointer in the header, a troubleshooting row for the identity fix, and the `nexus_human_interaction` orphan-package footnote |
| Root `README.md` | Makes zero mention of v2 anywhere — version badge and release-status callout describe only v1 (`v1.0.0 + v1.0.1 alignment`) | **Not fixed — flagged for a decision** (§6). This is a communications/positioning question (how should v1 and v2 be presented together in the project's front door), not a technical defect; both audits independently judged it a call for the user, not the engineering program, to make — the same category of decision as the version-number question this milestone opened with. |

---

## 4. Validation Results (Phase 5)

| Check | Result |
|---|---|
| Full test suite (`pytest tests/`) | **3215 passed, 1 skipped, 0 failed** (skip is the opt-in `NEXUS_CLAUDE_SMOKE` smoke test, requires a live authenticated `claude` CLI — unrelated to this milestone) |
| mypy --strict | **Clean — 0 errors across 388 production source files** (all touched packages plus the full v2 surface) |
| ruff check | **Clean, repository-wide** |
| Packaging build | `uv build --wheel` succeeds; inspected artifact contains all 31 v2 `nexus_*` packages plus `nexus` |
| Replay validation | `test_pipeline_replays_from_the_durable_log`, RC2's `test_replay_after_two_concurrent_goals_reconstructs_each_independently`, `test_replay_reconstructs_scheduling_history` — all pass |
| Restart validation | `test_pipeline_restarts_from_the_last_completed_stage`, `test_pipeline_restarts_after_a_mid_execution_interruption`, `test_restart_never_double_dispatches` — all pass, unchanged by RC2's fix |
| Scheduler validation | Full `tests/integration/test_scheduler.py` (7 tests, including RC2's new `test_recurring_schedule_occurrences_each_run_their_own_goal`) — all pass |
| Approval validation | Full `tests/integration/test_approval_exchange.py` (5 tests) — all pass |
| Execution/identity validation | RC2's full regression set (dispatch unit tests, bridge cross-goal test, two-goal collision integration test) plus RC1's runtime-manager and policy-composition restart-safety tests (90 tests total across the 8 files most relevant to RC1/RC2) — all pass |

RC2 regressions confirmed still fixed: re-ran the exact reproduction scripts from RC2's own investigation
(two goals sharing work-item keys; three occurrences of one recurring schedule) directly against the
current working tree — no crash, no silent state adoption, each goal/occurrence independently completes
its own Intent→Knowledge run.

---

## 5. Remaining Risks

None of the following block GA; all are either dormant (no live code path exercises them), pre-existing
and already tracked, or explicitly deferred product/positioning decisions.

| # | Risk | Why not fixed here |
|---|---|---|
| 1 | RC2 §9's four carried-forward items: no v1→v2 data migration tool; unversioned durable schema; ADR-009 unratified; two frozen-contract candidates (`engineering_strategy`, `repository_understanding`) not yet frozen | Unchanged from RC2 — none are identity/collision defects, all pre-existing and already disclosed |
| 2 | `WorkflowCoordinator` duplicate driver (P17 R4) has grown from "one low-exposure caller" to four consumer-application callers | All four callers are themselves unwired from any entrypoint (§2), so no live single-owner (INV-02) violation exists today — but the trend should be re-scored, not silently re-deferred a third time |
| 3 | `build_human_interaction()` builds a second, disconnected `ConstitutionalPipeline`/`ApprovalExchange` pair | Dormant — never called in production. Same shape as a previously-fixed real defect (two `HarnessRegistry` instances), so it should be watched, not ignored, if `nexus_human_interaction` is ever wired into a live entrypoint |
| 4 | `ARCHITECTURE_CONSTITUTION.md` and `99_ARCHITECTURAL_INVARIANTS.md` don't disclose ADR-009's pending INV-37 correction | A disclosure-only note is low-risk but touches documents this milestone was told to preserve; recommended as a fast-follow rather than done unilaterally here |
| 5 | Root `README.md` doesn't mention v2 at all | Positioning/communications decision, not a technical gap — flagged for the user (§6) |
| 6 | RC2's own §9 risks (facade's dead `_identity` param on `execution_graph()`; Recovery's unconditional `checkpoint_ref=None`) | Unchanged from RC2 — both are read-path/wiring gaps, neither corrupts durable data, both already disclosed in `RC2_EXECUTION_IDENTITY_REPORT.md` |

---

## 6. Open Decision for the User

**Should the root `README.md` acknowledge v2 exists, and if so, how?** Both audits independently flagged
this as the single most visible artifact that is currently silent about the platform this release is
about (its version badge and "Release status" callout describe only v1's `v1.0.0`/`v1.0.1` lineage).
Options range from a short pointer section to `docs/v2/`, to a fuller repositioning once v2.0.0 ships.
This wasn't resolved unilaterally for the same reason the version-number question wasn't: it's a
product/communications call, not an engineering one. Recommend a follow-up decision before or shortly
after the actual release.

---

## 7. Commit Plan

Nothing has been committed. The full working-tree diff (43 files: 41 modified, 2 untracked, plus
`LICENSE` and `uv.lock`) groups into seven commits by engineering milestone, in dependency order:

**1. `fix(execution,workflows): scope Runtime Session identity to the goal, not the work-item key alone`**
- Files: `nexus_execution/actuation/dispatch.py`, `nexus_workflows/spine/bridge.py`,
  `tests/unit/nexus_execution/actuation/fixtures.py`, `tests/unit/nexus_workflows/spine/test_bridge.py`,
  `tests/unit/nexus_execution/actuation/test_dispatch.py` (new)
- Rationale: closes RC1's reported cross-goal Runtime Session collision and the independent cross-goal
  scope-lookup collision found while verifying it (RC2 §2.1–2.2).
- Reports: `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md` §2.1–2.2, §7.
- Expected impact: two goals sharing a work-item key no longer collide on Runtime Session or Validation
  event scope. No behavior change for single-goal runs (all pre-existing tests pass unchanged).

**2. `fix(workflows): match restart-seeding to the goal actually being run`**
- Files: `nexus_workflows/spine/coordinator.py`, `tests/integration/test_constitutional_spine.py`,
  `tests/integration/test_scheduler.py`
- Rationale: the deepest defect RC2 found — restart-seeding silently adopted an unrelated goal's
  completed state and skipped Intent→Actuation entirely (RC2 §2.3). Includes the corrected
  goal-identity-matching fix (not the first, correlation-based attempt, which broke recurring schedules).
- Reports: `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md` §2.3, §5–7.
- Expected impact: a second goal (or a second occurrence of one recurring schedule) sharing a durable log
  now always runs its own full pipeline. No behavior change for single-goal restart (all pre-existing
  restart tests pass unchanged).

**3. `docs(rc2): execution identity & session isolation report`**
- Files: `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md` (new)
- Rationale: the full audit, root-cause analysis, identity model, and validation evidence behind commits
  1–2, closing RC1's risk #12.

**4. `chore(release): graduate v2 packages from 2.0.0a1 to 2.0.0`**
- Files: all 31 `nexus_*/__init__.py` (24 bumped, 7 newly versioned), `pyproject.toml` (version +
  `pydantic<3` ceiling), `uv.lock` (regenerated)
- Rationale: resolves the four-way version disagreement `P17_PRODUCTION_READINESS_REPORT.md` §7.2
  flagged as a pre-GA blocker and RC1 left unresolved; applies P17 §7.5's `pydantic` ceiling
  recommendation.
- Expected impact: none behavioral — pure metadata. Full suite re-verified green after this commit.

**5. `docs(release): add LICENSE; changelog entry for v2.0.0`**
- Files: `LICENSE` (new), `CHANGELOG.md`
- Rationale: closes the licensing gap (declared in `pyproject.toml`/README badge, file never existed);
  records this release per Keep a Changelog, honestly scoped (added/fixed/changed/known-limitations/
  migration notes, no capability exaggeration).

**6. `docs(v2): reconcile operator guide and ADR ratification report with RC2 and current ADR status`**
- Files: `docs/v2/OPERATOR_GUIDE.md`, `docs/v2/ADR_RATIFICATION_REPORT.md`
- Rationale: closes the `nexus_human_interaction` unannotated-orphan gap, the stale "ADR-009 not yet
  written" line, and adds RC2 cross-references alongside the existing RC1 ones.

**7. `docs(release): v2.0.0 release readiness report`**
- Files: `docs/v2/V1_RELEASE_READINESS_REPORT.md` (this document)
- Rationale: the audit, consistency check, validation evidence, and GA recommendation this milestone
  produced.

After commit 7, a release actually reflects RC2's fixes and this milestone's consistency work — closing
the gap described in §1's "one finding that matters most."

---

## 8. Release Checklist

- [x] Semantic version chosen and applied consistently (`2.0.0`, resolved with the user; §Scope note)
- [x] Package metadata verified (`pyproject.toml` packages list matches disk 31/31; console scripts
      resolve)
- [x] Dependency inventory verified (v2's only third-party dependency is `pydantic`, now `<3`-bounded)
- [x] Licensing verified and closed (`LICENSE` added, matches `pyproject.toml`/README declaration)
- [x] Changelog prepared (`CHANGELOG.md` v2.0.0 entry — added/fixed/changed/known-limitations/migration)
- [x] Release notes prepared (this report + the CHANGELOG entry serve as release notes)
- [x] Install instructions verified (both console scripts importable and callable; wheel builds and
      contains all packages)
- [x] Full test suite green (3215 passed, 1 unrelated skip)
- [x] mypy --strict clean (388 files)
- [x] ruff clean
- [x] Replay/restart/scheduler/approval/execution/identity validation re-confirmed
- [x] Commit plan finalized (§7)
- [ ] **Commits actually made** — explicitly not done this pass; awaiting a separate, explicit instruction
- [ ] **Tag cut** — explicitly not done this pass
- [ ] **Merge to a release branch/master** — explicitly not done this pass

---

## 9. GA Recommendation

**Recommended with Known Limitations**, contingent on executing §7's commit plan before cutting a release.

**Evidence for "Recommended":**
- Every architectural correctness issue Production Readiness (P17), RC1, and RC2 identified as a GA
  blocker is fixed and regression-tested, including the specific defect (§1, cross-goal execution-identity
  corruption) RC1's own report cited as the reason it downgraded from "conditional GA" — RC2 closed that,
  and this milestone's own repository/consistency audit surfaced no new defect of comparable severity.
- Full validation is green: 3215 tests, mypy --strict across 388 files, ruff clean, a verified wheel
  build.
- The repository is now internally consistent on the one thing that was genuinely inconsistent
  (versioning) and legally complete (LICENSE present).

**Evidence for "with Known Limitations," not an unconditional "Recommended":**
- §5's six items are real, if non-blocking: a duplicate execution driver whose exposure has grown
  (item 2), a dormant duplicate composition root (item 3), an undisclosed ADR dispute in canonical
  architecture docs (item 4), a communications gap in the project's front door (item 5), and RC2's own
  two carried-forward risks (item 6) — none corrupt data or crash the platform today, but none should be
  silently re-deferred indefinitely either.
- No v1→v2 data migration tool exists; v2 today is greenfield-only (unchanged since RC1, explicitly
  out of scope for both hardening passes).
- The durable schema remains unversioned with no migration mechanism (unchanged since P17).

**The one hard gate before this recommendation is actionable:** none of RC2's fixes or this milestone's
consistency work are committed. "Recommended" describes the working tree as verified in this report, not
the current git history. Executing §7's seven-commit plan is the explicit, single remaining step between
this report and a state that can actually be tagged `v2.0.0` with confidence.
